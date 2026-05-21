from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.models import RunContext


# Rough chars-to-tokens ratio for truncation heuristic
_CHARS_PER_TOKEN = 4


def _estimate_tokens(messages: list[dict]) -> int:
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total += len(content) // _CHARS_PER_TOKEN
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    total += len(str(block)) // _CHARS_PER_TOKEN
    return total


class ContextCompressor:
    """
    Trims the oldest non-system messages when the conversation approaches the
    token budget threshold. Always preserves:
      - The very first user message (original task)
      - The most recent 6 messages (enough for current tool-use round-trip)
    """

    def compress(self, ctx: RunContext) -> None:
        messages = ctx.messages
        if len(messages) <= 6:
            return

        target_tokens = int(ctx.budget_tracker.max_tokens * 0.7)
        current_estimate = _estimate_tokens(messages)
        if current_estimate <= target_tokens:
            return

        # Keep first and last 6; trim from the middle
        head = messages[:1]          # original user message
        tail = messages[-6:]         # recent context
        middle = messages[1:-6]

        while middle and _estimate_tokens(head + middle + tail) > target_tokens:
            middle.pop(0)

        ctx.messages = head + middle + tail
