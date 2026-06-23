"""
SWIFT Transaction Processing System with Agent Patterns
Main application entry point

This is the main integration point where all agent patterns work together
to process SWIFT messages through a complete pipeline.
"""

import logging
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import Config
from models.swift_message import SWIFTMessage
from services.swift_generator import SWIFTGenerator

# Import the agent patterns you'll be using
from agents.evaluator_optimizer import EvaluatorOptimizerPattern
from agents.parallelization import ParallelizationPattern
from agents.orchestrator_worker import OrchestratorWorkerPattern
from agents.prompt_chaining import PromptChainingPattern
from services.explainability_logger import ExplainabilityLogger
from services.metrics_collector import MetricsCollector


class SWIFTProcessingSystem:
    """Main system orchestrating all agent patterns for SWIFT processing"""

    def __init__(self):
        self.config = Config()
        self.swift_generator = SWIFTGenerator()

        # Initialize agent patterns
        # NOTE: These classes are scaffolded in the agents folder
        # You'll need to complete the TODOs in each file for them to work properly
        self.evaluator_optimizer = EvaluatorOptimizerPattern()
        self.parallelization_agent = ParallelizationPattern()
        self.orchestrator_worker = OrchestratorWorkerPattern()
        self.prompt_chaining_agent = PromptChainingPattern()
        self.explainability_logger = ExplainabilityLogger()
        self.metrics = MetricsCollector()

        # Wire metrics collector into all LLM services
        for pattern in [self.evaluator_optimizer, self.parallelization_agent,
                        self.orchestrator_worker, self.prompt_chaining_agent]:
            self._inject_metrics(pattern)
    
    def _inject_metrics(self, pattern):
        """Inject the metrics collector into any LLM service found on a pattern."""
        if hasattr(pattern, 'llm_service'):
            pattern.llm_service.metrics_collector = self.metrics
        # Evaluator-optimizer has agents with their own LLM services
        for attr_name in ['correction_agent', 'evaluator_agent']:
            agent = getattr(pattern, attr_name, None)
            if agent and hasattr(agent, 'llm_service'):
                agent.llm_service.metrics_collector = self.metrics
        # Parallelization has a list of agents
        for agent in getattr(pattern, 'list_of_agents', []):
            if hasattr(agent, 'llm_service'):
                agent.llm_service.metrics_collector = self.metrics

    def generate_swift_messages(self) -> List[Dict]:
        """Generate SWIFT messages for testing"""
        raw_messages = self.swift_generator.generate_messages(
            count=self.config.MESSAGE_COUNT,
            bank_count=self.config.BANK_COUNT
        )
        messages = []
        for msg in raw_messages:
            msg_dict = msg.model_dump(mode='json')
            msg_dict['amount'] = f"{msg.amount} {msg.currency}"
            messages.append(msg_dict)
        return messages
    
    def process_with_evaluator_optimizer(self, messages: List[Dict]) -> List[Dict]:
        """
        Step 1: Validate and correct SWIFT messages using Evaluator-Optimizer pattern

        This method calls the evaluator optimizer pattern to validate and fix messages.
        """
        print("\n" + "=" * 60)
        print("STEP 1: EVALUATOR-OPTIMIZER PATTERN")
        print("=" * 60)

        # Call the evaluator optimizer's process method
        validated_messages = self.evaluator_optimizer.process_with_evaluator_optimizer(messages)
        return validated_messages

    def process_with_parallelization(self, messages: List[Dict]) -> List[Dict]:
        """
        Step 2: Process messages in parallel with fraud detection

        This method uses parallel processing to run multiple fraud detection agents.
        """
        print("\n" + "=" * 60)
        print("STEP 2: PARALLELIZATION PATTERN")
        print("=" * 60)

        # Process messages in parallel using fraud detection agents
        processed_messages = self.parallelization_agent.process_batch_parallel(messages)
        return processed_messages

    def process_with_prompt_chaining(self, messages: List[Dict]) -> Dict:
        """
        Step 3: Enhanced fraud analysis using Prompt Chaining pattern

        This method chains multiple AI agents for comprehensive fraud analysis.
        """
        print("\n" + "=" * 60)
        print("STEP 3: PROMPT CHAINING PATTERN")
        print("=" * 60)

        # Process through the chain of agents
        chain_results = self.prompt_chaining_agent.process_chain(messages)
        return chain_results

    def process_with_orchestrator_worker(self, messages: List[Dict]) -> None:
        """
        Step 4: Process transactions using Orchestrator-Worker pattern

        This method uses an orchestrator to create tasks and workers to execute them.
        """
        print("\n" + "=" * 60)
        print("STEP 4: ORCHESTRATOR-WORKER PATTERN")
        print("=" * 60)

        results = {}

        # Run 1: Non-fraudulent messages
        print("\n--- Run 1: Non-fraudulent messages ---")
        clean_messages = [msg for msg in messages if msg.get('fraud_status') != "FRAUDULENT"]
        results['run_1_non_fraudulent'] = self.orchestrator_worker.process_with_orchestrator(clean_messages)

        # Run 2: High-value transactions (amount > 50000)
        print("\n--- Run 2: High-value transactions (> 50000) ---")
        high_value_messages = []
        for msg in messages:
            try:
                amount = float(msg.get('amount', '0').split()[0])
                if amount > 50000:
                    high_value_messages.append(msg)
            except (ValueError, TypeError):
                pass
        results['run_2_high_value'] = self.orchestrator_worker.process_with_orchestrator(high_value_messages)

        return results
        
    
    def _set_llm_step(self, step_name: str):
        """Set the current step label on all LLM services for metrics tagging."""
        for pattern in [self.evaluator_optimizer, self.parallelization_agent,
                        self.orchestrator_worker, self.prompt_chaining_agent]:
            if hasattr(pattern, 'llm_service'):
                pattern.llm_service._current_step = step_name
            for attr_name in ['correction_agent', 'evaluator_agent']:
                agent = getattr(pattern, attr_name, None)
                if agent and hasattr(agent, 'llm_service'):
                    agent.llm_service._current_step = step_name
            for agent in getattr(pattern, 'list_of_agents', []):
                if hasattr(agent, 'llm_service'):
                    agent.llm_service._current_step = step_name

    def run(self):
        """Main execution method - Orchestrates all agent patterns in sequence"""
        try:
            self.metrics.start_run()

            print("=" * 60)
            print("SWIFT TRANSACTION PROCESSING SYSTEM")
            print("=" * 60)

            # Step 1: Generate SWIFT messages
            print("\nGenerating SWIFT messages...")
            messages = self.generate_swift_messages()
            print(f"Generated {len(messages)} SWIFT messages")

            # Step 2: Evaluator-Optimizer
            self._set_llm_step("evaluator_optimizer")
            self.metrics.start_step("evaluator_optimizer")
            validated_messages = self.process_with_evaluator_optimizer(messages)
            self.metrics.end_step("evaluator_optimizer", len(validated_messages))
            self.explainability_logger.log_evaluator_optimizer(validated_messages)

            valid_count = sum(1 for m in validated_messages if m.get('validation_status') == 'VALID')
            invalid_count = len(validated_messages) - valid_count
            self.metrics.record_operational_stats("evaluator_optimizer", {
                "total": len(validated_messages),
                "valid": valid_count,
                "invalid": invalid_count,
                "stp_rate": round(valid_count / len(validated_messages), 3) if validated_messages else 0,
                "manual_repair_rate": round(invalid_count / len(validated_messages), 3) if validated_messages else 0,
            })

            # Step 3: Parallelization (fraud detection)
            self._set_llm_step("parallelization")
            self.metrics.start_step("parallelization")
            processed_messages = self.process_with_parallelization(validated_messages)
            self.metrics.end_step("parallelization", len(processed_messages))
            self.explainability_logger.log_parallelization(processed_messages)

            fraud_count = sum(1 for m in processed_messages if m.get('fraud_status') == 'FRAUDULENT')
            clean_count = len(processed_messages) - fraud_count
            self.metrics.record_operational_stats("parallelization", {
                "total": len(processed_messages),
                "fraudulent": fraud_count,
                "clean": clean_count,
                "fraud_flag_rate": round(fraud_count / len(processed_messages), 3) if processed_messages else 0,
            })

            # Step 4: Prompt Chaining
            self._set_llm_step("prompt_chaining")
            self.metrics.start_step("prompt_chaining")
            chain_results = self.process_with_prompt_chaining(processed_messages)
            self.metrics.end_step("prompt_chaining", len(processed_messages))
            self.explainability_logger.log_prompt_chaining(processed_messages, chain_results)

            final_decisions = chain_results.get('final_review', {}).get('final_decisions', [])
            decision_counts = {"APPROVE": 0, "HOLD": 0, "REJECT": 0}
            for d in final_decisions:
                dec = d.get('decision', 'UNKNOWN')
                if dec in decision_counts:
                    decision_counts[dec] += 1
            self.metrics.record_operational_stats("prompt_chaining", {
                "total": len(processed_messages),
                "decisions": decision_counts,
            })

            # Step 5: Orchestrator-Worker
            self._set_llm_step("orchestrator_worker")
            self.metrics.start_step("orchestrator_worker")
            orchestrator_results = self.process_with_orchestrator_worker(processed_messages)
            self.metrics.end_step("orchestrator_worker", len(processed_messages))
            self.explainability_logger.log_orchestrator_worker(
                orchestrator_results.get('run_1_non_fraudulent')
            )
            self.explainability_logger.log_orchestrator_worker(
                orchestrator_results.get('run_2_high_value')
            )

            run1 = orchestrator_results.get('run_1_non_fraudulent', {})
            run2 = orchestrator_results.get('run_2_high_value', {})
            self.metrics.record_operational_stats("orchestrator_worker", {
                "run_1_groups": len(run1.get('groups', [])),
                "run_1_tasks": len(run1.get('task_results', [])),
                "run_2_groups": len(run2.get('groups', [])),
                "run_2_tasks": len(run2.get('task_results', [])),
            })

            self.metrics.end_run()
            self.explainability_logger.flush()
            self.metrics.save()

            print("\n" + "=" * 60)
            print("PROCESSING COMPLETE")
            print("=" * 60)

        except Exception as e:
            print(f"Error in main execution: {e}")
            raise


def configure_logging():
    """Configure logging to output to both console and file."""
    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("swift_processing.log", mode="a")
        ]
    )


if __name__ == "__main__":
    configure_logging()
    system = SWIFTProcessingSystem()
    system.run()
