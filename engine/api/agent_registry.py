"""
Agent Registry — server-side store of AgentDefinitions.

Engineering teams register agents once at startup (or via POST /agents).
The run API looks up the definition by agent_id and builds the internal
AgentRun from it — callers never touch system_prompt, tools, or budget.

Storage: in-process dict (Phase 3). Phase 6 will persist to Layer 2
under the `agent_def:{agent_id}` namespace.
"""
from __future__ import annotations

import datetime

from engine.models import AgentDefinition
from engine.tools.registry import ToolRegistry


class AgentNotFound(Exception):
    pass


class AgentAlreadyExists(Exception):
    pass


class UnknownTools(Exception):
    """Raised when an AgentDefinition references tools not in the ToolRegistry."""
    def __init__(self, unknown: list[str], registered: list[str]) -> None:
        self.unknown = unknown
        self.registered = registered
        suggestions = ", ".join(registered) or "(none registered yet)"
        super().__init__(
            f"Unknown tool(s): {unknown}. "
            f"Registered tools: [{suggestions}]. "
            f"Register the tool first with tool_registry.register() before defining an agent."
        )


class AgentRegistry:
    """
    In-memory store for AgentDefinition objects.

    Thread-safety: single-process, asyncio — no lock needed.
    """

    def __init__(self, tool_registry: ToolRegistry) -> None:
        self._agents: dict[str, AgentDefinition] = {}
        self._tool_registry = tool_registry

    def register(self, definition: AgentDefinition) -> AgentDefinition:
        """
        Register a new agent.

        Raises AgentAlreadyExists if agent_id is taken.
        Raises UnknownTools if any tool name is not in the ToolRegistry.
        Returns the stored definition (with created_at set).
        """
        if definition.agent_id in self._agents:
            raise AgentAlreadyExists(
                f"Agent '{definition.agent_id}' already exists. "
                f"Use PUT /agents/{definition.agent_id} to update it."
            )
        self._validate_tools(definition.tools)
        stored = definition.model_copy(
            update={"created_at": datetime.datetime.utcnow().isoformat()}
        )
        self._agents[definition.agent_id] = stored
        return stored

    def get(self, agent_id: str) -> AgentDefinition:
        """Raises AgentNotFound if agent_id is unknown."""
        if agent_id not in self._agents:
            registered = sorted(self._agents.keys())
            hint = f" Registered agents: {registered}." if registered else " No agents registered yet."
            raise AgentNotFound(
                f"Agent '{agent_id}' not found.{hint} "
                f"Call POST /agents to register it first."
            )
        return self._agents[agent_id]

    def update(self, agent_id: str, definition: AgentDefinition) -> AgentDefinition:
        """Replace an existing agent definition. Raises AgentNotFound if not registered."""
        existing = self.get(agent_id)  # raises AgentNotFound if missing
        self._validate_tools(definition.tools)
        stored = definition.model_copy(
            update={
                "agent_id": agent_id,          # cannot rename via update
                "created_at": existing.created_at,
            }
        )
        self._agents[agent_id] = stored
        return stored

    def delete(self, agent_id: str) -> None:
        """Raises AgentNotFound if agent_id is unknown."""
        self.get(agent_id)  # raises if missing
        del self._agents[agent_id]

    def list_all(self) -> list[AgentDefinition]:
        return list(self._agents.values())

    # ── Validation ─────────────────────────────────────────────────────────────

    def _validate_tools(self, tools: list[str]) -> None:
        unknown = [t for t in tools if not self._tool_registry.has(t)]
        if unknown:
            registered = [td.name for td in self._tool_registry.list_all()]
            raise UnknownTools(unknown, registered)
