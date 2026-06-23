"""
Metrics Collector for SWIFT Processing Pipeline

Collects performance, efficiency, and operational metrics during pipeline runs.
Persists metrics to a JSONL file for historical tracking.
"""

import json
import time
import uuid
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Model pricing per 1M tokens (USD) - GPT-4o as of 2024
GPT4O_INPUT_COST_PER_M = 2.50
GPT4O_OUTPUT_COST_PER_M = 10.00


class MetricsCollector:
    """Collects and persists pipeline metrics across a single run."""

    def __init__(self, filepath: str = "audits/metrics.jsonl"):
        self.filepath = filepath
        self.run_id = str(uuid.uuid4())
        self.run_start: Optional[float] = None
        self.run_end: Optional[float] = None

        # Performance: per-step timing
        self._step_timers: Dict[str, float] = {}
        self._step_durations: Dict[str, float] = {}
        self._step_message_counts: Dict[str, int] = {}

        # Efficiency: LLM usage
        self._llm_calls: List[Dict] = []

        # Operations: counts
        self._operational_stats: Dict[str, Any] = {}

        logger.info(f"MetricsCollector initialized. Run ID: {self.run_id}")

    # -- Performance helpers --

    def start_run(self):
        self.run_start = time.time()

    def end_run(self):
        self.run_end = time.time()

    def start_step(self, step_name: str):
        self._step_timers[step_name] = time.time()

    def end_step(self, step_name: str, message_count: int):
        if step_name in self._step_timers:
            duration = time.time() - self._step_timers[step_name]
            self._step_durations[step_name] = duration
            self._step_message_counts[step_name] = message_count
            logger.info(f"[Metrics] {step_name}: {duration:.2f}s for {message_count} messages")

    # -- Efficiency helpers --

    def record_llm_call(self, step: str, prompt_tokens: int, completion_tokens: int,
                        model: str, retries: int = 0):
        self._llm_calls.append({
            "step": step,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "model": model,
            "retries": retries,
            "timestamp": time.time(),
        })

    # -- Operations helpers --

    def record_operational_stats(self, step: str, stats: Dict[str, Any]):
        self._operational_stats[step] = stats

    # -- Aggregation --

    def _aggregate_performance(self) -> Dict:
        total_time = (self.run_end - self.run_start) if self.run_start and self.run_end else 0
        total_messages = max(self._step_message_counts.values(), default=0)
        throughput = total_messages / total_time if total_time > 0 else 0

        steps = {}
        for step, duration in self._step_durations.items():
            count = self._step_message_counts.get(step, 0)
            steps[step] = {
                "duration_seconds": round(duration, 3),
                "message_count": count,
                "throughput_msgs_per_sec": round(count / duration, 3) if duration > 0 else 0,
            }

        return {
            "total_pipeline_time_seconds": round(total_time, 3),
            "total_messages": total_messages,
            "overall_throughput_msgs_per_sec": round(throughput, 3),
            "steps": steps,
        }

    def _aggregate_efficiency(self) -> Dict:
        total_prompt = sum(c["prompt_tokens"] for c in self._llm_calls)
        total_completion = sum(c["completion_tokens"] for c in self._llm_calls)
        total_tokens = total_prompt + total_completion
        total_retries = sum(c["retries"] for c in self._llm_calls)
        total_calls = len(self._llm_calls)

        cost = (total_prompt / 1_000_000 * GPT4O_INPUT_COST_PER_M +
                total_completion / 1_000_000 * GPT4O_OUTPUT_COST_PER_M)

        total_messages = max(self._step_message_counts.values(), default=1)
        cost_per_message = cost / total_messages if total_messages > 0 else 0

        # Per-step breakdown
        step_breakdown: Dict[str, Dict] = {}
        for call in self._llm_calls:
            step = call["step"]
            if step not in step_breakdown:
                step_breakdown[step] = {
                    "llm_calls": 0, "prompt_tokens": 0,
                    "completion_tokens": 0, "retries": 0,
                }
            step_breakdown[step]["llm_calls"] += 1
            step_breakdown[step]["prompt_tokens"] += call["prompt_tokens"]
            step_breakdown[step]["completion_tokens"] += call["completion_tokens"]
            step_breakdown[step]["retries"] += call["retries"]

        return {
            "total_llm_calls": total_calls,
            "total_prompt_tokens": total_prompt,
            "total_completion_tokens": total_completion,
            "total_tokens": total_tokens,
            "total_retries": total_retries,
            "estimated_cost_usd": round(cost, 6),
            "cost_per_message_usd": round(cost_per_message, 6),
            "step_breakdown": step_breakdown,
        }

    def _aggregate_operations(self) -> Dict:
        return self._operational_stats

    def to_dict(self) -> Dict:
        return {
            "run_id": self.run_id,
            "timestamp": datetime.now().isoformat(),
            "performance": self._aggregate_performance(),
            "efficiency": self._aggregate_efficiency(),
            "operations": self._aggregate_operations(),
        }

    def save(self):
        record = self.to_dict()
        with open(self.filepath, "a") as f:
            f.write(json.dumps(record) + "\n")
        logger.info(f"Metrics saved to {self.filepath} (run {self.run_id})")
