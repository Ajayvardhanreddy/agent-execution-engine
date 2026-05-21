from __future__ import annotations

import json
import logging
import time
from typing import Any

import anthropic

from engine.context.builder import ContextBuilder
from engine.context.compressor import ContextCompressor
from engine.models import RunContext
from engine.orchestrator.loop_guard import LoopGuard
from engine.orchestrator.retry_policy import LLM_RETRY
from engine.orchestrator.state_machine import AgentState
from engine.orchestrator.termination import TerminationChecker
from engine.observability.spans import Span
from engine.tools.executor import ToolExecutor
from engine.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

_ID_COUNTER = 0


def _gen_id(prefix: str = "sp") -> str:
    global _ID_COUNTER
    _ID_COUNTER += 1
    return f"{prefix}_{_ID_COUNTER:06d}"


class StepRunner:
    def __init__(
        self,
        registry: ToolRegistry,
        llm_client: anthropic.AsyncAnthropic,
        model: str,
    ) -> None:
        self._registry = registry
        self._client = llm_client
        self._model = model
        self._executor = ToolExecutor(registry)
        self._compressor = ContextCompressor()
        self._builder = ContextBuilder()
        self._loop_guard = LoopGuard()
        self._termination = TerminationChecker()

    async def execute(self, state: AgentState, ctx: RunContext) -> AgentState:
        ctx.state_history.append(state.value)
        start = time.time()

        try:
            next_state = await self._dispatch(state, ctx)
        except Exception as exc:
            logger.exception("Unhandled error in state %s", state.value)
            ctx.failure_reason = f"Unhandled error in {state.value}: {exc}"
            next_state = AgentState.FAIL

        span = Span(
            span_id=_gen_id("sp"),
            trace_id=ctx.trace_id,
            step=ctx.budget_tracker.steps_taken,
            from_state=state.value,
            to_state=next_state.value,
            timestamp_ms=int(start * 1000),
            duration_ms=int((time.time() - start) * 1000),
            metadata=self._span_metadata(state, ctx),
        )
        ctx.trace_collector.add_span(span)
        return next_state

    # ── Dispatch ────────────────────────────────────────────────────────────────

    async def _dispatch(self, state: AgentState, ctx: RunContext) -> AgentState:
        match state:
            case AgentState.START:
                return AgentState.LOAD_MEMORY
            case AgentState.LOAD_MEMORY:
                return await self._load_memory(ctx)
            case AgentState.BUILD_CONTEXT:
                return await self._build_context(ctx)
            case AgentState.CALL_LLM:
                return await self._call_llm(ctx)
            case AgentState.PROCESS_RESPONSE:
                return self._process_response(ctx)
            case AgentState.EXECUTE_TOOL:
                return await self._execute_tool(ctx)
            case AgentState.OBSERVE_RESULT:
                return self._observe_result(ctx)
            case AgentState.WRITE_MEMORY:
                return await self._write_memory(ctx)
            case AgentState.CHECK_TERMINATION:
                return self._check_termination(ctx)
            case _:
                raise ValueError(f"Cannot dispatch terminal state: {state.value}")

    # ── State handlers ──────────────────────────────────────────────────────────

    async def _load_memory(self, ctx: RunContext) -> AgentState:
        # Phase 1: no-op — memory wired in Phase 2
        return AgentState.BUILD_CONTEXT

    async def _build_context(self, ctx: RunContext) -> AgentState:
        self._builder.initialise(ctx)
        if ctx.budget_tracker.near_token_limit():
            self._compressor.compress(ctx)
        return AgentState.CALL_LLM

    async def _call_llm(self, ctx: RunContext) -> AgentState:
        tools_schemas = self._registry.get_anthropic_schemas(ctx.run.tools)
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": min(4096, max(256, ctx.budget_tracker.remaining_tokens())),
            "system": ctx.run.system_prompt,
            "messages": ctx.messages,
        }
        if tools_schemas:
            kwargs["tools"] = tools_schemas

        for attempt in range(LLM_RETRY.max_retries + 1):
            try:
                response = await self._client.messages.create(**kwargs)
                ctx.last_llm_response = response
                ctx.budget_tracker.add_tokens(
                    response.usage.input_tokens,
                    response.usage.output_tokens,
                    self._model,
                )
                ctx.budget_tracker.increment_step()
                return AgentState.PROCESS_RESPONSE

            except anthropic.APIStatusError as exc:
                logger.warning("LLM API error attempt %d/%d: %s", attempt + 1, LLM_RETRY.max_retries + 1, exc)
                if attempt < LLM_RETRY.max_retries:
                    await LLM_RETRY.sleep(attempt)
                else:
                    ctx.failure_reason = f"LLM API error after {LLM_RETRY.max_retries + 1} attempts: {exc}"
                    return AgentState.FAIL

            except Exception as exc:
                ctx.failure_reason = f"Unexpected LLM error: {exc}"
                return AgentState.FAIL

        ctx.failure_reason = "LLM call exhausted retries"
        return AgentState.FAIL

    def _process_response(self, ctx: RunContext) -> AgentState:
        response = ctx.last_llm_response

        if response.stop_reason == "tool_use":
            ctx.pending_tool_calls = [b for b in response.content if b.type == "tool_use"]
            ctx.messages.append({"role": "assistant", "content": response.content})
            return AgentState.EXECUTE_TOOL

        if response.stop_reason == "end_turn":
            text_blocks = [b for b in response.content if b.type == "text"]
            ctx.final_answer = text_blocks[0].text if text_blocks else ""
            ctx.messages.append({"role": "assistant", "content": response.content})
            return AgentState.RESPOND

        ctx.failure_reason = f"Unexpected stop_reason: {response.stop_reason!r}"
        return AgentState.FAIL

    async def _execute_tool(self, ctx: RunContext) -> AgentState:
        tool_results_content: list[dict] = []
        ctx.last_tool_results = []

        for call in ctx.pending_tool_calls:
            tool_name: str = call.name
            tool_input: dict = call.input

            # Tool not registered / not allowed for this agent
            if not self._registry.has(tool_name) or tool_name not in ctx.run.tools:
                available = ", ".join(ctx.run.tools)
                tool_results_content.append({
                    "type": "tool_result",
                    "tool_use_id": call.id,
                    "content": (
                        f"Tool '{tool_name}' is not available. "
                        f"Available tools: {available}"
                    ),
                    "is_error": True,
                })
                continue

            # Duplicate call guard
            if self._loop_guard.is_duplicate_tool_call(ctx, tool_name, tool_input):
                logger.warning("Duplicate tool call detected: %s", tool_name)
                tool_results_content.append({
                    "type": "tool_result",
                    "tool_use_id": call.id,
                    "content": (
                        "You already called this tool with these exact inputs. "
                        "Use a different approach or different parameters."
                    ),
                    "is_error": True,
                })
                continue

            result = await self._executor.execute(tool_name, tool_input, ctx.trace_id)
            self._loop_guard.register_tool_call(ctx, tool_name, tool_input)
            ctx.last_tool_results.append(result)

            # Escalate immediately if this is an escalation-class tool
            tool_def = self._registry.get(tool_name)
            if tool_def.permission_level == "escalate":
                ctx.force_escalate = True
                ctx.escalation_reason = (
                    result.output.get("reason", "") if result.output else ""
                ) or f"Tool '{tool_name}' triggered escalation."

            # Build tool_result block for next LLM message
            if result.success and result.output is not None:
                content_str = json.dumps(result.output)
            elif result.error is not None:
                content_str = json.dumps({
                    "error_type": result.error.error_type,
                    "message": result.error.message,
                    "recoverable": result.error.recoverable,
                })
            else:
                content_str = json.dumps({"error": "Tool returned no output."})

            tool_results_content.append({
                "type": "tool_result",
                "tool_use_id": call.id,
                "content": content_str,
                "is_error": not result.success,
            })

        ctx.messages.append({"role": "user", "content": tool_results_content})

        # Escalate immediately if any escalation-class tool was called
        if ctx.force_escalate:
            return AgentState.ESCALATE

        # Unrecoverable tool failure with on_error="fail"
        for result in ctx.last_tool_results:
            if not result.success and result.error and not result.error.recoverable:
                tool_def = self._registry.get(result.tool_name)
                if tool_def.on_error == "fail":
                    ctx.failure_reason = (
                        f"Tool '{result.tool_name}' failed with unrecoverable error: "
                        f"{result.error.message}"
                    )
                    return AgentState.FAIL

        return AgentState.OBSERVE_RESULT

    def _observe_result(self, ctx: RunContext) -> AgentState:
        # Phase 1: log results; Phase 2 will persist to working memory
        for result in ctx.last_tool_results:
            logger.info(
                json.dumps({
                    "event": "tool_result",
                    "trace_id": ctx.trace_id,
                    "tool_name": result.tool_name,
                    "success": result.success,
                    "latency_ms": result.latency_ms,
                    "retries_used": result.retries_used,
                })
            )
        return AgentState.WRITE_MEMORY

    async def _write_memory(self, ctx: RunContext) -> AgentState:
        # Phase 1: no-op — memory wired in Phase 2
        return AgentState.CHECK_TERMINATION

    def _check_termination(self, ctx: RunContext) -> AgentState:
        return self._termination.check(ctx)

    # ── Span metadata ────────────────────────────────────────────────────────────

    def _span_metadata(self, state: AgentState, ctx: RunContext) -> dict:
        if state == AgentState.CALL_LLM and ctx.last_llm_response:
            r = ctx.last_llm_response
            return {
                "model": self._model,
                "input_tokens": r.usage.input_tokens,
                "output_tokens": r.usage.output_tokens,
                "stop_reason": r.stop_reason,
                "total_cost_usd": round(ctx.budget_tracker.cost_usd, 6),
            }
        if state == AgentState.EXECUTE_TOOL:
            return {
                "tools_called": [r.tool_name for r in ctx.last_tool_results],
                "all_succeeded": all(r.success for r in ctx.last_tool_results),
            }
        return {}
