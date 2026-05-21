from unittest.mock import MagicMock

from engine.context.builder import ContextBuilder
from engine.context.compressor import ContextCompressor


def _make_ctx(messages=None, max_tokens=10000, tokens_used=0):
    ctx = MagicMock()
    ctx.messages = messages if messages is not None else []
    ctx.run.input = "Hello, I need help."
    ctx.budget_tracker.max_tokens = max_tokens
    ctx.budget_tracker.tokens_used = tokens_used
    ctx.budget_tracker.near_token_limit.return_value = tokens_used >= max_tokens * 0.8
    return ctx


def test_initialise_seeds_messages():
    builder = ContextBuilder()
    ctx = _make_ctx()
    builder.initialise(ctx)
    assert len(ctx.messages) == 1
    assert ctx.messages[0] == {"role": "user", "content": "Hello, I need help."}


def test_initialise_does_not_overwrite_existing_messages():
    builder = ContextBuilder()
    existing = [{"role": "user", "content": "old message"}]
    ctx = _make_ctx(messages=existing)
    builder.initialise(ctx)
    # Should not change existing messages
    assert ctx.messages[0]["content"] == "old message"


def test_compressor_preserves_head_and_tail():
    compressor = ContextCompressor()
    # Create a ctx with many messages that exceed target token budget
    messages = [{"role": "user", "content": "x" * 500} for _ in range(20)]
    ctx = _make_ctx(messages=messages, max_tokens=1000, tokens_used=900)
    ctx.messages = messages  # direct assignment
    original_first = messages[0]
    compressor.compress(ctx)
    # First message preserved
    assert ctx.messages[0] is original_first
    # List got shorter
    assert len(ctx.messages) < 20


def test_compressor_skips_short_history():
    compressor = ContextCompressor()
    messages = [{"role": "user", "content": "short"}] * 4
    ctx = _make_ctx(messages=list(messages))
    ctx.messages = list(messages)
    compressor.compress(ctx)
    assert len(ctx.messages) == 4  # unchanged
