"""
Base Agent Classes for SWIFT Transaction Processing

This module contains the base classes that all agents inherit from.
You will implement the BaseAgent abstract class and the SwiftCorrectionAgent.
"""

from abc import ABC, abstractmethod
from config import Config
from services.llm_service import LLMService


class BaseAgent(ABC):
    def __init__(self):
        self.config = Config()
        self.llm_service = LLMService()

    @abstractmethod
    def create_prompt(self, data):
        """Each agent must implement its own prompt creation."""
        pass

    def respond(self, prompt: str):
        """Common method to get LLM response."""
        return self.llm_service.get_swift_correction(prompt)


class SwiftCorrectionAgent(BaseAgent):
    """Agent for correcting SWIFT messages based on validation errors."""

    def __init__(self):
        super().__init__()

    def create_prompt(self, data: dict) -> tuple:
        """
        Create prompts for the LLM to correct a SWIFT message.

        Args:
            data: Dict with 'message' and 'errors' keys

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        message = data.get('message')
        errors = data.get('errors')

        system_prompt = """You are a SWIFT message correction expert.
        Fix the validation errors while maintaining the business intent.
        Return the corrected message in JSON format."""

        user_prompt = f"""
        Original SWIFT Message:
        {message}

        Validation Errors to Fix:
        {errors}

        Please correct these errors and return the complete corrected message in JSON format.
        """

        return system_prompt, user_prompt

    def respond(self, message, errors):
        """
        Get LLM response to correct the SWIFT message.

        Args:
            message: The SWIFT message to correct
            errors: The validation errors to fix

        Returns:
            dict: The corrected message data
        """
        import json

        system_prompt, user_prompt = self.create_prompt({'message': message, 'errors': errors})

        try:
            response = self.llm_service.client.chat.completions.create(
                model=self.llm_service.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )

            content = response.choices[0].message.content
            result = json.loads(content)
            return result

        except Exception as e:
            print(f"Error in SwiftCorrectionAgent: {e}")
            return message


class EvaluatorAgent(BaseAgent):
    """Agent for evaluating SWIFT messages against SWIFT standards."""

    def __init__(self):
        super().__init__()
        self.SWIFT_STANDARDS = {
            "max_reference_length": 16,
            "max_amount": 999999999.99,
            "min_amount": 0.01,
            "required_fields": [
                "message_type", "reference", "amount",
                "sender_bic", "receiver_bic"
            ],
            "valid_message_types": ["MT103", "MT202"],
            "valid_currencies": ["USD", "EUR", "GBP", "JPY", "CHF"]
        }

    def create_prompt(self, data: dict) -> str:
        """Create a prompt describing the message for evaluation context."""
        return f"Evaluate this SWIFT message for compliance: {data}"

    def evaluate(self, message: dict) -> tuple:
        """
        Evaluate a SWIFT message against SWIFT standards.

        Args:
            message: The SWIFT message to evaluate

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        for field in self.SWIFT_STANDARDS["required_fields"]:
            if field not in message or not message[field]:
                errors.append(f"Missing required field: {field}")

        if message.get("message_type") not in self.SWIFT_STANDARDS["valid_message_types"]:
            errors.append(f"Invalid message type: {message.get('message_type')}")

        reference = message.get("reference", "")
        if len(reference) > self.SWIFT_STANDARDS["max_reference_length"]:
            errors.append(f"Reference too long: {len(reference)} chars (max {self.SWIFT_STANDARDS['max_reference_length']})")

        try:
            amount_str = message.get("amount", "0")
            amount_value = float(''.join(c for c in amount_str.split()[0] if c.isdigit() or c == '.'))
            if amount_value > self.SWIFT_STANDARDS["max_amount"]:
                errors.append(f"Amount exceeds maximum: {amount_value}")
            elif amount_value < self.SWIFT_STANDARDS["min_amount"]:
                errors.append(f"Amount below minimum: {amount_value}")
        except (ValueError, IndexError, AttributeError):
            errors.append(f"Invalid amount format: {message.get('amount')}")

        sender_bic = message.get("sender_bic", "")
        receiver_bic = message.get("receiver_bic", "")

        if not self._validate_bic(sender_bic):
            errors.append(f"Invalid sender BIC: {sender_bic}")
        if not self._validate_bic(receiver_bic):
            errors.append(f"Invalid receiver BIC: {receiver_bic}")

        if sender_bic and sender_bic == receiver_bic:
            errors.append("Sender and receiver BIC cannot be the same")

        if "amount" in message:
            try:
                currency = message["amount"].split()[-1]
                if currency not in self.SWIFT_STANDARDS["valid_currencies"]:
                    errors.append(f"Invalid currency: {currency}")
            except (IndexError, AttributeError):
                errors.append("Cannot extract currency from amount")

        return len(errors) == 0, errors

    def _validate_bic(self, bic: str) -> bool:
        """Validate BIC format (8 or 11 characters)."""
        if not bic or len(bic) not in [8, 11]:
            return False
        if not bic[:4].isalpha():
            return False
        if not bic[4:6].isalpha():
            return False
        if not bic[6:8].isalnum():
            return False
        if len(bic) == 11 and not bic[8:11].isalnum():
            return False
        return True


