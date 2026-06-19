"""
Evaluator-Optimizer Pattern for SWIFT Message Validation

This module implements iterative validation and correction of SWIFT messages.
The evaluator identifies issues, and the optimizer corrects them.
"""

from typing import Dict, List, Any, Tuple
from agents.workflow_agents.base_agents import SwiftCorrectionAgent, EvaluatorAgent
from config import Config


class EvaluatorOptimizerPattern:
    """
    Implements the evaluator-optimizer pattern for SWIFT message processing.

    This pattern:
    1. Evaluates messages for compliance with SWIFT standards (via EvaluatorAgent)
    2. Optimizes (corrects) any identified issues (via SwiftCorrectionAgent)
    3. Re-evaluates to ensure corrections are valid
    4. Repeats up to MAX_ITERATIONS times
    """

    def __init__(self):
        """Initialize the evaluator-optimizer pattern."""
        self.config = Config()
        self.MAX_ITERATIONS = 3
        self.evaluator_agent = EvaluatorAgent()
        self.correction_agent = SwiftCorrectionAgent()

    def optimize_message(self, message: Dict, errors: List[str]) -> Dict:
        """
        Optimize (correct) a SWIFT message using the SwiftCorrectionAgent.

        Args:
            message: SWIFT message to optimize
            errors: List of errors to correct

        Returns:
            Optimized message
        """
        if not errors:
            return message

        try:
            corrected = self.correction_agent.respond(message, errors)

            for field in self.evaluator_agent.SWIFT_STANDARDS["required_fields"]:
                if field not in corrected:
                    corrected[field] = message.get(field, "")

            return corrected

        except Exception as e:
            print(f"Error during optimization: {e}")
            return message

    def process_with_evaluator_optimizer(self, messages: List[Dict]) -> List[Dict]:
        """
        Process messages through the evaluator-optimizer pattern.

        Args:
            messages: List of SWIFT messages to process

        Returns:
            List of validated and optimized messages
        """
        print("=" * 60)
        print("EVALUATOR-OPTIMIZER PATTERN PROCESSING")
        print("=" * 60)

        optimized_messages = []

        for i, message in enumerate(messages):
            print(f"\nProcessing message {i+1}/{len(messages)}: {message.get('message_id', 'Unknown')}")

            # Iterative evaluation and optimization
            for iteration in range(self.MAX_ITERATIONS):
                is_valid, errors = self.evaluator_agent.evaluate(message)

                if is_valid:
                    print(f"  ✓ Message valid after {iteration} iteration(s)")
                    message['validation_status'] = 'VALID'
                    message['validation_errors'] = []
                    break
                else:
                    print(f"  Iteration {iteration + 1}: Found {len(errors)} error(s)")
                    for error in errors[:3]:  # Show first 3 errors
                        print(f"    - {error}")

                    if iteration < self.MAX_ITERATIONS - 1:
                        # Attempt to optimize
                        print(f"  Attempting optimization...")
                        message = self.optimize_message(message, errors)
                    else:
                        # Max iterations reached
                        print(f"  ✗ Max iterations reached. Message still has errors.")
                        message['validation_status'] = 'INVALID'
                        message['validation_errors'] = errors

            optimized_messages.append(message)

        # Print summary
        valid_count = sum(1 for m in optimized_messages if m.get('validation_status') == 'VALID')
        print(f"\n{'=' * 60}")
        print(f"EVALUATOR-OPTIMIZER SUMMARY")
        print(f"{'=' * 60}")
        print(f"Total messages processed: {len(optimized_messages)}")
        print(f"Valid messages: {valid_count}")
        print(f"Invalid messages: {len(optimized_messages) - valid_count}")

        return optimized_messages

    def test_pattern(self):
        """
        Test the evaluator-optimizer pattern with sample messages.
        You can use this to verify the pattern works with your implementations.
        """
        test_messages = [
            {
                'message_id': 'VALID001',
                'message_type': 'MT103',
                'reference': 'REF123456',
                'amount': '5000.00 USD',
                'sender_bic': 'CHASUS33XXX',
                'receiver_bic': 'DEUTDEFFXXX',
                'remittance_info': 'Invoice payment'
            },
            {
                'message_id': 'INVALID001',
                'message_type': 'MT999',  # Invalid type
                'reference': 'THIS_REFERENCE_IS_WAY_TOO_LONG_12345',  # Too long
                'amount': '9999999999.99 USD',  # Too large
                'sender_bic': 'INVALID',  # Invalid BIC
                'receiver_bic': 'INVALID',  # Invalid BIC
                'remittance_info': 'Test invalid message'
            },
            {
                'message_id': 'FIXABLE001',
                'message_type': 'MT103',
                'reference': 'REF_NEEDS_FIX_123456789',  # Slightly too long
                'amount': '0.001 USD',  # Too small
                'sender_bic': 'TEST1234',  # Invalid format
                'receiver_bic': 'BARCGB22XXX',
                'remittance_info': 'Should be fixable'
            }
        ]

        print("Testing Evaluator-Optimizer Pattern\n")
        results = self.process_with_evaluator_optimizer(test_messages)

        print("\nTest Results:")
        for msg in results:
            print(f"\n{msg.get('message_id')}:")
            print(f"  Status: {msg.get('validation_status')}")
            if msg.get('validation_errors'):
                print(f"  Remaining errors: {len(msg.get('validation_errors'))}")

        return results


if __name__ == "__main__":
    # Test the evaluator-optimizer pattern
    pattern = EvaluatorOptimizerPattern()
    pattern.test_pattern()