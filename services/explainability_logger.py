"""
Explainability Logger for SWIFT Processing Pipeline

Accumulates all pipeline step results per message_id and writes
one JSON record per message to a JSONL file at the end of a run.
"""

import json
import uuid
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ExplainabilityLogger:
    """
    Accumulates agent decisions across all pipeline steps per message,
    then flushes one JSONL record per message at the end of the run.
    """

    def __init__(self, filepath: str = "audits/explainability.jsonl"):
        self.filepath = filepath
        self.run_id = str(uuid.uuid4())
        self._records: Dict[str, Dict] = {}
        logger.info(f"ExplainabilityLogger initialized. Run ID: {self.run_id}")

    def _get_record(self, message_id: str) -> Dict:
        """Get or create the record for a given message_id."""
        if message_id not in self._records:
            self._records[message_id] = {
                "run_id": self.run_id,
                "message_id": message_id,
                "steps": {}
            }
        return self._records[message_id]

    def log_evaluator_optimizer(self, messages: List[Dict]):
        """Record Step 1: Evaluator-Optimizer results per message."""
        for msg in messages:
            record = self._get_record(msg.get("message_id"))
            record["steps"]["evaluator_optimizer"] = {
                "agent": "EvaluatorOptimizerPattern",
                "decision": msg.get("validation_status", "UNKNOWN"),
                "output": {
                    "message_type": msg.get("message_type"),
                    "amount": msg.get("amount"),
                    "sender_bic": msg.get("sender_bic"),
                    "receiver_bic": msg.get("receiver_bic"),
                    "validation_errors": msg.get("validation_errors", [])
                }
            }
        logger.info(f"[Step 1] Recorded evaluator-optimizer results for {len(messages)} messages")

    def log_parallelization(self, messages: List[Dict]):
        """Record Step 2: Parallel fraud detection results per message."""
        for msg in messages:
            record = self._get_record(msg.get("message_id"))
            record["steps"]["parallelization"] = {
                "agents_used": [
                    "FraudAmountDetectionAgent",
                    "FraudPatternDetectionAgent",
                    "GeographicRiskAgent"
                ],
                "aggregated_by": "FraudAggAgent",
                "decision": msg.get("fraud_status", "UNKNOWN"),
                "output": {
                    "fraud_score": msg.get("fraud_score"),
                    "fraud_reasons": msg.get("fraud_reasons", [])
                }
            }
        logger.info(f"[Step 2] Recorded parallelization results for {len(messages)} messages")

    def log_prompt_chaining(self, messages: List[Dict], chain_results: Dict):
        """Record Step 3: Prompt chaining results per message."""
        # Build per-message lookup maps from each chain stage
        screening_map = {
            item.get("message_id"): item
            for item in chain_results.get("initial_screening", {}).get("screening_results", [])
        }
        technical_map = {
            item.get("message_id"): item
            for item in chain_results.get("technical_analysis", {}).get("technical_analysis", [])
        }
        compliance_map = {
            item.get("message_id"): item
            for item in chain_results.get("compliance_review", {}).get("compliance_review", [])
        }
        final_map = {
            item.get("message_id"): item
            for item in chain_results.get("final_review", {}).get("final_decisions", [])
        }

        for msg in messages:
            msg_id = msg.get("message_id")
            record = self._get_record(msg_id)
            final = final_map.get(msg_id, {})
            record["steps"]["prompt_chaining"] = {
                "initial_screening": {
                    "agent": "InitialScreener",
                    "decision": screening_map.get(msg_id, {}).get("risk_level", "UNKNOWN"),
                    "output": screening_map.get(msg_id, {})
                },
                "technical_analysis": {
                    "agent": "TechnicalAnalyst",
                    "decision": technical_map.get(msg_id, {}).get("risk_adjustment", "UNKNOWN"),
                    "output": technical_map.get(msg_id, {})
                },
                "risk_assessment": {
                    "agent": "RiskAssessor",
                    "decision": "batch-level",
                    "output": chain_results.get("risk_assessment", {})
                },
                "compliance_review": {
                    "agent": "ComplianceOfficer",
                    "decision": compliance_map.get(msg_id, {}).get("aml_risk", "UNKNOWN"),
                    "output": compliance_map.get(msg_id, {})
                },
                "final_review": {
                    "agent": "FinalReviewer",
                    "decision": final.get("decision", "UNKNOWN"),
                    "output": {
                        "confidence": final.get("confidence"),
                        "justification": final.get("justification"),
                        "key_factors": final.get("key_factors", []),
                        "follow_up_required": final.get("follow_up_required", [])
                    }
                }
            }
        logger.info(f"[Step 3] Recorded prompt chaining results for {len(messages)} messages")

    def log_orchestrator_worker(self, orchestrator_results: Optional[Dict]):
        """Record Step 4: Orchestrator-Worker results as a batch-level entry."""
        if not orchestrator_results:
            return

        analysis = orchestrator_results.get("orchestrator_analysis", {})
        record = self._get_record("__batch__")
        record["steps"]["orchestrator_worker"] = {
            "agent": "Orchestrator + GenericAgent",
            "decision": analysis.get("analysis", ""),
            "output": {
                "task_count": analysis.get("task_count", 0),
                "summary": orchestrator_results.get("summary"),
                "tasks": [
                    {
                        "task_id": t.get("task_id"),
                        "status": t.get("status"),
                        "results": t.get("results")
                    }
                    for t in orchestrator_results.get("task_results", [])
                ]
            }
        }
        logger.info(f"[Step 4] Recorded orchestrator-worker results")

    def flush(self):
        """Write all accumulated records to the JSONL file, one line per message."""
        timestamp = datetime.now().isoformat()
        with open(self.filepath, "a") as f:
            for record in self._records.values():
                record["timestamp"] = timestamp
                f.write(json.dumps(record) + "\n")
        logger.info(f"Flushed {len(self._records)} explainability records to {self.filepath}")
        self._records = {}
