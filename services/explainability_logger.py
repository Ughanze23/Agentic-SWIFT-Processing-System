"""
Explainability Logger for SWIFT Processing Pipeline

Records agent decisions, inputs, and outputs at each pipeline step
into a JSONL file for auditability and transparency.
"""

import json
import uuid
import logging
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ExplainabilityLogger:
    """Logs agent decisions and outputs to a JSONL file for explainability."""

    def __init__(self, filepath: str = "explainability.jsonl"):
        self.filepath = filepath
        self.run_id = str(uuid.uuid4())
        logger.info(f"ExplainabilityLogger initialized. Run ID: {self.run_id}, File: {self.filepath}")

    def log(
        self,
        step: int,
        step_name: str,
        agent: str,
        decision: str,
        output: Any,
        message_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ):
        """
        Write a single explainability entry to the JSONL file.

        Args:
            step: Pipeline step number (1-4)
            step_name: Human-readable step name
            agent: Name of the agent that produced this output
            decision: The decision or verdict made (e.g. VALID, FRAUDULENT, APPROVE)
            output: The full output/result from the agent
            message_id: SWIFT message ID if applicable
            metadata: Any additional context
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "run_id": self.run_id,
            "step": step,
            "step_name": step_name,
            "agent": agent,
            "message_id": message_id,
            "decision": decision,
            "output": output,
            "metadata": metadata or {}
        }
        try:
            with open(self.filepath, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.error(f"Failed to write explainability log: {e}")

    def log_evaluator_optimizer(self, messages: list):
        """Log results from Step 1: Evaluator-Optimizer."""
        for msg in messages:
            self.log(
                step=1,
                step_name="Evaluator-Optimizer",
                agent="EvaluatorOptimizerPattern",
                message_id=msg.get("message_id"),
                decision=msg.get("validation_status", "UNKNOWN"),
                output={
                    "validation_errors": msg.get("validation_errors", []),
                    "message_type": msg.get("message_type"),
                    "amount": msg.get("amount"),
                    "sender_bic": msg.get("sender_bic"),
                    "receiver_bic": msg.get("receiver_bic")
                }
            )
        logger.info(f"[Step 1] Logged {len(messages)} evaluator-optimizer results")

    def log_parallelization(self, messages: list):
        """Log results from Step 2: Parallelization (Fraud Detection)."""
        for msg in messages:
            self.log(
                step=2,
                step_name="Parallelization",
                agent="FraudAggAgent",
                message_id=msg.get("message_id"),
                decision=msg.get("fraud_status", "UNKNOWN"),
                output={
                    "fraud_score": msg.get("fraud_score"),
                    "fraud_reasons": msg.get("fraud_reasons", [])
                },
                metadata={
                    "agents_used": [
                        "FraudAmountDetectionAgent",
                        "FraudPatternDetectionAgent",
                        "GeographicRiskAgent"
                    ]
                }
            )
        fraudulent = sum(1 for m in messages if m.get("fraud_status") == "FRAUDULENT")
        logger.info(f"[Step 2] Logged {len(messages)} fraud detection results. Fraudulent: {fraudulent}")

    def log_prompt_chaining(self, chain_results: dict):
        """Log results from Step 3: Prompt Chaining."""
        step_agents = {
            "initial_screening": "InitialScreener",
            "technical_analysis": "TechnicalAnalyst",
            "risk_assessment": "RiskAssessor",
            "compliance_review": "ComplianceOfficer",
            "final_review": "FinalReviewer"
        }
        for stage_key, agent_name in step_agents.items():
            stage_data = chain_results.get(stage_key, {})
            if not stage_data:
                continue

            decision = (
                stage_data.get("summary")
                or stage_data.get("technical_summary")
                or stage_data.get("compliance_summary")
                or str(stage_data.get("batch_summary", "See output"))
            )

            self.log(
                step=3,
                step_name="Prompt-Chaining",
                agent=agent_name,
                decision=decision,
                output=stage_data
            )
        logger.info(f"[Step 3] Logged {len(step_agents)} prompt chaining stages")

    def log_orchestrator_worker(self, orchestrator_results: dict):
        """Log results from Step 4: Orchestrator-Worker."""
        if not orchestrator_results:
            return

        analysis = orchestrator_results.get("orchestrator_analysis", {})
        self.log(
            step=4,
            step_name="Orchestrator-Worker",
            agent="Orchestrator",
            decision=analysis.get("analysis", "Tasks created"),
            output={
                "task_count": analysis.get("task_count", 0),
                "tasks": analysis.get("tasks", [])
            }
        )

        for task_result in orchestrator_results.get("task_results", []):
            self.log(
                step=4,
                step_name="Orchestrator-Worker",
                agent="GenericAgent",
                decision="completed",
                output=task_result.get("results", {}),
                metadata={
                    "task_id": task_result.get("task_id"),
                    "status": task_result.get("status")
                }
            )

        total_tasks = len(orchestrator_results.get("task_results", []))
        logger.info(f"[Step 4] Logged orchestrator analysis + {total_tasks} task results")
