from unittest.mock import MagicMock

from engine.orchestrator.loop_guard import LoopGuard


def _make_ctx(state_history=None, seen_tool_calls=None):
    ctx = MagicMock()
    ctx.state_history = state_history or []
    ctx.seen_tool_calls = seen_tool_calls or set()
    return ctx


def test_no_duplicate_on_first_call():
    guard = LoopGuard()
    ctx = _make_ctx()
    assert not guard.is_duplicate_tool_call(ctx, "tool_a", {"x": 1})


def test_duplicate_detected_after_register():
    guard = LoopGuard()
    ctx = _make_ctx()
    guard.register_tool_call(ctx, "tool_a", {"x": 1})
    assert guard.is_duplicate_tool_call(ctx, "tool_a", {"x": 1})


def test_different_input_not_duplicate():
    guard = LoopGuard()
    ctx = _make_ctx()
    guard.register_tool_call(ctx, "tool_a", {"x": 1})
    assert not guard.is_duplicate_tool_call(ctx, "tool_a", {"x": 2})


def test_no_loop_with_short_history():
    guard = LoopGuard()
    ctx = _make_ctx(["A", "B", "C"])
    assert not guard.check_state_loop(ctx)


def test_loop_detected_with_repeating_sequence():
    guard = LoopGuard()
    # Pattern "A B" repeating 3 times
    ctx = _make_ctx(["A", "B", "A", "B", "A", "B"])
    assert guard.check_state_loop(ctx)


def test_no_false_positive_with_varied_history():
    guard = LoopGuard()
    ctx = _make_ctx(["A", "B", "C", "D", "E", "F", "G"])
    assert not guard.check_state_loop(ctx)


def test_single_state_repeated_three_times():
    guard = LoopGuard()
    ctx = _make_ctx(["A", "A", "A"])
    assert guard.check_state_loop(ctx)
