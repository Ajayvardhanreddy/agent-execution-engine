"""
Integration tests for the memory layer — fully self-contained.

All HTTP calls to the Layer 2 service are intercepted by pytest-httpx.
No running memory service is required.
"""
from __future__ import annotations

import json

import pytest
from pytest_httpx import HTTPXMock

from engine.memory.audit_memory import AuditMemory
from engine.memory.client import MemoryClient, MemoryServiceUnavailable
from engine.memory.session_memory import SessionMemory
from engine.memory.user_memory import UserMemory
from engine.memory.working_memory import WorkingMemory

BASE = "http://localhost:8080"


# ── Helpers ────────────────────────────────────────────────────────────────────

def _window_response(messages: list[dict]) -> dict:
    return {
        "session_id": "test-session",
        "messages": [{"role": m["role"], "content": m["content"], "ts": 1000} for m in messages],
        "total_messages": len(messages),
        "window_size": len(messages),
    }


def _session_response(messages: list[dict]) -> dict:
    return {
        "session_id": "test-session",
        "agent_id": "test-agent",
        "messages": [{"role": m["role"], "content": m["content"], "ts": 1000} for m in messages],
        "message_count": len(messages),
        "created_at": 1000,
        "updated_at": 2000,
        "version": 1,
    }


# ── MemoryClient ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_client_append_success(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/memory/agent1/session:s1/append",
        json=_session_response([{"role": "user", "content": "hello"}]),
    )
    client = MemoryClient(base_url=BASE)
    await client.append("agent1", "session:s1", "user", "hello")


@pytest.mark.asyncio
async def test_client_append_raises_on_503(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/memory/agent1/session:s1/append",
        status_code=503,
        json={"error": "kv_store_unavailable", "detail": "KV down"},
    )
    client = MemoryClient(base_url=BASE)
    with pytest.raises(MemoryServiceUnavailable):
        await client.append("agent1", "session:s1", "user", "hello")


@pytest.mark.asyncio
async def test_client_read_window_returns_empty_on_404(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        method="GET",
        url=f"{BASE}/memory/agent1/session:s1/window?last_n=50",
        status_code=404,
        json={"error": "session_not_found", "detail": "not found"},
    )
    client = MemoryClient(base_url=BASE)
    result = await client.read_window("agent1", "session:s1", last_n=50)
    assert result == []


@pytest.mark.asyncio
async def test_client_delete_ignores_404(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        method="DELETE",
        url=f"{BASE}/memory/agent1/working:run1",
        status_code=404,
        json={"error": "session_not_found", "detail": "not found"},
    )
    client = MemoryClient(base_url=BASE)
    # Should not raise
    await client.delete_session("agent1", "working:run1")


# ── SessionMemory ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_session_memory_load_returns_messages(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        method="GET",
        url=f"{BASE}/memory/support_agent/session:sess1/window?last_n=50",
        json=_window_response([
            {"role": "user", "content": "I need help"},
            {"role": "assistant", "content": "I can help you!"},
        ]),
    )
    client = MemoryClient(base_url=BASE)
    sm = SessionMemory(client)
    msgs = await sm.load("support_agent", "sess1", last_n=50)
    assert len(msgs) == 2
    assert msgs[0] == {"role": "user", "content": "I need help"}
    assert msgs[1] == {"role": "assistant", "content": "I can help you!"}


@pytest.mark.asyncio
async def test_session_memory_load_empty_when_no_history(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        method="GET",
        url=f"{BASE}/memory/support_agent/session:sess_new/window?last_n=50",
        status_code=404,
        json={"error": "session_not_found", "detail": ""},
    )
    client = MemoryClient(base_url=BASE)
    sm = SessionMemory(client)
    msgs = await sm.load("support_agent", "sess_new", last_n=50)
    assert msgs == []


# ── UserMemory ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_user_memory_load_facts(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        method="GET",
        url=f"{BASE}/memory/support_agent/user:u1",
        json=_session_response([
            {"role": "system", "content": "User's name is Alice."},
            {"role": "system", "content": "User prefers email contact."},
        ]),
    )
    client = MemoryClient(base_url=BASE)
    um = UserMemory(client)
    facts = await um.load_facts("support_agent", "u1")
    assert facts == ["User's name is Alice.", "User prefers email contact."]


@pytest.mark.asyncio
async def test_user_memory_extract_name(httpx_mock: HTTPXMock):
    # First load existing facts (empty)
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/memory/support_agent/user:u2/append",
        json=_session_response([{"role": "system", "content": "User's name is Bob."}]),
    )
    client = MemoryClient(base_url=BASE)
    um = UserMemory(client)
    await um.extract_and_store(
        "support_agent", "u2",
        user_message="Hi, my name is Bob. I have an issue with my order.",
        existing_facts=[],
    )
    # Verify the POST was called (httpx_mock raises if not consumed)


@pytest.mark.asyncio
async def test_user_memory_no_extract_if_no_name():
    # No HTTP mock needed — no call should be made
    client = MemoryClient(base_url=BASE)
    um = UserMemory(client)
    # Should complete without making any HTTP calls
    await um.extract_and_store(
        "support_agent", "u3",
        user_message="I want to return order ORD-789.",
        existing_facts=[],
    )


# ── WorkingMemory ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_working_memory_append_tool_result(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/memory/support_agent/working:run1/append",
        json=_session_response([{"role": "tool", "content": "{}"}]),
    )
    client = MemoryClient(base_url=BASE)
    wm = WorkingMemory(client)
    await wm.append_tool_result(
        "support_agent", "run1",
        tool_name="order_lookup",
        success=True,
        output={"order_id": "ORD-789", "status": "delivered"},
    )


@pytest.mark.asyncio
async def test_working_memory_load_parses_json(httpx_mock: HTTPXMock):
    payload = json.dumps({"tool": "order_lookup", "success": True, "output": {"status": "ok"}, "error": None})
    httpx_mock.add_response(
        method="GET",
        url=f"{BASE}/memory/support_agent/working:run1",
        json=_session_response([{"role": "tool", "content": payload}]),
    )
    client = MemoryClient(base_url=BASE)
    wm = WorkingMemory(client)
    results = await wm.load("support_agent", "run1")
    assert len(results) == 1
    assert results[0]["tool"] == "order_lookup"


@pytest.mark.asyncio
async def test_working_memory_delete(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        method="DELETE",
        url=f"{BASE}/memory/support_agent/working:run1",
        json={"message": "deleted", "session_id": "working:run1"},
    )
    client = MemoryClient(base_url=BASE)
    wm = WorkingMemory(client)
    await wm.delete("support_agent", "run1")


# ── AuditMemory ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_audit_memory_write(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/memory/support_agent/audit:run_abc/append",
        json=_session_response([{"role": "audit", "content": "{}"}]),
    )
    client = MemoryClient(base_url=BASE)
    am = AuditMemory(client)
    await am.write(
        "support_agent", "run_abc",
        session_id="sess1",
        user_id="user1",
        status="completed",
        steps_taken=3,
        total_tokens=1500,
        total_cost_usd=0.006,
        latency_ms=5000,
        trace_id="trace_xyz",
        failure_reason=None,
    )
