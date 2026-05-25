"""
Cost Efficiency Scorer — did the agent stay within its cost budget?

Score:
  1.0   cost <= threshold
  0.5   threshold < cost <= 2x threshold   (over budget but not catastrophic)
  0.0   cost > 2x threshold
"""
from __future__ import annotations

from engine.evals.base import EvalCase, ScoreDetail, Scorer
from engine.models import AgentRunResult


class CostEfficiencyScorer(Scorer):
    name = "cost_efficiency"
    weight = 1.0

    def score(
        self,
        case: EvalCase,
        result: AgentRunResult,
        tools_called: list[str],
    ) -> ScoreDetail:
        cost = result.total_cost_usd
        threshold = case.max_cost_usd

        if cost <= threshold:
            return self._detail(
                1.0,
                f"Cost ${cost:.4f} within threshold ${threshold:.4f}.",
            )
        if cost <= 2 * threshold:
            return self._detail(
                0.5,
                f"Cost ${cost:.4f} exceeds threshold ${threshold:.4f} "
                f"(within 2x — acceptable but high).",
            )
        return self._detail(
            0.0,
            f"Cost ${cost:.4f} exceeds 2x threshold (${2 * threshold:.4f}). "
            f"Agent is too expensive for this case.",
        )
