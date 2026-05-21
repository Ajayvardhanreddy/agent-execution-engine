from __future__ import annotations

import datetime
import logging
import os
import uuid

import anthropic

from engine.context.budget import BudgetTracker
from engine.models import AgentRun, AgentRunResult, RunContext
from engine.observability.traces import Trace, TraceCollector, store_trace
from engine.orchestrator.state_machine import AgentState, TERMINAL_STATES
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
    ) -> None:
        self._registry = registry
        self._model = model or os.environ.get("EVAL_MODEL", "claude-haiku-4-5-20251001")
        self._llm = anthropic.AsyncAnthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY"),
        )
        self._step_runner = StepRunner(registry, self._llm, self._model)

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
        )

        logger.info("Starting run %s (trace %s) agent=%s", run_id, trace_id, request.agent_id)

        state = AgentState.START

        while state not in TERMINAL_STATES:
            next_state = await self._step_runner.execute(state, ctx)
            logger.debug("%s → %s", state.value, next_state.value)
            state = next_state

        ended_at = datetime.datetime.utcnow().isoformat()
        status = _terminal_status(state, ctx)

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
    # FAIL — distinguish budget_exceeded vs timeout vs generic failed
    reason = ctx.failure_reason or ""
    if "max_steps" in reason or "max_tokens" in reason or "max_cost_usd" in reason:
        return "budget_exceeded"
    if "timeout" in reason:
        return "timeout"
    return "failed"
