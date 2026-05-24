"""
Eval harness contracts — EvalCase, ScoreDetail, EvalResult, Scorer ABC.

Everything downstream (scorers, runner, report) imports from here.
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from engine.models import AgentRunResult


@dataclass
class EvalCase:
    """One benchmark test case."""
    case_id: str
    description: str
    agent_id: str
    input: str

    # What we expect
    expected_status: str                          # "completed" | "escalated" | "budget_exceeded" | "failed"
    expected_tools_called: list[str] = field(default_factory=list)   # must appear in the run
    unexpected_tools_called: list[str] = field(default_factory=list) # must NOT appear
    answer_must_contain: list[str] = field(default_factory=list)     # case-insensitive substrings
    answer_must_not_contain: list[str] = field(default_factory=list)

    # Thresholds
    max_cost_usd: float = 0.10
    max_latency_ms: int = 60_000

    # Metadata
    tags: list[str] = field(default_factory=list)
    notes: str = ""

    # Set at run time — defaults produce unique IDs per case
    session_id: str = ""
    user_id: str = "eval_user"

    def __post_init__(self) -> None:
        if not self.session_id:
            self.session_id = f"eval_{self.case_id}_{uuid.uuid4().hex[:8]}"


@dataclass
class ScoreDetail:
    """Score from one scorer for one eval case."""
    scorer: str
    score: float        # 0.0 – 1.0
    passed: bool        # score >= scorer's pass threshold
    reason: str         # human-readable explanation


@dataclass
class EvalResult:
    """Full result for one eval case — run output + all scorer scores."""
    case: EvalCase
    run_result: AgentRunResult
    tools_called: list[str]         # extracted from trace spans
    scores: list[ScoreDetail]
    overall_score: float            # weighted average across all scorers
    passed: bool                    # True if overall_score >= PASS_THRESHOLD
    error: str | None = None        # set if the run itself crashed


PASS_THRESHOLD = 0.70               # overall score required to mark a case as passing


# ── Scorer ABC ────────────────────────────────────────────────────────────────

class Scorer(ABC):
    """
    Base class for all eval scorers.

    Each scorer receives the EvalCase (expected behaviour) and the
    AgentRunResult + tools_called (actual behaviour) and returns a
    ScoreDetail with a score in [0, 1] and an explanation.

    hard_fail=True scorers override the overall pass/fail regardless of other
    scorer scores — if a hard_fail scorer scores 0, the case fails even if the
    weighted average is above the threshold.
    """
    name: str
    weight: float = 1.0             # relative weight in overall score calculation
    pass_threshold: float = 0.70    # score >= this → passed
    hard_fail: bool = False         # if True and score == 0.0, case auto-fails

    @abstractmethod
    def score(
        self,
        case: EvalCase,
        result: AgentRunResult,
        tools_called: list[str],
    ) -> ScoreDetail:
        ...

    def _detail(self, score: float, reason: str) -> ScoreDetail:
        return ScoreDetail(
            scorer=self.name,
            score=round(score, 3),
            passed=score >= self.pass_threshold,
            reason=reason,
        )
