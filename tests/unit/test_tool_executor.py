import asyncio

import pytest
from pydantic import BaseModel

from engine.tools.executor import ToolExecutor
from engine.tools.registry import ToolRegistry
from engine.tools.schemas import ToolDefinition


class _In(BaseModel):
    x: int


class _Out(BaseModel):
    y: int


def _make_registry(fn, name="t", timeout=10, max_retries=0, on_error="return_structured_error") -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(ToolDefinition(
        name=name,
        description="test",
        input_schema=_In,
        output_schema=_Out,
        fn=fn,
        timeout_seconds=timeout,
        max_retries=max_retries,
        on_error=on_error,
    ))
    return reg


@pytest.mark.asyncio
async def test_success():
    async def fn(inp: _In) -> dict:
        return {"y": inp.x * 2}

    reg = _make_registry(fn)
    result = await ToolExecutor(reg).execute("t", {"x": 5}, "trace_1")
    assert result.success
    assert result.output == {"y": 10}
    assert result.error is None
    assert result.retries_used == 0


@pytest.mark.asyncio
async def test_input_validation_error():
    async def fn(inp: _In) -> dict:
        return {"y": 1}

    reg = _make_registry(fn)
    result = await ToolExecutor(reg).execute("t", {"x": "not_an_int"}, "trace_1")
    assert not result.success
    assert result.error is not None
    assert result.error.error_type == "validation_error"
    assert not result.error.recoverable


@pytest.mark.asyncio
async def test_empty_result():
    async def fn(inp: _In) -> dict:
        return {}

    reg = _make_registry(fn)
    result = await ToolExecutor(reg).execute("t", {"x": 1}, "trace_1")
    assert not result.success
    assert result.error.error_type == "empty_result"
    assert result.error.recoverable


@pytest.mark.asyncio
async def test_output_validation_error():
    async def fn(inp: _In) -> dict:
        return {"y": "not_an_int"}

    reg = _make_registry(fn)
    result = await ToolExecutor(reg).execute("t", {"x": 1}, "trace_1")
    assert not result.success
    assert result.error.error_type == "validation_error"


@pytest.mark.asyncio
async def test_timeout():
    async def fn(inp: _In) -> dict:
        await asyncio.sleep(999)
        return {"y": 1}

    reg = _make_registry(fn, timeout=1, max_retries=0)
    result = await ToolExecutor(reg).execute("t", {"x": 1}, "trace_1")
    assert not result.success
    assert result.error.error_type == "timeout"


@pytest.mark.asyncio
async def test_retry_on_exception():
    call_count = 0

    async def fn(inp: _In) -> dict:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise RuntimeError("transient failure")
        return {"y": 42}

    reg = _make_registry(fn, max_retries=2)
    result = await ToolExecutor(reg).execute("t", {"x": 1}, "trace_1")
    assert result.success
    assert result.output == {"y": 42}
    assert result.retries_used == 2


@pytest.mark.asyncio
async def test_on_error_fail_returns_immediately():
    async def fn(inp: _In) -> dict:
        raise RuntimeError("hard failure")

    reg = _make_registry(fn, max_retries=2, on_error="fail")
    result = await ToolExecutor(reg).execute("t", {"x": 1}, "trace_1")
    assert not result.success
    assert result.retries_used == 0  # fails immediately, no retries
