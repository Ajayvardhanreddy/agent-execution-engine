"""
Latency Scorer — was the run fast enough?

Score:
  1.0   latency <= threshold
  linear decay from 1.0 → 0.0 between threshold and 2x threshold
  0.0   latency > 2x threshold
"""
from __future__ import annotations

from engine.evals.base import EvalCase, ScoreDetail, Scorer
from engine.models import AgentRunResult


class LatencyScorer(Scorer):
    name = "latency"
    weight = 0.5        # lower weight — latency matters but less than correctness

    def score(
        self,
        case: EvalCase,
        result: AgentRunResult,
        tools_called: list[str],
    ) -> ScoreDetail:
        latency = result.latency_ms
        threshold = case.max_latency_ms

        if latency <= threshold:
            return self._detail(
                1.0,
                f"Latency {latency}ms within threshold {threshold}ms.",
            )

        double = 2 * threshold
        if latency >= double:
            return self._detail(
                0.0,
                f"Latency {latency}ms exceeds 2x threshold ({double}ms).",
            )

        # Linear decay between threshold and 2x threshold
        score = 1.0 - (latency - threshold) / threshold
        return self._detail(
            score,
            f"Latency {latency}ms exceeds threshold {threshold}ms "
            f"(within 2x — {score:.0%} score).",
        )
