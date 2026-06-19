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
        
    
    def run(self):
        """Main execution method - Orchestrates all agent patterns in sequence"""
        try:
            print("=" * 60)
            print("SWIFT TRANSACTION PROCESSING SYSTEM")
            print("=" * 60)

            # Step 1: Generate SWIFT messages
            print("\nGenerating SWIFT messages...")
            messages = self.generate_swift_messages()
            print(f"Generated {len(messages)} SWIFT messages")

            validated_messages = self.process_with_evaluator_optimizer(messages)
            self.explainability_logger.log_evaluator_optimizer(validated_messages)

            processed_messages = self.process_with_parallelization(validated_messages)
            self.explainability_logger.log_parallelization(processed_messages)

            chain_results = self.process_with_prompt_chaining(processed_messages)
            self.explainability_logger.log_prompt_chaining(processed_messages, chain_results)

            orchestrator_results = self.process_with_orchestrator_worker(processed_messages)
            self.explainability_logger.log_orchestrator_worker(
                orchestrator_results.get('run_1_non_fraudulent')
            )
            self.explainability_logger.log_orchestrator_worker(
                orchestrator_results.get('run_2_high_value')
            )

            self.explainability_logger.flush()

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
