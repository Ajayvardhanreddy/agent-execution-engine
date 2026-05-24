"""
Health and readiness endpoints.

GET /health   — liveness probe (always 200 if process is alive)
GET /ready    — readiness probe (checks memory service reachability)
"""
from __future__ import annotations

import os
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from engine.api.dependencies import get_engine
from engine.orchestrator.engine import AgentEngine

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    version: str = "0.1.0"


class ReadinessResponse(BaseModel):
    status: str
    memory_service: str     # "reachable" | "unreachable" | "disabled"


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness probe — returns 200 as long as the process is running."""
    return HealthResponse(status="ok")


@router.get("/ready", response_model=ReadinessResponse)
async def ready(
    engine: Annotated[AgentEngine, Depends(get_engine)],
) -> ReadinessResponse:
    """
    Readiness probe — checks whether the memory service is reachable.

    Returns 200 regardless (the engine degrades gracefully without memory),
    but the `memory_service` field tells you the current state.
    """
    memory_url = os.environ.get("MEMORY_SERVICE_URL", "http://localhost:8080")
    if not memory_url:
        return ReadinessResponse(status="ok", memory_service="disabled")

    is_healthy = await engine._memory_client.is_healthy()  # type: ignore[attr-defined]
    return ReadinessResponse(
        status="ok",
        memory_service="reachable" if is_healthy else "unreachable",
    )
