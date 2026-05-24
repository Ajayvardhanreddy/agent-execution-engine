"""
Run routes — submit a new agent run and query its result.

POST /runs          — start a run (agent config looked up server-side)
GET  /runs/{run_id} — retrieve a stored run result by run_id
"""
from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from engine.api.agent_registry import AgentNotFound, AgentRegistry
from engine.api.dependencies import get_agent_registry, get_engine
from engine.api.metrics import ACTIVE_RUNS, RUN_DURATION, RUN_TOKENS, RUNS_TOTAL
from engine.models import AgentRun, AgentRunResult, RunRequest
from engine.orchestrator.engine import AgentEngine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/runs", tags=["runs"])

_run_results: dict[str, AgentRunResult] = {}


@router.post("", response_model=AgentRunResult, status_code=200)
async def submit_run(
    request: RunRequest,
    engine: Annotated[AgentEngine, Depends(get_engine)],
    agent_registry: Annotated[AgentRegistry, Depends(get_agent_registry)],
) -> AgentRunResult:
    """
    Submit an agent run and wait for it to complete.

    The request body only needs: agent_id, session_id, user_id, input.
    The engine looks up the agent's system_prompt, tools, and budget
    server-side — callers cannot modify agent configuration.

    Optional `budget_override` lets callers apply *tighter* limits for
    a specific run (e.g. a rate-limited free tier).

    Returns 404 if agent_id is not registered (call POST /agents first).
    """
    try:
        definition = agent_registry.get(request.agent_id)
    except AgentNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # Callers may tighten but not loosen the budget
    budget = request.budget_override or definition.default_budget

    internal_run = AgentRun(
        agent_id=request.agent_id,
        session_id=request.session_id,
        user_id=request.user_id,
        input=request.input,
        tools=definition.tools,
        system_prompt=definition.system_prompt,
        budget=budget,
    )

    agent_id = request.agent_id
    ACTIVE_RUNS.labels(agent_id=agent_id).inc()

    try:
        result = await engine.run(internal_run)
    except Exception as exc:
        logger.exception("Unhandled error running agent %s", agent_id)
        ACTIVE_RUNS.labels(agent_id=agent_id).dec()
        raise HTTPException(status_code=500, detail=f"Internal engine error: {exc}") from exc

    ACTIVE_RUNS.labels(agent_id=agent_id).dec()
    RUNS_TOTAL.labels(agent_id=agent_id, status=result.status).inc()
    RUN_DURATION.labels(agent_id=agent_id, status=result.status).observe(
        result.latency_ms / 1000.0
    )
    RUN_TOKENS.labels(agent_id=agent_id, model=engine._model).inc(result.total_tokens_used)  # type: ignore[attr-defined]

    _run_results[result.run_id] = result

    logger.info(
        "run_complete run_id=%s status=%s steps=%d tokens=%d cost=$%.4f latency=%dms",
        result.run_id, result.status, result.steps_taken,
        result.total_tokens_used, result.total_cost_usd, result.latency_ms,
    )

    return result


@router.get("/{run_id}", response_model=AgentRunResult)
async def get_run(run_id: str) -> AgentRunResult:
    """
    Retrieve a previously completed run result by its run_id.

    Returns 404 if the run_id is unknown (not yet completed, or server restarted).
    """
    result = _run_results.get(run_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Run '{run_id}' not found. It may still be in progress or the server was restarted.",
        )
    return result
