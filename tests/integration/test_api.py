"""
Integration tests for the REST API — agents CRUD, tools, POST /runs,
GET /runs/{run_id}, health/ready.

AgentEngine is mocked via FastAPI dependency overrides.
A real ToolRegistry and AgentRegistry are used so validation logic is tested.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient
from pydantic import BaseModel

from engine.api.agent_registry import AgentRegistry
from engine.api.app import app
from engine.api.dependencies import get_agent_registry, get_engine, get_tool_registry
from engine.models import AgentRunResult
from engine.tools.registry import ToolRegistry
from engine.tools.schemas import ToolDefinition

# ── Shared test fixtures ──────────────────────────────────────────────────────

class _In(BaseModel):
    x: str

class _Out(BaseModel):
    y: str

async def _fn(inp: _In) -> dict:
    return {"y": inp.x}

def _make_tool_registry() -> ToolRegistry:
    tr = ToolRegistry()
    tr.register(ToolDefinition(
        name="order_lookup",
        description="Look up order status",
        input_schema=_In, output_schema=_Out, fn=_fn,
    ))
    return tr

def _make_agent_registry(tr: ToolRegistry) -> AgentRegistry:
    return AgentRegistry(tool_registry=tr)

def _mock_engine(result: AgentRunResult) -> MagicMock:
    engine = MagicMock()
    engine._model = "claude-haiku-4-5-20251001"
    engine.run = AsyncMock(return_value=result)
    return engine

def _completed_result(run_id: str = "run_test001") -> AgentRunResult:
    return AgentRunResult(
        run_id=run_id, status="completed",
        final_answer="Order is delivered.",
        trace_id="trace_test001",
        steps_taken=3, total_tokens_used=450,
        total_cost_usd=0.0018, latency_ms=2300,
    )

_AGENT_PAYLOAD = {
    "agent_id": "support_agent",
    "description": "Customer support agent",
    "system_prompt": "You are a helpful support agent.",
    "tools": ["order_lookup"],
    "default_budget": {"max_steps": 5, "max_tokens": 2000, "max_cost_usd": 0.10, "timeout_seconds": 30},
}

_RUN_PAYLOAD = {
    "agent_id": "support_agent",
    "session_id": "sess_test",
    "user_id": "user_test",
    "input": "Where is my order?",
}


# ── POST /agents ──────────────────────────────────────────────────────────────

def test_register_agent_success():
    tr = _make_tool_registry()
    ar = _make_agent_registry(tr)
    app.dependency_overrides[get_tool_registry] = lambda: tr
    app.dependency_overrides[get_agent_registry] = lambda: ar

    with TestClient(app) as client:
        resp = client.post("/agents", json=_AGENT_PAYLOAD)

    app.dependency_overrides.clear()
    assert resp.status_code == 201
    data = resp.json()
    assert data["agent_id"] == "support_agent"
    assert data["created_at"] != ""


def test_register_agent_duplicate_returns_409():
    tr = _make_tool_registry()
    ar = _make_agent_registry(tr)
    app.dependency_overrides[get_tool_registry] = lambda: tr
    app.dependency_overrides[get_agent_registry] = lambda: ar

    with TestClient(app) as client:
        client.post("/agents", json=_AGENT_PAYLOAD)
        resp = client.post("/agents", json=_AGENT_PAYLOAD)

    app.dependency_overrides.clear()
    assert resp.status_code == 409
    assert "already exists" in resp.json()["detail"]


def test_register_agent_unknown_tool_returns_422():
    tr = _make_tool_registry()
    ar = _make_agent_registry(tr)
    app.dependency_overrides[get_tool_registry] = lambda: tr
    app.dependency_overrides[get_agent_registry] = lambda: ar

    payload = {**_AGENT_PAYLOAD, "tools": ["nonexistent_tool"]}

    with TestClient(app) as client:
        resp = client.post("/agents", json=payload)

    app.dependency_overrides.clear()
    assert resp.status_code == 422
    assert "nonexistent_tool" in resp.json()["detail"]


# ── GET /agents ───────────────────────────────────────────────────────────────

def test_list_agents_empty():
    tr = _make_tool_registry()
    ar = _make_agent_registry(tr)
    app.dependency_overrides[get_tool_registry] = lambda: tr
    app.dependency_overrides[get_agent_registry] = lambda: ar

    with TestClient(app) as client:
        resp = client.get("/agents")

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_agents_after_register():
    tr = _make_tool_registry()
    ar = _make_agent_registry(tr)
    app.dependency_overrides[get_tool_registry] = lambda: tr
    app.dependency_overrides[get_agent_registry] = lambda: ar

    with TestClient(app) as client:
        client.post("/agents", json=_AGENT_PAYLOAD)
        resp = client.get("/agents")

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["agent_id"] == "support_agent"
    # system_prompt must NOT appear in list view
    assert "system_prompt" not in resp.json()[0]


def test_get_agent_full_definition():
    tr = _make_tool_registry()
    ar = _make_agent_registry(tr)
    app.dependency_overrides[get_tool_registry] = lambda: tr
    app.dependency_overrides[get_agent_registry] = lambda: ar

    with TestClient(app) as client:
        client.post("/agents", json=_AGENT_PAYLOAD)
        resp = client.get("/agents/support_agent")

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    data = resp.json()
    assert "system_prompt" in data
    assert data["system_prompt"] == "You are a helpful support agent."


def test_get_agent_not_found():
    tr = _make_tool_registry()
    ar = _make_agent_registry(tr)
    app.dependency_overrides[get_agent_registry] = lambda: ar

    with TestClient(app) as client:
        resp = client.get("/agents/nonexistent")

    app.dependency_overrides.clear()
    assert resp.status_code == 404


def test_delete_agent():
    tr = _make_tool_registry()
    ar = _make_agent_registry(tr)
    app.dependency_overrides[get_tool_registry] = lambda: tr
    app.dependency_overrides[get_agent_registry] = lambda: ar

    with TestClient(app) as client:
        client.post("/agents", json=_AGENT_PAYLOAD)
        resp = client.delete("/agents/support_agent")
        assert resp.status_code == 204
        resp2 = client.get("/agents/support_agent")
        assert resp2.status_code == 404

    app.dependency_overrides.clear()


# ── GET /tools ────────────────────────────────────────────────────────────────

def test_list_tools_returns_registered_tools():
    tr = _make_tool_registry()
    app.dependency_overrides[get_tool_registry] = lambda: tr

    with TestClient(app) as client:
        resp = client.get("/tools")

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    tools = resp.json()
    assert len(tools) == 1
    assert tools[0]["name"] == "order_lookup"
    assert "input_schema" in tools[0]
    assert "output_schema" in tools[0]


def test_get_tool_not_found():
    tr = _make_tool_registry()
    app.dependency_overrides[get_tool_registry] = lambda: tr

    with TestClient(app) as client:
        resp = client.get("/tools/nonexistent_tool")

    app.dependency_overrides.clear()
    assert resp.status_code == 404
    assert "nonexistent_tool" in resp.json()["detail"]


# ── POST /runs ────────────────────────────────────────────────────────────────

def test_submit_run_with_registered_agent():
    tr = _make_tool_registry()
    ar = _make_agent_registry(tr)
    result = _completed_result("run_api_001")
    engine = _mock_engine(result)

    app.dependency_overrides[get_tool_registry] = lambda: tr
    app.dependency_overrides[get_agent_registry] = lambda: ar
    app.dependency_overrides[get_engine] = lambda: engine

    with TestClient(app) as client:
        client.post("/agents", json=_AGENT_PAYLOAD)
        resp = client.post("/runs", json=_RUN_PAYLOAD)

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["run_id"] == "run_api_001"


def test_submit_run_unregistered_agent_returns_404():
    tr = _make_tool_registry()
    ar = _make_agent_registry(tr)
    app.dependency_overrides[get_tool_registry] = lambda: tr
    app.dependency_overrides[get_agent_registry] = lambda: ar

    with TestClient(app) as client:
        # No POST /agents first
        resp = client.post("/runs", json=_RUN_PAYLOAD)

    app.dependency_overrides.clear()
    assert resp.status_code == 404
    assert "support_agent" in resp.json()["detail"]


def test_submit_run_uses_agent_definition_not_request():
    """Engine must receive system_prompt and tools from the registry, not the request."""
    tr = _make_tool_registry()
    ar = _make_agent_registry(tr)
    result = _completed_result()
    engine = _mock_engine(result)

    app.dependency_overrides[get_tool_registry] = lambda: tr
    app.dependency_overrides[get_agent_registry] = lambda: ar
    app.dependency_overrides[get_engine] = lambda: engine

    with TestClient(app) as client:
        client.post("/agents", json=_AGENT_PAYLOAD)
        client.post("/runs", json=_RUN_PAYLOAD)

    app.dependency_overrides.clear()

    # Verify engine.run was called with the definition's system_prompt
    call_args = engine.run.call_args[0][0]
    assert call_args.system_prompt == "You are a helpful support agent."
    assert call_args.tools == ["order_lookup"]


def test_submit_run_missing_required_field_returns_422():
    with TestClient(app) as client:
        resp = client.post("/runs", json={"agent_id": "support_agent"})
    assert resp.status_code == 422


# ── GET /runs/{run_id} ────────────────────────────────────────────────────────

def test_get_run_returns_stored_result():
    tr = _make_tool_registry()
    ar = _make_agent_registry(tr)
    result = _completed_result("run_stored_001")
    engine = _mock_engine(result)

    app.dependency_overrides[get_tool_registry] = lambda: tr
    app.dependency_overrides[get_agent_registry] = lambda: ar
    app.dependency_overrides[get_engine] = lambda: engine

    with TestClient(app) as client:
        client.post("/agents", json=_AGENT_PAYLOAD)
        client.post("/runs", json=_RUN_PAYLOAD)
        resp = client.get("/runs/run_stored_001")

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert resp.json()["run_id"] == "run_stored_001"


def test_get_run_unknown_returns_404():
    with TestClient(app) as client:
        resp = client.get("/runs/run_totally_unknown")
    assert resp.status_code == 404


# ── Health / Ready ────────────────────────────────────────────────────────────

def test_health_check():
    with TestClient(app) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_ready_memory_unreachable():
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
    assert resp.json()["memory_service"] == "unreachable"
