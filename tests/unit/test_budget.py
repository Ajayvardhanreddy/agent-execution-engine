import time

from engine.context.budget import BudgetTracker


def test_initial_state():
    bt = BudgetTracker(max_steps=10, max_tokens=1000, max_cost_usd=1.0, timeout_seconds=30)
    assert bt.steps_taken == 0
    assert bt.tokens_used == 0
    assert bt.cost_usd == 0.0


def test_increment_step():
    bt = BudgetTracker()
    bt.increment_step()
    bt.increment_step()
    assert bt.steps_taken == 2


def test_add_tokens_and_cost():
    bt = BudgetTracker()
    bt.add_tokens(100, 50, "claude-haiku-4-5-20251001")
    assert bt.tokens_used == 150
    assert bt.cost_usd > 0.0


def test_near_token_limit():
    bt = BudgetTracker(max_tokens=1000)
    bt.add_tokens(799, 0, "claude-haiku-4-5-20251001")
    assert not bt.near_token_limit(0.8)
    bt.add_tokens(1, 0, "claude-haiku-4-5-20251001")
    assert bt.near_token_limit(0.8)  # 800/1000 = 0.8


def test_steps_exceeded():
    bt = BudgetTracker(max_steps=3)
    for _ in range(3):
        bt.increment_step()
    exceeded, reason = bt.is_exceeded()
    assert exceeded
    assert "max_steps" in reason


def test_tokens_exceeded():
    bt = BudgetTracker(max_tokens=100)
    bt.add_tokens(50, 51, "claude-haiku-4-5-20251001")
    exceeded, reason = bt.is_exceeded()
    assert exceeded
    assert "max_tokens" in reason


def test_cost_exceeded():
    bt = BudgetTracker(max_cost_usd=0.001, max_tokens=100_000, max_steps=10_000)
    bt.add_tokens(10000, 0, "claude-haiku-4-5-20251001")
    exceeded, reason = bt.is_exceeded()
    assert exceeded
    assert "max_cost_usd" in reason


def test_remaining_tokens():
    bt = BudgetTracker(max_tokens=1000)
    bt.add_tokens(300, 100, "claude-haiku-4-5-20251001")
    assert bt.remaining_tokens() == 600
