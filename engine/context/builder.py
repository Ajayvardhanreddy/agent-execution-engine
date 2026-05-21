from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.models import RunContext


class ContextBuilder:
    """
    Assembles the message list that gets sent to the LLM.

    Phase 1: messages are built incrementally in RunContext.messages.
    This builder's job is to initialise the list on the first call and
    apply the compressor when near the token limit.
    Phase 2: will inject session + user memory here.
    """

    def initialise(self, ctx: RunContext) -> None:
        """Called once at BUILD_CONTEXT on step 0 to seed the message list."""
        if ctx.messages:
            return  # already seeded on a previous turn (shouldn't happen in Phase 1)
        ctx.messages = [{"role": "user", "content": ctx.run.input}]
