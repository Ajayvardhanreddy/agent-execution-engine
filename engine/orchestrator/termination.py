from __future__ import annotations

from typing import TYPE_CHECKING

from engine.orchestrator.loop_guard import LoopGuard
from engine.orchestrator.state_machine import AgentState

if TYPE_CHECKING:
    from engine.models import RunContext


class TerminationChecker:
    def __init__(self) -> None:
        self._loop_guard = LoopGuard()

    def check(self, ctx: RunContext) -> AgentState:
        """
        Called at CHECK_TERMINATION. Returns the next state.
        Order of precedence: escalate > budget > loop > continue.
        """
        if ctx.force_escalate:
            return AgentState.ESCALATE

        exceeded, reason = ctx.budget_tracker.is_exceeded()
        if exceeded:
            ctx.failure_reason = reason
            return AgentState.FAIL

        if self._loop_guard.check_state_loop(ctx):
            ctx.failure_reason = "Infinite loop detected — same state sequence repeated 3 times."
            return AgentState.FAIL

        return AgentState.CALL_LLM
