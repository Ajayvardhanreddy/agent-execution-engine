"""
Answer Quality Scorer — does the final answer contain what it should?

Score:
  keyword_score   = keywords_found / total_expected_keywords  (if any)
  forbidden_hits  = forbidden keywords found in answer
  forbidden_penalty = 0.30 per forbidden keyword found

  final = max(0.0, keyword_score - forbidden_penalty)

  If no keywords specified, defaults to 1.0 (unless forbidden terms found).
  All matching is case-insensitive.
  If the agent returned no final answer, score is 0.0.
"""
from __future__ import annotations

from engine.evals.base import EvalCase, ScoreDetail, Scorer
from engine.models import AgentRunResult


class AnswerQualityScorer(Scorer):
    name = "answer_quality"
    weight = 1.5
    FORBIDDEN_PENALTY = 0.30

    def score(
        self,
        case: EvalCase,
        result: AgentRunResult,
        tools_called: list[str],
    ) -> ScoreDetail:
        answer = (result.final_answer or "").lower()

        if not answer and case.expected_status == "completed":
            return self._detail(0.0, "No final answer returned for a completed run.")

        if not answer:
            # Escalated/failed runs don't need a text answer
            return self._detail(1.0, "No answer required for non-completed run.")

        reasons: list[str] = []

        # Keyword recall
        if case.answer_must_contain:
            found = [kw for kw in case.answer_must_contain if kw.lower() in answer]
            missing = [kw for kw in case.answer_must_contain if kw.lower() not in answer]
            keyword_score = len(found) / len(case.answer_must_contain)
            if missing:
                reasons.append(f"missing keywords: {missing}")
        else:
            keyword_score = 1.0

        # Forbidden term penalty
        forbidden_hits = [kw for kw in case.answer_must_not_contain if kw.lower() in answer]
        forbidden_penalty = len(forbidden_hits) * self.FORBIDDEN_PENALTY
        if forbidden_hits:
            reasons.append(f"forbidden terms found: {forbidden_hits}")

        score = max(0.0, keyword_score - forbidden_penalty)
        if not reasons:
            reasons.append(f"All {len(case.answer_must_contain)} keyword(s) found, no forbidden terms.")

        return self._detail(score, " | ".join(reasons))
