from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.models import RunContext


class LoopGuard:
    """
    Two guards:
    1. Duplicate tool call detection — same tool + same inputs called twice.
    2. State loop detection — same sequence of states repeating 3 times.
    """

    def is_duplicate_tool_call(self, ctx: RunContext, tool_name: str, tool_input: dict) -> bool:
        key = _tool_key(tool_name, tool_input)
        return key in ctx.seen_tool_calls

    def register_tool_call(self, ctx: RunContext, tool_name: str, tool_input: dict) -> None:
        key = _tool_key(tool_name, tool_input)
        ctx.seen_tool_calls.add(key)

    def check_state_loop(self, ctx: RunContext) -> bool:
        """
        Returns True if the last N states form a repeating cycle of length 1–5,
        repeated at least 3 times.
        """
        history = ctx.state_history
        if len(history) < 3:
            return False

        for seq_len in range(1, 6):
            tail = history[-(seq_len * 3):]
            if len(tail) < seq_len * 3:
                continue
            chunk_a = tail[:seq_len]
            chunk_b = tail[seq_len : seq_len * 2]
            chunk_c = tail[seq_len * 2 :]
            if chunk_a == chunk_b == chunk_c:
                return True
        return False


def _tool_key(tool_name: str, tool_input: dict) -> str:
    payload = json.dumps({"tool": tool_name, "input": tool_input}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()
