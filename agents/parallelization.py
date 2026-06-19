"""
Parallelization Pattern for Concurrent Fraud Detection

This module implements parallel fraud detection using multiple agents.
You will add a third fraud detection agent and implement aggregation.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any
import json
import logging
import time
from agents.workflow_agents.base_agents import (
    FraudAmountDetectionAgent,
    FraudPatternDetectionAgent,
    FraudAggAgent
)
from services.llm_service import LLMService


class AnomalyDetectionAgent:
    """LLM-based agent that uses GPT-4o to detect anomalous patterns in SWIFT messages."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.llm_service = LLMService()

    def analyze(self, message: Dict) -> Dict:
        """
        Use GPT-4o to analyze a SWIFT message for anomalous patterns
        that rule-based agents might miss.

        Args:
            message: SWIFT message to analyze

        Returns:
            dict: Fraud analysis results with risk score and reasons
        """
        try:
            prompt = f"""Analyze this SWIFT transaction for anomalies and fraud indicators.
Consider unusual field combinations, timing patterns, naming conventions,
and anything that deviates from normal banking transaction patterns.

Transaction:
- Message ID: {message.get('message_id', 'N/A')}
- Type: {message.get('message_type', 'N/A')}
- Amount: {message.get('amount', 'N/A')}
- Sender BIC: {message.get('sender_bic', 'N/A')}
- Receiver BIC: {message.get('receiver_bic', 'N/A')}
- Reference: {message.get('reference', 'N/A')}
- Remittance Info: {message.get('remittance_info', 'N/A')}
- Ordering Customer: {message.get('ordering_customer', 'N/A')}
- Beneficiary: {message.get('beneficiary', 'N/A')}
- Value Date: {message.get('value_date', 'N/A')}

Respond with JSON in this exact format:
{{
    "risk_score": 0.0 to 1.0,
    "anomalies": ["list of detected anomalies"],
    "reasoning": "brief explanation"
}}"""

            response = self.llm_service.client.chat.completions.create(
                model=self.llm_service.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an AI fraud analyst specializing in SWIFT transaction anomaly detection. "
                        "Evaluate transactions for subtle anomalies that rule-based systems might miss. "
                        "Be conservative — only flag genuinely suspicious patterns. "
                        "Respond with JSON only."
                    },
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )

            result = json.loads(response.choices[0].message.content or "{}")
            risk_score = float(result.get("risk_score", 0))
            anomalies = result.get("anomalies", [])

            return {
                "agent": "AnomalyDetectionAgent",
                "risk_score": min(risk_score, 1.0),
                "fraud_reasons": anomalies
            }

        except Exception as e:
            self.logger.error(f"AnomalyDetectionAgent error: {e}")
            return {
                "agent": "AnomalyDetectionAgent",
                "risk_score": 0,
                "fraud_reasons": []
            }


class GeographicRiskAgent:
    """Agent for detecting fraud based on geographic risk of BIC country codes."""

    def __init__(self):
        # BIC format: AAAABBCC... where chars 4-5 are the ISO country code
        self.high_risk_countries = {'IR', 'KP', 'SY', 'CU', 'VE', 'MM', 'YE', 'LY', 'SD', 'SO'}
        self.medium_risk_countries = {'AF', 'IQ', 'PK', 'NG', 'UA', 'RU', 'BY'}

    def analyze(self, message: Dict) -> Dict:
        risk_score = 0
        fraud_reasons = []

        sender_bic = message.get('sender_bic', '')
        receiver_bic = message.get('receiver_bic', '')

        sender_country = sender_bic[4:6].upper() if len(sender_bic) >= 6 else ''
        receiver_country = receiver_bic[4:6].upper() if len(receiver_bic) >= 6 else ''

        for country, label in [(sender_country, 'sender'), (receiver_country, 'receiver')]:
            if country in self.high_risk_countries:
                risk_score += 0.5
                fraud_reasons.append(f"High-risk country detected for {label}: {country}")
            elif country in self.medium_risk_countries:
                risk_score += 0.25
                fraud_reasons.append(f"Medium-risk country detected for {label}: {country}")

        return {
            "agent": "GeographicRiskAgent",
            "risk_score": min(risk_score, 1.0),
            "fraud_reasons": fraud_reasons
        }


