from __future__ import annotations

from engine.tools.schemas import ToolDefinition


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered.")
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition:
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' not found in registry.")
        return self._tools[name]

    def has(self, name: str) -> bool:
        return name in self._tools

    def list_all(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def get_anthropic_schemas(self, names: list[str]) -> list[dict]:
        """Convert registered ToolDefinitions to Anthropic tool-use schema format."""
        schemas = []
        for name in names:
            if not self.has(name):
                continue
            tool = self._tools[name]
            schema = tool.input_schema.model_json_schema()
            # Anthropic requires "type": "object" at root; Pydantic already sets this
            schemas.append({
                "name": tool.name,
                "description": tool.description,
                "input_schema": schema,
            })
        return schemas
