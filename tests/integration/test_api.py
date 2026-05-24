"""
Integration tests for the REST API — POST /runs, GET /runs/{run_id},
GET /traces/{trace_id}/replay.

The AgentEngine is fully mocked: we override the FastAPI dependency so
no Anthropic API calls or memory service calls are made.
All tests run without any external services.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock

from engine.api.app import app
from engine.api.dependencies import get_engine
from engine.models import AgentRunResult


# ── Mock engine factory ───────────────────────────────────────────────────────

def _mock_engine(result: AgentRunResult) -> MagicMock:
    engine = MagicMock()
    engine._model = "claude-haiku-4-5-20251001"
    engine.run = AsyncMock(return_value=result)
    return engine


def _completed_result(run_id: str = "run_test001", trace_id: str = "trace_test001") -> AgentRunResult:
    return AgentRunResult(
        run_id=run_id,
        status="completed",
        final_answer="Your order ORD-789 has been delivered.",
        trace_id=trace_id,
        steps_taken=3,
        total_tokens_used=450,
        total_cost_usd=0.0018,
        latency_ms=2300,
    )


def _failed_result(run_id: str = "run_fail001") -> AgentRunResult:
    return AgentRunResult(
        run_id=run_id,
        status="failed",
        final_answer=None,
        trace_id="trace_fail001",
        steps_taken=1,
        total_tokens_used=100,
        total_cost_usd=0.0004,
        latency_ms=500,
        failure_reason="LLM API error after 4 attempts: 500 Internal Server Error",
    )


_VALID_RUN_PAYLOAD = {
    "agent_id": "support_agent",
    "session_id": "sess_test",
    "user_id": "user_test",
    "input": "Where is my order ORD-789?",
    "tools": ["order_lookup"],
    "system_prompt": "You are a helpful support agent.",
    "budget": {
        "max_steps": 5,
        "max_tokens": 2000,
        "max_cost_usd": 0.10,
        "timeout_seconds": 30,
    },
}


# ── POST /runs ────────────────────────────────────────────────────────────────

def test_submit_run_returns_completed_result():
    result = _completed_result()
    app.dependency_overrides[get_engine] = lambda: _mock_engine(result)

    with TestClient(app) as client:
        resp = client.post("/runs", json=_VALID_RUN_PAYLOAD)

    app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["run_id"] == "run_test001"
    assert data["status"] == "completed"
    assert data["final_answer"] == "Your order ORD-789 has been delivered."
    assert data["steps_taken"] == 3
    assert data["total_tokens_used"] == 450


def test_submit_run_returns_failed_result():
    result = _failed_result()
    app.dependency_overrides[get_engine] = lambda: _mock_engine(result)

    with TestClient(app) as client:
        resp = client.post("/runs", json=_VALID_RUN_PAYLOAD)

    app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "failed"
    assert data["failure_reason"] is not None
    assert data["final_answer"] is None


def test_submit_run_missing_required_field_returns_422():
    with TestClient(app) as client:
        resp = client.post("/runs", json={"agent_id": "support_agent"})  # missing most fields
    assert resp.status_code == 422


def test_submit_run_engine_crash_returns_500():
    engine = MagicMock()
    engine._model = "claude-haiku-4-5-20251001"
    engine.run = AsyncMock(side_effect=RuntimeError("catastrophic failure"))
    app.dependency_overrides[get_engine] = lambda: engine

    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.post("/runs", json=_VALID_RUN_PAYLOAD)

    app.dependency_overrides.clear()
    assert resp.status_code == 500
    assert "Internal engine error" in resp.json()["detail"]


# ── GET /runs/{run_id} ────────────────────────────────────────────────────────

def test_get_run_returns_stored_result():
    result = _completed_result(run_id="run_stored_001", trace_id="trace_stored_001")
    app.dependency_overrides[get_engine] = lambda: _mock_engine(result)

    with TestClient(app) as client:
        # Submit first
        client.post("/runs", json=_VALID_RUN_PAYLOAD)
        # Then retrieve
        resp = client.get("/runs/run_stored_001")

    app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["run_id"] == "run_stored_001"


def test_get_run_unknown_id_returns_404():
    with TestClient(app) as client:
        resp = client.get("/runs/run_does_not_exist_xyz")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


# ── GET /health and /ready ────────────────────────────────────────────────────

def test_health_check():
    with TestClient(app) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "version": "0.1.0"}


def test_ready_check_memory_unreachable():
    """
    /ready should return 200 even when memory service is unreachable —
    the engine degrades gracefully.
    """
    memory_client = MagicMock()
    memory_client.is_healthy = AsyncMock(return_value=False)
    engine = MagicMock()
    engine._model = "claude-haiku-4-5-20251001"
    engine._memory_client = memory_client

    app.dependency_overrides[get_engine] = lambda: engine

    with TestClient(app) as client:
        resp = client.get("/ready")

    app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["memory_service"] == "unreachable"


def test_ready_check_memory_healthy():
    memory_client = MagicMock()
    memory_client.is_healthy = AsyncMock(return_value=True)
    engine = MagicMock()
    engine._model = "claude-haiku-4-5-20251001"
    engine._memory_client = memory_client

    app.dependency_overrides[get_engine] = lambda: engine

    with TestClient(app) as client:
        resp = client.get("/ready")

    app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["memory_service"] == "reachable"
