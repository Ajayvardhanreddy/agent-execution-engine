"""
Async HTTP client wrapping the Layer 2 Agent Memory Service API.

Base URL: MEMORY_SERVICE_URL (default http://localhost:8080)
No auth required.

All methods raise MemoryServiceUnavailable on 503 / connection error.
Callers decide whether to fail-fast or degrade gracefully.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_URL = "http://localhost:8080"
_TIMEOUT = httpx.Timeout(10.0)


class MemoryServiceUnavailable(Exception):
    """
    Raised when Layer 2 returns 503 (KV store down).
    This is a hard failure — the spec says do not continue without memory.
    """

class MemoryServiceUnreachable(Exception):
    """
    Raised when the Layer 2 process cannot be reached at all (ConnectError).
    The engine treats this as 'no memory available' and degrades gracefully
    rather than failing the run, so Phase 1 scenarios work without Layer 2.
    """


class MemorySessionNotFound(Exception):
    """Raised when Layer 2 returns 404 for a session lookup."""


@dataclass
class StoredMessage:
    role: str
    content: str
    ts: int


class MemoryClient:
    """
    Thin async wrapper around every Layer 2 endpoint used by the engine.
    One instance lives for the lifetime of the process; it owns an
    httpx.AsyncClient that is shared across all requests.
    """

    def __init__(self, base_url: str | None = None) -> None:
        self._base = (base_url or os.environ.get("MEMORY_SERVICE_URL", _DEFAULT_URL)).rstrip("/")
        self._http = httpx.AsyncClient(base_url=self._base, timeout=_TIMEOUT)

    # ── Write ──────────────────────────────────────────────────────────────────

    async def append(self, agent_id: str, session_id: str, role: str, content: str) -> None:
        """
        POST /memory/{agent_id}/{session_id}/append
        Creates the session if it does not exist.
        """
        url = f"/memory/{agent_id}/{session_id}/append"
        try:
            resp = await self._http.post(url, json={"role": role, "content": content})
        except httpx.ConnectError as exc:
            raise MemoryServiceUnreachable(f"Cannot reach memory service at {self._base}: {exc}") from exc

        if resp.status_code == 503:
            raise MemoryServiceUnavailable(resp.json().get("detail", "kv_store_unavailable"))
        resp.raise_for_status()

    # ── Read ───────────────────────────────────────────────────────────────────

    async def read_window(
        self, agent_id: str, session_id: str, last_n: int = 50
    ) -> list[StoredMessage]:
        """
        GET /memory/{agent_id}/{session_id}/window?last_n=N
        Returns an empty list if the session does not exist (404).
        """
        url = f"/memory/{agent_id}/{session_id}/window"
        try:
            resp = await self._http.get(url, params={"last_n": last_n})
        except httpx.ConnectError as exc:
            raise MemoryServiceUnreachable(f"Cannot reach memory service: {exc}") from exc

        if resp.status_code == 404:
            return []
        if resp.status_code == 503:
            raise MemoryServiceUnavailable(resp.json().get("detail", "kv_store_unavailable"))
        resp.raise_for_status()

        data = resp.json()
        return [StoredMessage(role=m["role"], content=m["content"], ts=m["ts"]) for m in data["messages"]]

    async def read_all(self, agent_id: str, session_id: str) -> list[StoredMessage]:
        """
        GET /memory/{agent_id}/{session_id}
        Returns an empty list if the session does not exist.
        """
        url = f"/memory/{agent_id}/{session_id}"
        try:
            resp = await self._http.get(url)
        except httpx.ConnectError as exc:
            raise MemoryServiceUnreachable(f"Cannot reach memory service: {exc}") from exc

        if resp.status_code == 404:
            return []
        if resp.status_code == 503:
            raise MemoryServiceUnavailable(resp.json().get("detail", "kv_store_unavailable"))
        resp.raise_for_status()

        data = resp.json()
        return [StoredMessage(role=m["role"], content=m["content"], ts=m["ts"]) for m in data["messages"]]

    # ── Delete ─────────────────────────────────────────────────────────────────

    async def delete_session(self, agent_id: str, session_id: str) -> None:
        """
        DELETE /memory/{agent_id}/{session_id}
        Silently ignores 404 (already deleted / never existed).
        """
        url = f"/memory/{agent_id}/{session_id}"
        try:
            resp = await self._http.delete(url)
        except httpx.ConnectError as exc:
            raise MemoryServiceUnreachable(f"Cannot reach memory service: {exc}") from exc

        if resp.status_code in (200, 404):
            return
        if resp.status_code == 503:
            raise MemoryServiceUnavailable(resp.json().get("detail", "kv_store_unavailable"))
        resp.raise_for_status()

    # ── Health ─────────────────────────────────────────────────────────────────

    async def is_healthy(self) -> bool:
        try:
            resp = await self._http.get("/health")
            return resp.status_code == 200
        except Exception:
            return False

    async def aclose(self) -> None:
        await self._http.aclose()
