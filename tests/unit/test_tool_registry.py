import pytest
from pydantic import BaseModel

from engine.tools.registry import ToolRegistry
from engine.tools.schemas import ToolDefinition


class _Input(BaseModel):
    value: str


class _Output(BaseModel):
    result: str


async def _dummy_fn(inp: _Input) -> dict:
    return {"result": inp.value}


def _make_tool(name: str = "test_tool") -> ToolDefinition:
    return ToolDefinition(
        name=name,
        description="A test tool",
        input_schema=_Input,
        output_schema=_Output,
        fn=_dummy_fn,
    )


def test_register_and_get():
    reg = ToolRegistry()
    tool = _make_tool()
    reg.register(tool)
    assert reg.get("test_tool") is tool


def test_has():
    reg = ToolRegistry()
    reg.register(_make_tool())
    assert reg.has("test_tool")
    assert not reg.has("other_tool")


def test_duplicate_registration_raises():
    reg = ToolRegistry()
    reg.register(_make_tool())
    with pytest.raises(ValueError, match="already registered"):
        reg.register(_make_tool())


def test_get_missing_raises():
    reg = ToolRegistry()
    with pytest.raises(KeyError):
        reg.get("nonexistent")


def test_list_all():
    reg = ToolRegistry()
    reg.register(_make_tool("tool_a"))
    reg.register(_make_tool("tool_b"))
    names = [t.name for t in reg.list_all()]
    assert set(names) == {"tool_a", "tool_b"}


def test_anthropic_schemas():
    reg = ToolRegistry()
    reg.register(_make_tool("tool_a"))
    reg.register(_make_tool("tool_b"))
    schemas = reg.get_anthropic_schemas(["tool_a"])
    assert len(schemas) == 1
    assert schemas[0]["name"] == "tool_a"
    assert "input_schema" in schemas[0]
    assert schemas[0]["input_schema"]["type"] == "object"


def test_anthropic_schemas_skips_unregistered():
    reg = ToolRegistry()
    reg.register(_make_tool("tool_a"))
    schemas = reg.get_anthropic_schemas(["tool_a", "ghost_tool"])
    assert len(schemas) == 1
