from __future__ import annotations

from typing import Any, Awaitable, Callable, Literal

from pydantic import BaseModel, ConfigDict

from engine.tools.errors import ToolErrorType


class ToolError(BaseModel):
    error_type: ToolErrorType
    message: str
    recoverable: bool


class ToolResult(BaseModel):
    tool_name: str
    success: bool
    output: dict[str, Any] | None
    error: ToolError | None
    latency_ms: int
    retries_used: int


class ToolDefinition(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    description: str
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]
    fn: Callable[[BaseModel], Awaitable[dict[str, Any]]]
    timeout_seconds: int = 10
    max_retries: int = 2
    permission_level: Literal["read", "write", "escalate"] = "read"
    on_timeout: Literal["fail", "escalate", "skip"] = "fail"
    on_error: Literal["fail", "escalate", "return_structured_error"] = "return_structured_error"
