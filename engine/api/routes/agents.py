"""
Agent and Tool management routes.

Agent CRUD (engineering team, one-time setup):
  POST   /agents                     — register a new agent definition
  GET    /agents                     — list all registered agents
  GET    /agents/{agent_id}          — get one agent's config
  PUT    /agents/{agent_id}          — update agent config
  DELETE /agents/{agent_id}          — remove an agent

Tool inspection:
  GET    /tools                      — list all registered tools with schemas
  GET    /tools/{tool_name}          — get one tool's full schema
  POST   /tools/{tool_name}/test     — run a tool directly with test input
"""
from __future__ import annotations

import logging
import time
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from engine.api.agent_registry import AgentAlreadyExists, AgentNotFound, AgentRegistry, UnknownTools
from engine.api.dependencies import get_agent_registry, get_tool_registry
from engine.models import AgentDefinition
from engine.tools.executor import ToolExecutor
from engine.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)
router = APIRouter(tags=["agents & tools"])


# ── Response models ────────────────────────────────────────────────────────────

class ToolSchema(BaseModel):
    name: str
    description: str
    permission_level: str
    timeout_seconds: int
    max_retries: int
    on_error: str
    on_timeout: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]


class ToolTestRequest(BaseModel):
    input: dict[str, Any]


class ToolTestResponse(BaseModel):
    tool_name: str
    success: bool
    output: dict[str, Any] | None
    error: dict[str, Any] | None
    latency_ms: int
    retries_used: int


class AgentListItem(BaseModel):
    agent_id: str
    description: str
    tools: list[str]
    created_at: str


# ── Agent routes ───────────────────────────────────────────────────────────────

@router.post("/agents", response_model=AgentDefinition, status_code=201)
async def register_agent(
    definition: AgentDefinition,
    agent_registry: Annotated[AgentRegistry, Depends(get_agent_registry)],
) -> AgentDefinition:
    """
    Register a new agent definition.

    The engineering team calls this once per agent before any runs.
    All fields (system_prompt, tools, budget) are fixed server-side —
    callers of POST /runs only send agent_id + session + user + input.

    Tool names in `tools` must already be registered in the ToolRegistry.
    Returns 409 if agent_id already exists. Use PUT to update.
    """
    try:
        return agent_registry.register(definition)
    except AgentAlreadyExists as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except UnknownTools as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/agents", response_model=list[AgentListItem])
async def list_agents(
    agent_registry: Annotated[AgentRegistry, Depends(get_agent_registry)],
) -> list[AgentListItem]:
    """List all registered agents (summary view — no system_prompt)."""
    return [
        AgentListItem(
            agent_id=a.agent_id,
            description=a.description,
            tools=a.tools,
            created_at=a.created_at,
        )
        for a in agent_registry.list_all()
    ]


@router.get("/agents/{agent_id}", response_model=AgentDefinition)
async def get_agent(
    agent_id: str,
    agent_registry: Annotated[AgentRegistry, Depends(get_agent_registry)],
) -> AgentDefinition:
    """Get full agent definition including system_prompt."""
    try:
        return agent_registry.get(agent_id)
    except AgentNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/agents/{agent_id}", response_model=AgentDefinition)
async def update_agent(
    agent_id: str,
    definition: AgentDefinition,
    agent_registry: Annotated[AgentRegistry, Depends(get_agent_registry)],
) -> AgentDefinition:
    """
    Update an existing agent definition.

    agent_id in the path is authoritative — the agent_id in the body is ignored.
    Returns 404 if agent does not exist (use POST /agents to create).
    """
    try:
        return agent_registry.update(agent_id, definition)
    except AgentNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except UnknownTools as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/agents/{agent_id}", status_code=204)
async def delete_agent(
    agent_id: str,
    agent_registry: Annotated[AgentRegistry, Depends(get_agent_registry)],
) -> None:
    """Remove an agent definition. Does not affect completed runs."""
    try:
        agent_registry.delete(agent_id)
    except AgentNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ── Tool routes ────────────────────────────────────────────────────────────────

@router.get("/tools", response_model=list[ToolSchema])
async def list_tools(
    tool_registry: Annotated[ToolRegistry, Depends(get_tool_registry)],
) -> list[ToolSchema]:
    """
    List all tools registered in the engine.

    Use this to discover available tools before registering an agent.
    The `input_schema` and `output_schema` fields are JSON Schema objects
    showing exactly what the tool accepts and returns.
    """
    return [
        ToolSchema(
            name=t.name,
            description=t.description,
            permission_level=t.permission_level,
            timeout_seconds=t.timeout_seconds,
            max_retries=t.max_retries,
            on_error=t.on_error,
            on_timeout=t.on_timeout,
            input_schema=t.input_schema.model_json_schema(),
            output_schema=t.output_schema.model_json_schema(),
        )
        for t in tool_registry.list_all()
    ]


@router.get("/tools/{tool_name}", response_model=ToolSchema)
async def get_tool(
    tool_name: str,
    tool_registry: Annotated[ToolRegistry, Depends(get_tool_registry)],
) -> ToolSchema:
    """Get one tool's full schema including input/output types."""
    if not tool_registry.has(tool_name):
        registered = [t.name for t in tool_registry.list_all()]
        raise HTTPException(
            status_code=404,
            detail=f"Tool '{tool_name}' not found. Registered tools: {registered}",
        )
    t = tool_registry.get(tool_name)
    return ToolSchema(
        name=t.name,
        description=t.description,
        permission_level=t.permission_level,
        timeout_seconds=t.timeout_seconds,
        max_retries=t.max_retries,
        on_error=t.on_error,
        on_timeout=t.on_timeout,
        input_schema=t.input_schema.model_json_schema(),
        output_schema=t.output_schema.model_json_schema(),
    )


@router.post("/tools/{tool_name}/test", response_model=ToolTestResponse)
async def test_tool(
    tool_name: str,
    request: ToolTestRequest,
    tool_registry: Annotated[ToolRegistry, Depends(get_tool_registry)],
) -> ToolTestResponse:
    """
    Run a tool directly with test input — no agent, no LLM.

    Use this to verify your tool code works before wiring it into an agent.
    Returns the raw output, latency, and any errors.

    Example:
      POST /tools/order_lookup/test
      { "input": { "order_id": "ORD-789" } }
    """
    if not tool_registry.has(tool_name):
        registered = [t.name for t in tool_registry.list_all()]
        raise HTTPException(
            status_code=404,
            detail=f"Tool '{tool_name}' not found. Registered tools: {registered}",
        )

    executor = ToolExecutor(tool_registry)
    trace_id = f"test_{int(time.time() * 1000)}"

    result = await executor.execute(tool_name, request.input, trace_id=trace_id)

    return ToolTestResponse(
        tool_name=result.tool_name,
        success=result.success,
        output=result.output,
        error=result.error.model_dump() if result.error else None,
        latency_ms=result.latency_ms,
        retries_used=result.retries_used,
    )
