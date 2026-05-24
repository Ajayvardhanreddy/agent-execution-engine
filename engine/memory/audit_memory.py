"""
Audit Memory — immutable run record written once at completion.

Layer 2 session_id convention: "audit:{run_id}"
e.g. agent_id="support_agent", session_id="audit:run_xyz789"

Written at: run completion (RESPOND / ESCALATE / FAIL). Single append.
TTL:        90 days (managed by Layer 2 cleanup job).

This feeds directly into the Layer 2 activity stream:
  GET /stream/{agent_id}  returns these events chronologically.
"""
from __future__ import annotations

import json
import logging

from engine.memory.client import MemoryClient

logger = logging.getLogger(__name__)

_PREFIX = "audit"


def _ns(run_id: str) -> str:
    return f"{_PREFIX}:{run_id}"


class AuditMemory:
    def __init__(self, client: MemoryClient) -> None:
        self._client = client

    async def write(
        self,
        agent_id: str,
        run_id: str,
        *,
        session_id: str,
        user_id: str,
        status: str,
        steps_taken: int,
        total_tokens: int,
        total_cost_usd: float,
        latency_ms: int,
        trace_id: str,
        failure_reason: str | None,
    ) -> None:
        record = json.dumps({
            "run_id": run_id,
            "session_id": session_id,
            "user_id": user_id,
            "status": status,
            "steps_taken": steps_taken,
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost_usd, 6),
            "latency_ms": latency_ms,
            "trace_id": trace_id,
            "failure_reason": failure_reason,
        })
        await self._client.append(agent_id, _ns(run_id), role="audit", content=record)
        logger.info("audit_memory.written run=%s status=%s", run_id, status)
