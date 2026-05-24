"""
Trace routes — retrieve raw traces and replay them step-by-step.

GET /traces/{trace_id}         — full trace with all spans
GET /traces/{trace_id}/replay  — spans ordered by step, enriched with delta info
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from engine.observability.traces import Trace, get_trace

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/traces", tags=["traces"])


# ── Response models ────────────────────────────────────────────────────────────

class ReplayStep(BaseModel):
    """A single step in the trace replay — one state transition."""
    step: int
    span_id: str
    from_state: str
    to_state: str
    duration_ms: int
    timestamp_ms: int
    cumulative_duration_ms: int    # wall time from run start to end of this step
    metadata: dict[str, Any] = {}


class TraceReplayResponse(BaseModel):
    trace_id: str
    run_id: str
    agent_id: str
    session_id: str
    user_id: str
    status: str
    started_at: str
    ended_at: str
    total_steps: int
    total_tokens: int
    total_cost_usd: float
    total_latency_ms: int
    steps: list[ReplayStep]


# ── Handlers ──────────────────────────────────────────────────────────────────

@router.get("/{trace_id}", response_model=Trace)
async def get_trace_raw(trace_id: str) -> Trace:
    """
    Return the raw trace object — all spans as stored.
    Useful for programmatic access and eval pipelines.
    """
    trace = get_trace(trace_id)
    if trace is None:
        raise HTTPException(
            status_code=404,
            detail=f"Trace '{trace_id}' not found. Run must complete in this server session.",
        )
    return trace


@router.get("/{trace_id}/replay", response_model=TraceReplayResponse)
async def replay_trace(trace_id: str) -> TraceReplayResponse:
    """
    Replay a completed trace step by step.

    Returns spans sorted by step number, each enriched with cumulative
    wall-clock time from the start of the run. Useful for debugging exactly
    what the agent did, in what order, and how long each state took.

    Example response step:
      {
        "step": 2,
        "from_state": "CALL_LLM",
        "to_state": "PROCESS_RESPONSE",
        "duration_ms": 1240,
        "cumulative_duration_ms": 1350,
        "metadata": {"model": "claude-haiku-4-5-20251001", "input_tokens": 312, ...}
      }
    """
    trace = get_trace(trace_id)
    if trace is None:
        raise HTTPException(
            status_code=404,
            detail=f"Trace '{trace_id}' not found.",
        )

    # Sort spans by step, then by timestamp within the same step
    sorted_spans = sorted(trace.spans, key=lambda s: (s.step, s.timestamp_ms))

    # Build replay steps with cumulative durations
    cumulative_ms = 0
    steps: list[ReplayStep] = []
    for span in sorted_spans:
        cumulative_ms += span.duration_ms
        steps.append(ReplayStep(
            step=span.step,
            span_id=span.span_id,
            from_state=span.from_state,
            to_state=span.to_state,
            duration_ms=span.duration_ms,
            timestamp_ms=span.timestamp_ms,
            cumulative_duration_ms=cumulative_ms,
            metadata=span.metadata,
        ))

    return TraceReplayResponse(
        trace_id=trace.trace_id,
        run_id=trace.run_id,
        agent_id=trace.agent_id,
        session_id=trace.session_id,
        user_id=trace.user_id,
        status=trace.status,
        started_at=trace.started_at,
        ended_at=trace.ended_at,
        total_steps=trace.steps_taken,
        total_tokens=trace.total_tokens,
        total_cost_usd=trace.total_cost_usd,
        total_latency_ms=trace.total_latency_ms,
        steps=steps,
    )
