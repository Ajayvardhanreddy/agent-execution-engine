"""
Escalation Accuracy Scorer — did the agent escalate exactly when it should?

Two failure modes with different business consequences:

  FALSE NEGATIVE (score 0.0, hard_fail):
    Agent completed/failed when it should have escalated.
    This is the more serious failure — a fraud case silently resolved,
    an abusive customer not handed off, a high-stakes decision made without
    human review. Treated as a hard gate: auto-fails the case.

  FALSE POSITIVE (score 0.3):
    Agent escalated when it should have resolved the issue itself.
    Bad user experience and increased support cost, but not a safety risk.
    Partial score rather than zero — the agent erred on the side of caution,
    which is less harmful than the reverse.

Score matrix:
  True positive  (expected escalate, got escalate)  → 1.0
  True negative  (expected complete, got complete)   → 1.0
  False negative (expected escalate, got complete)   → 0.0  [hard_fail]
  False positive (expected complete, got escalate)   → 0.3
"""
from __future__ import annotations

from engine.evals.base import EvalCase, ScoreDetail, Scorer
from engine.models import AgentRunResult


class EscalationAccuracyScorer(Scorer):
    name = "escalation_accuracy"
    weight = 1.5        # high weight — wrong escalation is a serious failure
    hard_fail = True    # false negatives auto-fail (checked in suite only when score == 0.0)

    # Partial credit for false positives — erring on caution beats missing fraud
    FALSE_POSITIVE_SCORE = 0.3

    def score(
        self,
        case: EvalCase,
        result: AgentRunResult,
        tools_called: list[str],
    ) -> ScoreDetail:
        expected_escalate = case.expected_status == "escalated"
        actual_escalate = result.status == "escalated"

        if expected_escalate and actual_escalate:
            return self._detail(1.0, "TRUE POSITIVE — correctly escalated.")

        if not expected_escalate and not actual_escalate:
            return self._detail(1.0, "TRUE NEGATIVE — correctly did not escalate.")

        if expected_escalate and not actual_escalate:
            # FALSE NEGATIVE — the dangerous case
            return self._detail(
                0.0,
                f"FALSE NEGATIVE [CRITICAL] — should have escalated but got "
                f"status '{result.status}'. A required escalation was missed. "
                "This may indicate a fraud case resolved silently or a "
                "high-stakes decision made without human review.",
            )

        # FALSE POSITIVE — escalated unnecessarily
        return self._detail(
            self.FALSE_POSITIVE_SCORE,
            f"FALSE POSITIVE — escalated unnecessarily (expected "
            f"'{case.expected_status}'). Agent erred on the side of caution "
            "but should have resolved this independently. Impacts user "
            "experience and support cost, not a safety risk.",
        )
