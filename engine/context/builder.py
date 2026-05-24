from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.models import RunContext


class ContextBuilder:
    """
    Assembles the message list sent to the LLM.

    Phase 1: seeds message list from the user's raw input.
    Phase 2: also injects prior session history and restores working memory context.
             User facts are injected into the system prompt via build_system_prompt().
    """

    def initialise(self, ctx: RunContext) -> None:
        """
        Called once at BUILD_CONTEXT on step 0 to seed the message list.
        If session memory was loaded (Phase 2), ctx.messages is already populated
        with prior history — we append the new user turn on top of that.
        """
        if ctx.messages:
            # Session history was loaded by LOAD_MEMORY; new user turn is already
            # appended there. Nothing more to do.
            return
        # First run or no prior history: seed with just the user's input.
        ctx.messages = [{"role": "user", "content": ctx.run.input}]

    def build_system_prompt(self, ctx: RunContext) -> str:
        """
        Returns the effective system prompt for the current run.
        If user facts exist (loaded from user memory), they are appended
        so the LLM knows persistent context about the user.
        """
        base = ctx.run.system_prompt
        if not ctx.user_facts:
            return base
        facts_block = "\n".join(f"- {f}" for f in ctx.user_facts)
        return (
            f"{base}\n\n"
            f"--- Persistent context about this user ---\n"
            f"{facts_block}"
        )