class ParallelizationPattern:
    """
    Implements parallel processing of fraud detection agents.
    Multiple agents analyze messages concurrently for better performance.
    """

    def __init__(self, max_workers: int = 8):
        """
        Initialize the parallelization pattern.

        Args:
            max_workers: Maximum number of concurrent threads
        """
        self.max_workers = max_workers

        self.list_of_agents = [
            FraudAmountDetectionAgent(),
            FraudPatternDetectionAgent(),
            GeographicRiskAgent(),
            AnomalyDetectionAgent()
        ]

    def _process_message(self, message: Dict, agent: Any) -> Dict:
        """
        Process a single message with a specific fraud detection agent.

        Args:
            message: SWIFT message to analyze
            agent: Fraud detection agent to use

        Returns:
            Fraud analysis results from the agent
        """
        try:
            # Call the agent's analyze method
            result = agent.analyze(message)
            result['message_id'] = message.get('message_id', 'unknown')
            return result
        except Exception as e:
            print(f"Error in agent {agent.__class__.__name__}: {e}")
            return {
                'agent': agent.__class__.__name__,
                'error': str(e),
                'risk_score': 0,
                'fraud_reasons': []
            }

    def process_batch_parallel(self, messages: List[Dict]) -> List[Dict]:
        """
        Process a batch of messages in parallel using all fraud detection agents.

        Args:
            messages: List of SWIFT messages to process

        Returns:
            List of messages with fraud detection results
        """
        print(f"Processing {len(messages)} messages with {len(self.list_of_agents)} agents in parallel...")
        start_time = time.time()

        aggregator = FraudAggAgent()

        # Process messages in parallel
        processed_messages = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_msg = {}
            for message in messages:
                # Submit tasks for each agent to analyze this message
                agent_futures = []
                for agent in self.list_of_agents:
                    future = executor.submit(self._process_message, message, agent)
                    agent_futures.append(future)

                future_to_msg[message['message_id']] = {
                    'message': message,
                    'futures': agent_futures
                }

            # Collect results
            for msg_id, msg_data in future_to_msg.items():
                message = msg_data['message']
                agent_results = []

                # Wait for all agents to complete for this message
                for future in msg_data['futures']:
                    try:
                        result = future.result(timeout=30)
                        agent_results.append(result)
                    except Exception as e:
                        print(f"Error getting result for message {msg_id}: {e}")

                aggregated = aggregator.aggregate_results(agent_results)
                message['fraud_status'] = "FRAUDULENT" if aggregated['is_fraudulent'] else "CLEAN"
                message['fraud_score'] = aggregated['confidence']
                message['fraud_reasons'] = aggregated['aggregated_reasons']

                processed_messages.append(message)

        elapsed_time = time.time() - start_time
        print(f"Parallel processing completed in {elapsed_time:.2f} seconds")

        # Print fraud summary
        fraudulent_count = sum(1 for m in processed_messages
                              if m.get('fraud_status') == 'FRAUDULENT')
        print(f"Fraud Detection Summary: {fraudulent_count}/{len(processed_messages)} messages flagged as fraudulent")

        return processed_messages

    def test_agents(self):
        """
        Test method to verify all agents are working.
        You can use this to test your third agent.
        """
        test_message = {
            'message_id': 'TEST001',
            'amount': '15000.00 USD',
            'sender_bic': 'TESTUS33XXX',
            'receiver_bic': 'FAKEGB22XXX',
            'remittance_info': 'Urgent payment needed immediately'
        }

        print("Testing fraud detection agents:")
        print(f"Test message: {test_message}")
        print("\nAgent results:")

        for agent in self.list_of_agents:
            result = agent.analyze(test_message)
            print(f"\n{agent.__class__.__name__}:")
            print(f"  Risk Score: {result.get('risk_score', 0)}")
            print(f"  Reasons: {result.get('fraud_reasons', [])}")

        # Test aggregation if aggregator is available
        if hasattr(self, 'aggregator'):
            agent_results = [agent.analyze(test_message) for agent in self.list_of_agents]
            aggregated = self.aggregator.aggregate_results(agent_results)
            print(f"\nAggregated Result:")
            print(f"  Is Fraudulent: {aggregated['is_fraudulent']}")
            print(f"  Confidence: {aggregated['confidence']}%")
            print(f"  Total Risk Score: {aggregated['total_risk_score']}")


if __name__ == "__main__":
    # Test the parallelization pattern
    pattern = ParallelizationPattern()
    pattern.test_agents()