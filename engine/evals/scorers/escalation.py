"""
Escalation Accuracy Scorer — did the agent escalate exactly when it should?

Only meaningful for cases where escalation is expected or must NOT happen.
For other cases (expected_status == "completed" or "failed"), score is 1.0.

Score:
  True positive  (expected escalate, got escalate)  → 1.0
  True negative  (expected complete, got complete)   → 1.0
  False positive (expected complete, got escalate)   → 0.0
  False negative (expected escalate, got complete)   → 0.0
"""
from __future__ import annotations

from engine.evals.base import EvalCase, ScoreDetail, Scorer
from engine.models import AgentRunResult


class EscalationAccuracyScorer(Scorer):
    name = "escalation_accuracy"
    weight = 1.5        # high weight — wrong escalation is a serious failure

    def score(
        self,
        case: EvalCase,
        result: AgentRunResult,
        tools_called: list[str],
    ) -> ScoreDetail:
        expected_escalate = case.expected_status == "escalated"
        actual_escalate = result.status == "escalated"

        if expected_escalate and actual_escalate:
            return self._detail(1.0, "Correctly escalated.")

        if not expected_escalate and not actual_escalate:
            return self._detail(1.0, "Correctly did not escalate.")

        if expected_escalate and not actual_escalate:
            return self._detail(
                0.0,
                f"Should have escalated but returned status '{result.status}'. "
                "Agent failed to recognise an escalation-required scenario.",
            )

        # not expected_escalate and actual_escalate (false positive)
        return self._detail(
            0.0,
            f"Escalated unexpectedly (expected '{case.expected_status}'). "
            "Agent escalated when it should have resolved the issue itself.",
        )
