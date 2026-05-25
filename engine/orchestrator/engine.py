from __future__ import annotations

import datetime
import logging
import os
import uuid

import anthropic

from engine.context.budget import BudgetTracker
from engine.memory.audit_memory import AuditMemory
from engine.memory.client import MemoryClient, MemoryServiceUnavailable, MemoryServiceUnreachable
from engine.memory.session_memory import SessionMemory
from engine.memory.user_memory import UserMemory
from engine.memory.working_memory import WorkingMemory
from engine.models import AgentRun, AgentRunResult, RunContext
from engine.observability.traces import Trace, TraceCollector, store_trace
from engine.orchestrator.state_machine import TERMINAL_STATES, AgentState
from engine.orchestrator.step_runner import StepRunner
from engine.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class AgentEngine:
    """
    Public entry point. Create one instance per process; share across requests.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        model: str | None = None,
        memory_url: str | None = None,
    ) -> None:
        self._registry = registry
        self._model = model or os.environ.get("EVAL_MODEL", "claude-haiku-4-5-20251001")
        self._llm = anthropic.AsyncAnthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY"),
        )
        self._step_runner = StepRunner(registry, self._llm, self._model)

        # Memory client — shared across all runs
        self._memory_client = MemoryClient(base_url=memory_url)
        self._session_memory = SessionMemory(self._memory_client)
        self._user_memory = UserMemory(self._memory_client)
        self._working_memory = WorkingMemory(self._memory_client)
        self._audit_memory = AuditMemory(self._memory_client)

    async def run(self, request: AgentRun) -> AgentRunResult:
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        trace_id = f"trace_{uuid.uuid4().hex[:12]}"
        started_at = datetime.datetime.utcnow().isoformat()

        budget_tracker = BudgetTracker(
            max_steps=request.budget.max_steps,
            max_tokens=request.budget.max_tokens,
            max_cost_usd=request.budget.max_cost_usd,
            timeout_seconds=request.budget.timeout_seconds,
        )
        trace_collector = TraceCollector(trace_id=trace_id, run_id=run_id)

        ctx = RunContext(
            run=request,
            run_id=run_id,
            trace_id=trace_id,
            budget_tracker=budget_tracker,
            trace_collector=trace_collector,
            # Inject memory objects
            session_memory=self._session_memory,
            user_memory=self._user_memory,
            working_memory=self._working_memory,
            audit_memory=self._audit_memory,
        )

        logger.info("Starting run %s (trace %s) agent=%s", run_id, trace_id, request.agent_id)

        state = AgentState.START

        while state not in TERMINAL_STATES:
            next_state = await self._step_runner.execute(state, ctx)
            logger.debug("%s → %s", state.value, next_state.value)
            state = next_state

        ended_at = datetime.datetime.utcnow().isoformat()
        status = _terminal_status(state, ctx)

        # ── Post-run memory operations ─────────────────────────────────────────

        # 1. Write assistant final answer to session memory
        if ctx.final_answer and ctx.session_memory:
            try:
                await ctx.session_memory.append_assistant_message(
                    request.agent_id, request.session_id, ctx.final_answer
                )
            except (MemoryServiceUnavailable, MemoryServiceUnreachable):
                logger.warning("Failed to write final answer to session memory run=%s", run_id)

        # 2. Write audit record
        try:
            await self._audit_memory.write(
                request.agent_id,
                run_id,
                session_id=request.session_id,
                user_id=request.user_id,
                status=status,
                steps_taken=budget_tracker.steps_taken,
                total_tokens=budget_tracker.tokens_used,
                total_cost_usd=budget_tracker.cost_usd,
                latency_ms=budget_tracker.elapsed_ms(),
                trace_id=trace_id,
                failure_reason=ctx.failure_reason,
            )
        except (MemoryServiceUnavailable, MemoryServiceUnreachable):
            logger.warning("Failed to write audit record run=%s", run_id)

        # 3. Delete working memory explicitly
        try:
            await self._working_memory.delete(request.agent_id, run_id)
        except (MemoryServiceUnavailable, MemoryServiceUnreachable):
            logger.warning("Failed to delete working memory run=%s", run_id)

        # ── Build and store trace ──────────────────────────────────────────────
        trace = Trace(
            trace_id=trace_id,
            run_id=run_id,
            agent_id=request.agent_id,
            session_id=request.session_id,
            user_id=request.user_id,
            started_at=started_at,
            ended_at=ended_at,
            status=status,
            spans=trace_collector.spans(),
            total_tokens=budget_tracker.tokens_used,
            total_cost_usd=round(budget_tracker.cost_usd, 6),
            total_latency_ms=budget_tracker.elapsed_ms(),
            steps_taken=budget_tracker.steps_taken,
        )
        store_trace(trace)
        trace_collector.emit_json({"status": status})

        logger.info(
            "Run %s finished: status=%s steps=%d tokens=%d cost=$%.4f latency=%dms",
            run_id, status, budget_tracker.steps_taken,
            budget_tracker.tokens_used, budget_tracker.cost_usd,
            budget_tracker.elapsed_ms(),
        )

        return AgentRunResult(
            run_id=run_id,
            status=status,  # type: ignore[arg-type]
            final_answer=ctx.final_answer,
            trace_id=trace_id,
            steps_taken=budget_tracker.steps_taken,
            total_tokens_used=budget_tracker.tokens_used,
            total_cost_usd=round(budget_tracker.cost_usd, 6),
            latency_ms=budget_tracker.elapsed_ms(),
            failure_reason=ctx.failure_reason,
        )


def _terminal_status(state: AgentState, ctx: RunContext) -> str:
    if state == AgentState.RESPOND:
        return "completed"
    if state == AgentState.ESCALATE:
        return "escalated"
    reason = ctx.failure_reason or ""
    if "max_steps" in reason or "max_tokens" in reason or "max_cost_usd" in reason:
        return "budget_exceeded"
    if "timeout" in reason:
        return "timeout"
    return "failed"
