"""
Unit tests for all 6 eval scorers.

No LLM calls — scorers operate on pre-built EvalCase + AgentRunResult.
"""
from __future__ import annotations

import pytest

from engine.evals.base import EvalCase
from engine.evals.scorers import (
    AnswerQualityScorer,
    CostEfficiencyScorer,
    EscalationAccuracyScorer,
    LatencyScorer,
    TaskCompletionScorer,
    ToolSelectionScorer,
)
from engine.evals.suite import EvalSuite
from engine.models import AgentRunResult


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _case(
    expected_status: str = "completed",
    expected_tools: list[str] | None = None,
    unexpected_tools: list[str] | None = None,
    must_contain: list[str] | None = None,
    must_not_contain: list[str] | None = None,
    max_cost: float = 0.10,
    max_latency: int = 30_000,
) -> EvalCase:
    return EvalCase(
        case_id="test_001",
        description="test case",
        agent_id="test_agent",
        input="test input",
        expected_status=expected_status,
        expected_tools_called=expected_tools or [],
        unexpected_tools_called=unexpected_tools or [],
        answer_must_contain=must_contain or [],
        answer_must_not_contain=must_not_contain or [],
        max_cost_usd=max_cost,
        max_latency_ms=max_latency,
    )


def _result(
    status: str = "completed",
    answer: str = "Your order has been refunded.",
    cost: float = 0.02,
    latency: int = 5_000,
    steps: int = 3,
) -> AgentRunResult:
    return AgentRunResult(
        run_id="run_test",
        status=status,
        final_answer=answer,
        trace_id="trace_test",
        steps_taken=steps,
        total_tokens_used=500,
        total_cost_usd=cost,
        latency_ms=latency,
    )


# ── TaskCompletionScorer ──────────────────────────────────────────────────────

class TestTaskCompletion:
    scorer = TaskCompletionScorer()

    def test_exact_match_scores_1(self):
        s = self.scorer.score(_case("completed"), _result("completed"), [])
        assert s.score == 1.0
        assert s.passed

    def test_mismatch_scores_0(self):
        s = self.scorer.score(_case("completed"), _result("failed"), [])
        assert s.score == 0.0
        assert not s.passed

    def test_escalated_match(self):
        s = self.scorer.score(_case("escalated"), _result("escalated"), [])
        assert s.score == 1.0

    def test_escalated_mismatch(self):
        s = self.scorer.score(_case("escalated"), _result("completed"), [])
        assert s.score == 0.0


# ── ToolSelectionScorer ───────────────────────────────────────────────────────

class TestToolSelection:
    scorer = ToolSelectionScorer()

    def test_no_constraints_scores_1(self):
        s = self.scorer.score(_case(), _result(), ["order_lookup"])
        assert s.score == 1.0

    def test_all_expected_tools_called(self):
        s = self.scorer.score(
            _case(expected_tools=["order_lookup", "refund_request"]),
            _result(),
            ["order_lookup", "refund_request"],
        )
        assert s.score == 1.0
        assert s.passed

    def test_missing_one_expected_tool(self):
        s = self.scorer.score(
            _case(expected_tools=["order_lookup", "refund_request"]),
            _result(),
            ["order_lookup"],  # refund_request missing
        )
        assert s.score == pytest.approx(1.0 - 0.25)

    def test_all_expected_missing(self):
        s = self.scorer.score(
            _case(expected_tools=["order_lookup", "refund_request"]),
            _result(),
            [],
        )
        assert s.score == pytest.approx(max(0.0, 1.0 - 0.25 - 0.25))

    def test_unexpected_tool_called_penalised(self):
        s = self.scorer.score(
            _case(unexpected_tools=["escalate_to_human"]),
            _result(),
            ["order_lookup", "escalate_to_human"],
        )
        assert s.score == pytest.approx(1.0 - 0.20)

    def test_score_floored_at_zero(self):
        s = self.scorer.score(
            _case(expected_tools=["a", "b", "c", "d", "e"]),
            _result(),
            [],
        )
        assert s.score == 0.0


# ── AnswerQualityScorer ───────────────────────────────────────────────────────

class TestAnswerQuality:
    scorer = AnswerQualityScorer()

    def test_no_constraints_scores_1(self):
        s = self.scorer.score(_case(), _result(answer="anything"), [])
        assert s.score == 1.0

    def test_all_keywords_present(self):
        s = self.scorer.score(
            _case(must_contain=["refund", "order"]),
            _result(answer="Your refund for the order has been approved."),
            [],
        )
        assert s.score == 1.0

    def test_missing_keyword_reduces_score(self):
        s = self.scorer.score(
            _case(must_contain=["refund", "invoice"]),
            _result(answer="Your refund has been approved."),
            [],
        )
        assert s.score == pytest.approx(0.5)

    def test_forbidden_term_penalises(self):
        s = self.scorer.score(
            _case(must_not_contain=["cannot process"]),
            _result(answer="We cannot process your refund."),
            [],
        )
        assert s.score < 1.0

    def test_no_answer_for_completed_scores_0(self):
        s = self.scorer.score(
            _case(expected_status="completed"),
            _result(status="completed", answer=""),
            [],
        )
        assert s.score == 0.0

    def test_no_answer_for_escalated_scores_1(self):
        s = self.scorer.score(
            _case(expected_status="escalated"),
            _result(status="escalated", answer=""),
            [],
        )
        assert s.score == 1.0

    def test_case_insensitive_matching(self):
        s = self.scorer.score(
            _case(must_contain=["REFUND"]),
            _result(answer="your refund is approved"),
            [],
        )
        assert s.score == 1.0


