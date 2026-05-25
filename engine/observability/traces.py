from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel

from engine.observability.spans import Span

logger = logging.getLogger(__name__)


class Trace(BaseModel):
    trace_id: str
    run_id: str
    agent_id: str
    session_id: str
    user_id: str
    started_at: str        # ISO timestamp
    ended_at: str
    status: str
    spans: list[Span]
    total_tokens: int
    total_cost_usd: float
    total_latency_ms: int
    steps_taken: int


class TraceCollector:
    """
    Accumulates spans during a run and emits each one as a JSON log line.
    Phase 1-2: stores completed traces in a module-level dict.
    Phase 3: will also persist to the memory service.
    """

    def __init__(self, trace_id: str, run_id: str) -> None:
        self.trace_id = trace_id
        self.run_id = run_id
        self._spans: list[Span] = []

    def add_span(self, span: Span) -> None:
        self._spans.append(span)
        logger.info(json.dumps({"event": "span", **span.model_dump()}))

    def spans(self) -> list[Span]:
        return list(self._spans)

    def emit_json(self, extra: dict[str, Any] | None = None) -> None:
        payload: dict[str, Any] = {
            "trace_id": self.trace_id,
            "run_id": self.run_id,
            "spans": [s.model_dump() for s in self._spans],
        }
        if extra:
            payload.update(extra)
        logger.info(json.dumps(payload))


# ── Module-level in-memory store (Phase 1-2) ──────────────────────────────────
_trace_store: dict[str, Trace] = {}


def store_trace(trace: Trace) -> None:
    _trace_store[trace.trace_id] = trace


def get_trace(trace_id: str) -> Trace | None:
    return _trace_store.get(trace_id)