class FraudAmountDetectionAgent:
    """Agent for detecting fraud based on transaction amounts."""

    def __init__(self):
        self.rules = [
            {"condition": "amount > 10000", "risk_score": 0.3},
            {"condition": "round_amount", "risk_score": 0.2},
            {"condition": "unusual_precision", "risk_score": 0.1}
        ]

    def analyze(self, message):
        """
        Analyze a SWIFT message for amount-based fraud patterns.

        Args:
            message: The SWIFT message to analyze

        Returns:
            dict: Fraud analysis results with risk score and reasons
        """
        risk_score = 0
        fraud_reasons = []

        try:
            # Extract amount from message
            amount_str = message.get('amount', '0')
            # Remove currency code and convert to float
            amount = float(''.join(c for c in amount_str if c.isdigit() or c == '.'))

            # Rule 1: Large amounts
            if amount > 10000:
                risk_score += 0.3
                fraud_reasons.append(f"High amount transaction: {amount}")

            # Rule 2: Round amounts (multiples of 1000)
            if amount % 1000 == 0 and amount > 0:
                risk_score += 0.2
                fraud_reasons.append(f"Suspiciously round amount: {amount}")

            # Rule 3: Unusual precision for large amounts
            if amount > 100000 and (amount % 1) != 0:
                risk_score += 0.1
                fraud_reasons.append("Large amount with unusual decimal precision")

        except (ValueError, TypeError) as e:
            print(f"Error analyzing amount: {e}")

        return {
            "agent": "FraudAmountDetectionAgent",
            "risk_score": min(risk_score, 1.0),
            "fraud_reasons": fraud_reasons
        }


class FraudPatternDetectionAgent:
    """Agent for detecting fraud based on transaction patterns."""

    def __init__(self):
        self.high_risk_patterns = ['TEST', 'FAKE', 'DEMO', '999', '000000']
        self.suspicious_keywords = ['urgent', 'immediately', 'secret', 'confidential']

    def analyze(self, message):
        """
        Analyze a SWIFT message for pattern-based fraud indicators.

        Args:
            message: The SWIFT message to analyze

        Returns:
            dict: Fraud analysis results with risk score and reasons
        """
        risk_score = 0
        fraud_reasons = []

        # Check BIC codes for test patterns
        sender_bic = message.get('sender_bic', '')
        receiver_bic = message.get('receiver_bic', '')

        for pattern in self.high_risk_patterns:
            if pattern in sender_bic.upper() or pattern in receiver_bic.upper():
                risk_score += 0.4
                fraud_reasons.append(f"Test/fake pattern detected in BIC: {pattern}")

        # Check for same sender and receiver
        if sender_bic and sender_bic == receiver_bic:
            risk_score += 0.5
            fraud_reasons.append("Same sender and receiver BIC")

        # Check remittance info for suspicious keywords
        remittance = message.get('remittance_info', '').lower()
        for keyword in self.suspicious_keywords:
            if keyword in remittance:
                risk_score += 0.2
                fraud_reasons.append(f"Suspicious keyword in remittance: {keyword}")

        return {
            "agent": "FraudPatternDetectionAgent",
            "risk_score": min(risk_score, 1.0),
            "fraud_reasons": fraud_reasons
        }


class FraudAggAgent:
    """Agent for aggregating fraud detection results from multiple agents."""

    def __init__(self):
        self.threshold = 0.5  # Fraud threshold (50%)

    def aggregate_results(self, fraud_results):
        """
        Aggregate fraud detection results from multiple agents.

        Args:
            fraud_results: List of fraud detection results from different agents

        Returns:
            dict: Aggregated fraud assessment
        """
        if not fraud_results:
            return {
                "is_fraudulent": False,
                "confidence": 0,
                "total_risk_score": 0,
                "aggregated_reasons": []
            }

        # Calculate average risk score
        total_risk = sum(r.get('risk_score', 0) for r in fraud_results)
        avg_risk = total_risk / len(fraud_results)

        # Aggregate all fraud reasons
        all_reasons = []
        for result in fraud_results:
            agent_name = result.get('agent', 'Unknown')
            reasons = result.get('fraud_reasons', [])
            for reason in reasons:
                all_reasons.append(f"[{agent_name}] {reason}")

        # Determine if fraudulent based on threshold
        is_fraudulent = avg_risk >= self.threshold

        return {
            "is_fraudulent": is_fraudulent,
            "confidence": round(avg_risk * 100, 2),
            "total_risk_score": round(avg_risk, 3),
            "aggregated_reasons": all_reasons
        }