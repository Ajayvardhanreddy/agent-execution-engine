"""
Run routes — submit a new agent run and query its result.

POST /runs          — start an agent run (synchronous, waits for completion)
GET  /runs/{run_id} — retrieve a stored run result by run_id
"""
from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from engine.api.dependencies import get_engine
from engine.api.metrics import ACTIVE_RUNS, RUN_DURATION, RUN_TOKENS, RUNS_TOTAL
from engine.models import AgentRun, AgentRunResult
from engine.orchestrator.engine import AgentEngine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/runs", tags=["runs"])

# Module-level result cache — Phase 3 uses in-process storage.
# Phase 5/6 will persist via the memory service.
_run_results: dict[str, AgentRunResult] = {}


@router.post("", response_model=AgentRunResult, status_code=200)
async def submit_run(
    request: AgentRun,
    engine: Annotated[AgentEngine, Depends(get_engine)],
) -> AgentRunResult:
    """
    Submit an agent run and wait for it to complete.

    The request body is an `AgentRun` — agent_id, session_id, user_id, input,
    tools list, system_prompt, and optional budget overrides.

    Returns the full `AgentRunResult` once the run finishes (completed /
    escalated / failed / budget_exceeded / timeout).
    """
    agent_id = request.agent_id
    ACTIVE_RUNS.labels(agent_id=agent_id).inc()

    try:
        result = await engine.run(request)
    except Exception as exc:
        logger.exception("Unhandled error running agent %s", agent_id)
        ACTIVE_RUNS.labels(agent_id=agent_id).dec()
        raise HTTPException(status_code=500, detail=f"Internal engine error: {exc}") from exc

    # Record metrics
    ACTIVE_RUNS.labels(agent_id=agent_id).dec()
    RUNS_TOTAL.labels(agent_id=agent_id, status=result.status).inc()
    RUN_DURATION.labels(agent_id=agent_id, status=result.status).observe(
        result.latency_ms / 1000.0
    )
    RUN_TOKENS.labels(
        agent_id=agent_id,
        model=engine._model,  # type: ignore[attr-defined]
    ).inc(result.total_tokens_used)

    # Persist for GET /runs/{run_id}
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
