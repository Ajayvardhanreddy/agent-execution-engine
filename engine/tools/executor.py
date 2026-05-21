from __future__ import annotations

import asyncio
import time

from pydantic import ValidationError

from engine.tools.errors import is_recoverable
from engine.tools.registry import ToolRegistry
from engine.tools.schemas import ToolError, ToolResult


class ToolExecutor:
    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    async def execute(
        self,
        tool_name: str,
        raw_input: dict,
        trace_id: str,
    ) -> ToolResult:
        tool = self.registry.get(tool_name)
        retries_used = 0
        start_ms = time.time() * 1000

        # Validate input before any attempt
        try:
            validated_input = tool.input_schema.model_validate(raw_input)
        except ValidationError as exc:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                output=None,
                error=ToolError(
                    error_type="validation_error",
                    message=f"Input validation failed: {exc.error_count()} error(s): {exc.errors()[0]['msg']}",
                    recoverable=False,
                ),
                latency_ms=int(time.time() * 1000 - start_ms),
                retries_used=0,
            )

        last_error: ToolError | None = None

        for attempt in range(tool.max_retries + 1):
            if attempt > 0:
                retries_used += 1
                await asyncio.sleep(min(2 ** (attempt - 1), 8))  # 1s, 2s, 4s…

            try:
                raw_output = await asyncio.wait_for(
                    tool.fn(validated_input),
                    timeout=tool.timeout_seconds,
                )
            except asyncio.TimeoutError:
                last_error = ToolError(
                    error_type="timeout",
                    message=f"Tool '{tool_name}' timed out after {tool.timeout_seconds}s",
                    recoverable=True,
                )
                if attempt < tool.max_retries:
                    continue
                # All retries exhausted on timeout
                return self._timeout_result(tool_name, last_error, start_ms, retries_used, tool.on_timeout)

            except Exception as exc:
                last_error = ToolError(
                    error_type="external_failure",
                    message=str(exc),
                    recoverable=is_recoverable("external_failure"),
                )
                if tool.on_error == "fail":
                    return ToolResult(
                        tool_name=tool_name,
                        success=False,
                        output=None,
                        error=last_error,
                        latency_ms=int(time.time() * 1000 - start_ms),
                        retries_used=retries_used,
                    )
                if attempt < tool.max_retries:
                    continue
                break

            # Validate output
            if raw_output is None or raw_output == {}:
                last_error = ToolError(
                    error_type="empty_result",
                    message=f"Tool '{tool_name}' returned empty output.",
                    recoverable=True,
                )
                return ToolResult(
                    tool_name=tool_name,
                    success=False,
                    output=None,
                    error=last_error,
                    latency_ms=int(time.time() * 1000 - start_ms),
                    retries_used=retries_used,
                )

            try:
                tool.output_schema.model_validate(raw_output)
            except ValidationError as exc:
                last_error = ToolError(
                    error_type="validation_error",
                    message=f"Output validation failed: {exc.errors()[0]['msg']}",
                    recoverable=False,
                )
                return ToolResult(
                    tool_name=tool_name,
                    success=False,
                    output=None,
                    error=last_error,
                    latency_ms=int(time.time() * 1000 - start_ms),
                    retries_used=retries_used,
                )

            # Success
            return ToolResult(
                tool_name=tool_name,
                success=True,
                output=raw_output,
                error=None,
                latency_ms=int(time.time() * 1000 - start_ms),
                retries_used=retries_used,
            )

        # Exhausted all retries with non-timeout error
        return ToolResult(
            tool_name=tool_name,
            success=False,
            output=None,
            error=last_error,
            latency_ms=int(time.time() * 1000 - start_ms),
            retries_used=retries_used,
        )

    def _timeout_result(
        self,
        tool_name: str,
        error: ToolError,
        start_ms: float,
        retries_used: int,
        on_timeout: str,
    ) -> ToolResult:
        # on_timeout="escalate" is handled by the step runner checking the result
        return ToolResult(
            tool_name=tool_name,
            success=False,
            output=None,
            error=error,
            latency_ms=int(time.time() * 1000 - start_ms),
            retries_used=retries_used,
        )