# ── CostEfficiencyScorer ──────────────────────────────────────────────────────

class TestCostEfficiency:
    scorer = CostEfficiencyScorer()

    def test_within_threshold_scores_1(self):
        s = self.scorer.score(_case(max_cost=0.10), _result(cost=0.05), [])
        assert s.score == 1.0

    def test_at_threshold_scores_1(self):
        s = self.scorer.score(_case(max_cost=0.10), _result(cost=0.10), [])
        assert s.score == 1.0

    def test_over_threshold_within_2x_scores_half(self):
        s = self.scorer.score(_case(max_cost=0.10), _result(cost=0.15), [])
        assert s.score == 0.5

    def test_over_2x_threshold_scores_0(self):
        s = self.scorer.score(_case(max_cost=0.10), _result(cost=0.25), [])
        assert s.score == 0.0


# ── LatencyScorer ─────────────────────────────────────────────────────────────

class TestLatency:
    scorer = LatencyScorer()

    def test_within_threshold_scores_1(self):
        s = self.scorer.score(_case(max_latency=30_000), _result(latency=10_000), [])
        assert s.score == 1.0

    def test_at_threshold_scores_1(self):
        s = self.scorer.score(_case(max_latency=30_000), _result(latency=30_000), [])
        assert s.score == 1.0

    def test_over_2x_threshold_scores_0(self):
        s = self.scorer.score(_case(max_latency=30_000), _result(latency=61_000), [])
        assert s.score == 0.0

    def test_midpoint_scores_half(self):
        # At 1.5x threshold, score should be 0.5
        s = self.scorer.score(_case(max_latency=30_000), _result(latency=45_000), [])
        assert s.score == pytest.approx(0.5)


# ── EscalationAccuracyScorer ──────────────────────────────────────────────────

class TestEscalationAccuracy:
    scorer = EscalationAccuracyScorer()

    def test_true_positive(self):
        s = self.scorer.score(_case("escalated"), _result("escalated"), [])
        assert s.score == 1.0

    def test_true_negative(self):
        s = self.scorer.score(_case("completed"), _result("completed"), [])
        assert s.score == 1.0

    def test_false_negative_scores_0(self):
        # Should have escalated but didn't
        s = self.scorer.score(_case("escalated"), _result("completed"), [])
        assert s.score == 0.0

    def test_false_positive_scores_partial(self):
        # Should NOT have escalated but did — partial credit, not zero
        # Erring on caution is less harmful than missing a required escalation
        s = self.scorer.score(_case("completed"), _result("escalated"), [])
        assert s.score == pytest.approx(0.3)
        assert not s.passed
        assert "FALSE POSITIVE" in s.reason

    def test_false_negative_scores_0_and_critical(self):
        # Should have escalated but didn't — the dangerous case
        s = self.scorer.score(_case("escalated"), _result("completed"), [])
        assert s.score == 0.0
        assert "FALSE NEGATIVE" in s.reason
        assert "CRITICAL" in s.reason

    def test_false_negative_auto_fails_via_suite(self):
        # False negative has hard_fail=True — suite must auto-fail even if
        # other scorers are perfect
        suite = EvalSuite()
        case = _case(
            expected_status="escalated",
            max_cost=0.10,
            max_latency=30_000,
        )
        result = _result(status="completed", cost=0.01, latency=1_000)
        eval_result = suite.evaluate(case, result, [])
        assert not eval_result.passed
        assert eval_result.scores[0].score == 0.0  # task_completion
        assert any(s.scorer == "escalation_accuracy" and s.score == 0.0 for s in eval_result.scores)


# ── EvalSuite ─────────────────────────────────────────────────────────────────

class TestEvalSuite:
    suite = EvalSuite()

    def test_perfect_run_passes(self):
        case = _case(
            expected_status="completed",
            expected_tools=["order_lookup"],
            must_contain=["refund"],
        )
        result = _result(
            status="completed",
            answer="Your refund has been approved.",
            cost=0.02,
            latency=5_000,
        )
        eval_result = self.suite.evaluate(case, result, ["order_lookup"])
        assert eval_result.passed
        assert eval_result.overall_score >= 0.90

    def test_wrong_status_fails(self):
        case = _case(expected_status="completed")
        result = _result(status="failed")
        eval_result = self.suite.evaluate(case, result, [])
        assert not eval_result.passed

    def test_crashed_run_fails(self):
        case = _case()
        result = _result()
        eval_result = self.suite.evaluate(case, result, [], error="Engine exploded")
        assert not eval_result.passed
        assert eval_result.overall_score == 0.0
        assert eval_result.error == "Engine exploded"

    def test_overall_score_is_weighted_average(self):
        """Overall score must be between 0 and 1."""
        case = _case()
        result = _result()
        eval_result = self.suite.evaluate(case, result, [])
        assert 0.0 <= eval_result.overall_score <= 1.0
