"""
Tests for the MCP server tools (engine/mcp/server.py).

These tests mock the engine HTTP API and verify:
  - run_agent returns the final_answer on success
  - run_agent handles engine failures gracefully
  - run_agent forwards the correct payload to POST /runs
  - list_agents returns the engine's /agents response
"""
from __future__ import annotations

import pytest
import pytest_httpx

import engine.mcp.server as mcp_server

# ── run_agent ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_agent_returns_final_answer(httpx_mock: pytest_httpx.HTTPXMock) -> None:
    httpx_mock.add_response(
        method="POST",
        url=f"{mcp_server.ENGINE_URL}/runs",
        json={
            "run_id": "run_abc",
            "status": "completed",
            "final_answer": "Your refund of $29.99 has been processed.",
            "trace_id": "trace_abc",
            "steps_taken": 3,
            "total_tokens_used": 500,
            "total_cost_usd": 0.001,
            "latency_ms": 1200,
            "failure_reason": None,
        },
    )

    result = await mcp_server.run_agent(
        agent_id="support_agent",
        session_id="sess-001",
        user_id="user-42",
        input="I want a refund",
    )

    assert result == "Your refund of $29.99 has been processed."


@pytest.mark.asyncio
async def test_run_agent_forwards_correct_payload(httpx_mock: pytest_httpx.HTTPXMock) -> None:
    httpx_mock.add_response(
        method="POST",
        url=f"{mcp_server.ENGINE_URL}/runs",
        json={
            "run_id": "run_x",
            "status": "completed",
            "final_answer": "Done.",
            "trace_id": "t",
            "steps_taken": 1,
            "total_tokens_used": 100,
            "total_cost_usd": 0.0,
            "latency_ms": 500,
            "failure_reason": None,
        },
    )

    await mcp_server.run_agent(
        agent_id="engineering_agent",
        session_id="eng-sess-001",
        user_id="eng-alice",
        input="Review PR-42",
    )

    requests = httpx_mock.get_requests()
    assert len(requests) == 1
    body = requests[0].content
    import json
    payload = json.loads(body)
    assert payload["agent_id"] == "engineering_agent"
    assert payload["session_id"] == "eng-sess-001"
    assert payload["user_id"] == "eng-alice"
    assert payload["input"] == "Review PR-42"


@pytest.mark.asyncio
async def test_run_agent_no_final_answer_returns_status(
    httpx_mock: pytest_httpx.HTTPXMock,
) -> None:
    httpx_mock.add_response(
        method="POST",
        url=f"{mcp_server.ENGINE_URL}/runs",
        json={
            "run_id": "run_fail",
            "status": "failed",
            "final_answer": None,
            "trace_id": "t",
            "steps_taken": 2,
            "total_tokens_used": 200,
            "total_cost_usd": 0.0,
            "latency_ms": 800,
            "failure_reason": "budget exceeded",
        },
    )

    result = await mcp_server.run_agent(
        agent_id="support_agent",
        session_id="sess-002",
        user_id="user-99",
        input="help",
    )

    assert result == "[failed] budget exceeded"


@pytest.mark.asyncio
async def test_run_agent_engine_4xx_raises(httpx_mock: pytest_httpx.HTTPXMock) -> None:
    httpx_mock.add_response(
        method="POST",
        url=f"{mcp_server.ENGINE_URL}/runs",
        status_code=404,
        json={"detail": "Agent 'ghost_agent' not found."},
    )

    import httpx

    with pytest.raises(httpx.HTTPStatusError):
        await mcp_server.run_agent(
            agent_id="ghost_agent",
            session_id="s",
            user_id="u",
            input="hello",
        )


# ── list_agents ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_agents_returns_registry(httpx_mock: pytest_httpx.HTTPXMock) -> None:
    agents_payload = [
        {"agent_id": "support_agent", "description": "Customer support agent", "tools": ["get_order"]},
        {"agent_id": "engineering_agent", "description": "Engineering assistant", "tools": ["code_search"]},
    ]
    httpx_mock.add_response(
        method="GET",
        url=f"{mcp_server.ENGINE_URL}/agents",
        json=agents_payload,
    )

    result = await mcp_server.list_agents()

    assert len(result) == 2
    assert result[0]["agent_id"] == "support_agent"
    assert result[1]["agent_id"] == "engineering_agent"


@pytest.mark.asyncio
async def test_list_agents_empty_registry(httpx_mock: pytest_httpx.HTTPXMock) -> None:
    httpx_mock.add_response(
        method="GET",
        url=f"{mcp_server.ENGINE_URL}/agents",
        json=[],
    )

    result = await mcp_server.list_agents()

    assert result == []
