"""
EvalSuite — runs all 6 scorers on a single (case, result) pair and
returns a consolidated EvalResult.
"""
from __future__ import annotations

from engine.evals.base import EvalCase, EvalResult, PASS_THRESHOLD, Scorer
from engine.evals.scorers import (
    AnswerQualityScorer,
    CostEfficiencyScorer,
    EscalationAccuracyScorer,
    LatencyScorer,
    TaskCompletionScorer,
    ToolSelectionScorer,
)
from engine.models import AgentRunResult

_DEFAULT_SCORERS: list[Scorer] = [
    TaskCompletionScorer(),
    ToolSelectionScorer(),
    AnswerQualityScorer(),
    CostEfficiencyScorer(),
    LatencyScorer(),
    EscalationAccuracyScorer(),
]


class EvalSuite:
    """
    Applies all scorers to a (case, result) pair.

    Weighted average across all scorers produces the overall score.
    Pass threshold is configurable (default PASS_THRESHOLD = 0.70).
    """

    def __init__(
        self,
        scorers: list[Scorer] | None = None,
        pass_threshold: float = PASS_THRESHOLD,
    ) -> None:
        self._scorers = scorers or _DEFAULT_SCORERS
        self._pass_threshold = pass_threshold

    def evaluate(
        self,
        case: EvalCase,
        result: AgentRunResult,
        tools_called: list[str],
        error: str | None = None,
    ) -> EvalResult:
        if error:
            # Run crashed before producing a result
            return EvalResult(
                case=case,
                run_result=result,
                tools_called=[],
                scores=[],
                overall_score=0.0,
                passed=False,
                error=error,
            )

        score_details = [
            scorer.score(case, result, tools_called)
            for scorer in self._scorers
        ]

        # Weighted average
        total_weight = sum(s.weight for s in self._scorers)
        overall = sum(
            detail.score * scorer.weight
            for detail, scorer in zip(score_details, self._scorers)
        ) / total_weight

        # Hard-fail check: any hard_fail scorer with score 0.0 overrides pass/fail
        hard_failed = any(
            detail.score == 0.0 and scorer.hard_fail
            for detail, scorer in zip(score_details, self._scorers)
        )
        passed = (overall >= self._pass_threshold) and not hard_failed

        return EvalResult(
            case=case,
            run_result=result,
            tools_called=tools_called,
            scores=score_details,
            overall_score=round(overall, 3),
            passed=passed,
        )
