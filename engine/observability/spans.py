from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class Span(BaseModel):
    span_id: str
    trace_id: str
    step: int
    from_state: str
    to_state: str
    timestamp_ms: int
    duration_ms: int
    metadata: dict[str, Any] = {}
