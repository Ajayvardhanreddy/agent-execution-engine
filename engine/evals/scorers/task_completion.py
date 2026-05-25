"""
Task Completion Scorer — did the agent finish with the expected status?

Score:
  1.0  status matches expected exactly
  0.0  status does not match
"""
from __future__ import annotations

from engine.evals.base import EvalCase, ScoreDetail, Scorer
from engine.models import AgentRunResult


class TaskCompletionScorer(Scorer):
    name = "task_completion"
    weight = 2.0        # highest weight — correct status is the primary signal
    hard_fail = True    # wrong status auto-fails the case regardless of other scores

    def score(
        self,
        case: EvalCase,
        result: AgentRunResult,
        tools_called: list[str],
    ) -> ScoreDetail:
        if result.status == case.expected_status:
            return self._detail(1.0, f"Status '{result.status}' matches expected.")
        return self._detail(
            0.0,
            f"Expected status '{case.expected_status}', got '{result.status}'. "
            f"Failure reason: {result.failure_reason or 'none'}",
        )
