"""
Unit tests for AgentRegistry — registration, lookup, update, delete,
and tool validation.
"""
from __future__ import annotations

import pytest
from pydantic import BaseModel

from engine.api.agent_registry import (
    AgentAlreadyExists,
    AgentNotFound,
    AgentRegistry,
    UnknownTools,
)
from engine.models import AgentDefinition
from engine.tools.registry import ToolRegistry
from engine.tools.schemas import ToolDefinition

# ── Fixtures ──────────────────────────────────────────────────────────────────

class _In(BaseModel):
    x: str

class _Out(BaseModel):
    y: str

async def _fn(inp: _In) -> dict:
    return {"y": inp.x}

def _make_tool(name: str) -> ToolDefinition:
    return ToolDefinition(
        name=name, description=f"Tool {name}",
        input_schema=_In, output_schema=_Out, fn=_fn,
    )

def _make_registry(*tool_names: str) -> AgentRegistry:
    tr = ToolRegistry()
    for n in tool_names:
        tr.register(_make_tool(n))
    return AgentRegistry(tool_registry=tr)

def _defn(agent_id: str = "support_agent", tools: list[str] | None = None) -> AgentDefinition:
    return AgentDefinition(
        agent_id=agent_id,
        description="Test agent",
        system_prompt="You are a test agent.",
        tools=tools or ["tool_a"],
    )


# ── register ──────────────────────────────────────────────────────────────────

def test_register_succeeds():
    ar = _make_registry("tool_a")
    stored = ar.register(_defn())
    assert stored.agent_id == "support_agent"
    assert stored.created_at != ""


def test_register_sets_created_at():
    ar = _make_registry("tool_a")
    stored = ar.register(_defn())
    assert "T" in stored.created_at   # ISO format


def test_register_duplicate_raises():
    ar = _make_registry("tool_a")
    ar.register(_defn())
    with pytest.raises(AgentAlreadyExists):
        ar.register(_defn())


def test_register_unknown_tool_raises():
    ar = _make_registry("tool_a")
    with pytest.raises(UnknownTools) as exc_info:
        ar.register(_defn(tools=["tool_a", "tool_missing"]))
    assert "tool_missing" in str(exc_info.value)
    assert "tool_a" in str(exc_info.value)


def test_register_all_tools_unknown_raises():
    ar = _make_registry()   # empty tool registry
    with pytest.raises(UnknownTools):
        ar.register(_defn(tools=["tool_a"]))


# ── get ───────────────────────────────────────────────────────────────────────

def test_get_returns_stored_definition():
    ar = _make_registry("tool_a")
    ar.register(_defn())
    result = ar.get("support_agent")
    assert result.agent_id == "support_agent"


def test_get_unknown_raises():
    ar = _make_registry("tool_a")
    with pytest.raises(AgentNotFound) as exc_info:
        ar.get("nonexistent_agent")
    assert "nonexistent_agent" in str(exc_info.value)


def test_get_error_message_lists_registered_agents():
    ar = _make_registry("tool_a")
    ar.register(_defn("agent_one"))
    with pytest.raises(AgentNotFound) as exc_info:
        ar.get("agent_two")
    assert "agent_one" in str(exc_info.value)


# ── update ────────────────────────────────────────────────────────────────────

def test_update_succeeds():
    ar = _make_registry("tool_a", "tool_b")
    ar.register(_defn(tools=["tool_a"]))
    updated = ar.update("support_agent", _defn(tools=["tool_b"]))
    assert updated.tools == ["tool_b"]


def test_update_preserves_created_at():
    ar = _make_registry("tool_a")
    original = ar.register(_defn())
    updated = ar.update("support_agent", _defn())
    assert updated.created_at == original.created_at


def test_update_nonexistent_raises():
    ar = _make_registry("tool_a")
    with pytest.raises(AgentNotFound):
        ar.update("nonexistent", _defn())


def test_update_unknown_tool_raises():
    ar = _make_registry("tool_a")
    ar.register(_defn())
    with pytest.raises(UnknownTools):
        ar.update("support_agent", _defn(tools=["tool_missing"]))


# ── delete ────────────────────────────────────────────────────────────────────

def test_delete_removes_agent():
    ar = _make_registry("tool_a")
    ar.register(_defn())
    ar.delete("support_agent")
    with pytest.raises(AgentNotFound):
        ar.get("support_agent")


def test_delete_nonexistent_raises():
    ar = _make_registry("tool_a")
    with pytest.raises(AgentNotFound):
        ar.delete("nonexistent")


# ── list_all ──────────────────────────────────────────────────────────────────

def test_list_all_empty():
    ar = _make_registry("tool_a")
    assert ar.list_all() == []


def test_list_all_returns_all():
    ar = _make_registry("tool_a")
    ar.register(_defn("agent_one"))
    ar.register(_defn("agent_two"))
    ids = {a.agent_id for a in ar.list_all()}
    assert ids == {"agent_one", "agent_two"}
