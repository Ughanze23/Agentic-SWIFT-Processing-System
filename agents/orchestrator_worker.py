"""
Orchestrator-Worker Pattern for Task Distribution

This module implements the orchestrator-worker pattern where an orchestrator
analyzes a batch of SWIFT messages, proposes a grouping plan (e.g. by currency,
bank, or risk tier), and workers produce a structured report per group.
"""

import json
from typing import Dict, List, Any
from config import Config
from services.llm_service import LLMService


class OrchestratorWorkerPattern:
    """
    Implements the orchestrator-worker pattern for SWIFT message processing.
    The orchestrator proposes a grouping plan and workers produce reports per group.
    """

    def __init__(self):
        """Initialize the orchestrator-worker pattern."""
        self.config = Config()
        self.llm_service = LLMService()
        self.client = self.llm_service.client
        self.model = self.llm_service.model

    class Orchestrator:
        """
        Orchestrator that analyzes messages and proposes a grouping plan.
        It partitions messages into named groups by a chosen dimension
        (currency, bank, risk tier, message type, etc.) and creates
        one report task per group for workers to execute.
        """

        def __init__(self, llm_service: LLMService):
            """Initialize the Orchestrator."""
            self.llm_service = llm_service
            self.model = llm_service.model

        def analyze_and_create_tasks(self, messages: List[Dict]) -> Dict:
            """
            Analyze messages, propose a grouping plan, and create one
            report task per group.

            Args:
                messages: List of SWIFT messages to analyze

            Returns:
                Dictionary with grouping plan and tasks
            """
            system_prompt = """You are an Orchestrator for SWIFT transaction processing.

Your job is to:
1. Examine the batch of messages.
2. Choose the BEST grouping dimension for analysis. Pick ONE of:
   - currency (group by the currency in the amount field)
   - sender_bank (group by sender BIC)
   - receiver_bank (group by receiver BIC)
   - message_type (group by MT103 / MT202)
   - risk_tier (group by fraud_status or fraud_score)
   Choose whichever dimension produces the most useful analytical grouping
   for this particular batch.
3. Partition every message_id into exactly one group.
4. Create one summary_report task per group.

Return JSON only."""

            user_prompt = f"""Analyze these SWIFT messages and propose a grouping plan:

{json.dumps(messages, indent=2, default=str)}

Return JSON with this exact structure:
{{
    "analysis": "Brief analysis of the message batch",
    "group_by": "the dimension you chose (e.g. currency, sender_bank, message_type, risk_tier)",
    "groups": [
        {{
            "group_key": "the group value (e.g. USD, MT103, CLEAN)",
            "message_ids": ["list", "of", "message_ids", "in", "this", "group"]
        }}
    ],
    "tasks": [
        {{
            "task_id": "group_report_001",
            "type": "summary_report",
            "group_key": "the group value this task covers",
            "description": "Produce a compliance and risk summary report for this group",
            "message_ids": ["same", "message_ids", "as", "the", "group"]
        }}
    ]
}}

Every message_id must appear in exactly one group. Create one task per group."""

            try:
                response = self.llm_service.call_with_retry(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1
                )
                return json.loads(response.choices[0].message.content or "{}")
            except Exception as e:
                print(f"Orchestrator error: {e}")
                return {}

    class GenericAgent:
        """
        Worker agent that produces a structured report for a group of
        messages assigned by the orchestrator.
        """

        def __init__(self, llm_service: LLMService):
            """Initialize the Generic Agent."""
            self.llm_service = llm_service
            self.model = llm_service.model

        def execute_task(self, task: Dict, group_messages: List[Dict]) -> Dict:
            """
            Produce a report for a group of messages.

            Args:
                task: Task dictionary from the orchestrator
                group_messages: The actual message dicts belonging to this group

            Returns:
                Dictionary with the group report
            """
            group_key = task.get('group_key', 'unknown')
            description = task.get('description', '')

            system_prompt = """You are a SWIFT Transaction Report Generator.
Produce a structured compliance and risk summary report for the assigned
group of transactions. Be specific about amounts, parties, and risk factors.
Return JSON only."""

            user_prompt = f"""Generate a report for this group of transactions.

Group Key: {group_key}
Task: {description}

Transactions in this group:
{json.dumps(group_messages, indent=2, default=str)}

Return JSON with this structure:
{{
    "group_key": "{group_key}",
    "transaction_count": number,
    "total_amount": "sum with currency",
    "risk_summary": "overall risk assessment for this group",
    "key_findings": ["list of notable findings"],
    "compliance_status": "PASS or REVIEW_NEEDED",
    "recommendations": ["list of recommendations"]
}}"""

            try:
                response = self.llm_service.call_with_retry(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1
                )
                results = json.loads(response.choices[0].message.content or "{}")
            except Exception as e:
                print(f"GenericAgent error on task {task.get('task_id')}: {e}")
                results = {"error": str(e)}

            return {
                "task_id": task.get('task_id'),
                "group_key": group_key,
                "status": "completed",
                "results": results
            }

    def process_with_orchestrator(self, messages: List[Dict]) -> Dict:
        """
        Process messages using the orchestrator-worker pattern.

        1. Orchestrator proposes a grouping plan
        2. Messages are partitioned into groups
        3. A worker produces a report for each group

        Args:
            messages: List of SWIFT messages to process

        Returns:
            Processing results with grouping plan and per-group reports
        """
        print("=" * 60)
        print("ORCHESTRATOR-WORKER PATTERN PROCESSING")
        print("=" * 60)

        # Step 1: Orchestrator proposes grouping plan
        orchestrator = self.Orchestrator(self.llm_service)
        print("Orchestrator analyzing messages and proposing grouping plan...")
        orchestrator_response = orchestrator.analyze_and_create_tasks(messages)

        group_by = orchestrator_response.get('group_by', 'unknown')
        groups = orchestrator_response.get('groups', [])
        tasks = orchestrator_response.get('tasks', [])

        print(f"Orchestrator Analysis: {orchestrator_response.get('analysis', 'No analysis')}")
        print(f"Grouping dimension: {group_by}")
        print(f"Groups created: {len(groups)}")
        for g in groups:
            print(f"  - {g.get('group_key')}: {len(g.get('message_ids', []))} message(s)")
        print(f"Tasks created: {len(tasks)}")

        # Build a lookup from message_id to message dict
        msg_lookup = {m.get('message_id'): m for m in messages}

        # Step 2: Worker produces a report per group
        agent = self.GenericAgent(self.llm_service)
        results = []

        for task in tasks:
            group_key = task.get('group_key', 'unknown')
            task_msg_ids = task.get('message_ids', [])
            group_messages = [msg_lookup[mid] for mid in task_msg_ids if mid in msg_lookup]

            print(f"Worker reporting on group '{group_key}' ({len(group_messages)} messages)...")
            result = agent.execute_task(task, group_messages)
            results.append(result)
            print(f"  Group '{group_key}' report completed")

        # Summary
        print(f"\nOrchestrator-Worker Summary: {len(results)} group reports produced "
              f"(grouped by {group_by})")

        return {
            'orchestrator_analysis': orchestrator_response,
            'group_by': group_by,
            'groups': groups,
            'task_results': results,
            'summary': f"Produced {len(results)} group reports for {len(messages)} messages (grouped by {group_by})"
        }

    def test_orchestrator(self):
        """Test method for the orchestrator-worker pattern."""
        test_messages = [
            {
                'message_id': 'MSG001',
                'message_type': 'MT103',
                'amount': '75000.00 USD',
                'sender_bic': 'CHASUS33XXX',
                'receiver_bic': 'DEUTDEFFXXX',
                'reference': 'TRX20240101001',
                'remittance_info': 'Payment for equipment purchase',
                'fraud_status': 'CLEAN'
            },
            {
                'message_id': 'MSG002',
                'message_type': 'MT202',
                'amount': '1000000.00 EUR',
                'sender_bic': 'BNPAFRPPXXX',
                'receiver_bic': 'BARCGB22XXX',
                'reference': 'COV20240101002',
                'remittance_info': 'Cover payment',
                'fraud_status': 'CLEAN'
            },
            {
                'message_id': 'MSG003',
                'message_type': 'MT103',
                'amount': '25000.00 USD',
                'sender_bic': 'CHASUS33XXX',
                'receiver_bic': 'BARCGB22XXX',
                'reference': 'TRX20240101003',
                'remittance_info': 'Supplier payment',
                'fraud_status': 'FRAUDULENT'
            }
        ]

        print("Testing Orchestrator-Worker Pattern\n")
        results = self.process_with_orchestrator(test_messages)

        print("\n" + "=" * 60)
        print("TEST RESULTS SUMMARY")
        print("=" * 60)

        if results:
            print(f"Group by: {results.get('group_by')}")
            print(f"Groups: {len(results.get('groups', []))}")
            for r in results.get('task_results', []):
                print(f"\n  Group '{r.get('group_key')}':")
                report = r.get('results', {})
                print(f"    Transactions: {report.get('transaction_count')}")
                print(f"    Risk: {report.get('risk_summary', 'N/A')}")
                print(f"    Compliance: {report.get('compliance_status', 'N/A')}")

        return results


if __name__ == "__main__":
    pattern = OrchestratorWorkerPattern()
    pattern.test_orchestrator()
