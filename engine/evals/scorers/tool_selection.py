"""
Tool Selection Scorer — did the agent call the right tools?

Score:
  Starts at 1.0.
  Deducts for each expected tool NOT called (missing).
  Deducts for each unexpected tool that WAS called (wrong).

  missing_penalty  = 0.25 per tool
  wrong_penalty    = 0.20 per tool
  Floor at 0.0.

  If no expected or unexpected tools are specified, score is 1.0 (unconstrained).
"""
from __future__ import annotations

from engine.evals.base import EvalCase, ScoreDetail, Scorer
from engine.models import AgentRunResult


class ToolSelectionScorer(Scorer):
    name = "tool_selection"
    weight = 1.5

    MISSING_PENALTY = 0.25
    WRONG_PENALTY = 0.20

    def score(
        self,
        case: EvalCase,
        result: AgentRunResult,
        tools_called: list[str],
    ) -> ScoreDetail:
        if not case.expected_tools_called and not case.unexpected_tools_called:
            return self._detail(1.0, "No tool constraints specified — unconstrained.")

        called_set = set(tools_called)
        reasons: list[str] = []
        penalty = 0.0

        # Missing expected tools
        for tool in case.expected_tools_called:
            if tool not in called_set:
                penalty += self.MISSING_PENALTY
                reasons.append(f"missing: '{tool}'")

        # Unexpected tools called
        for tool in case.unexpected_tools_called:
            if tool in called_set:
                penalty += self.WRONG_PENALTY
                reasons.append(f"unexpected: '{tool}'")

        score = max(0.0, 1.0 - penalty)
        reason = (
            f"Tools called: {sorted(called_set)}. "
            + ("; ".join(reasons) if reasons else "All constraints met.")
        )
        return self._detail(score, reason)
