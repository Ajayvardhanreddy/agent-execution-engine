from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel

from engine.context.budget import BudgetTracker
from engine.memory.audit_memory import AuditMemory

# Memory types — imported lazily to avoid circular imports at module load
# (memory modules import client which imports os/httpx; safe to import here)
from engine.memory.session_memory import SessionMemory
from engine.memory.user_memory import UserMemory
from engine.memory.working_memory import WorkingMemory
from engine.observability.traces import TraceCollector
from engine.tools.schemas import ToolResult

# ── Public request / response contracts ───────────────────────────────────────

class RunBudget(BaseModel):
    max_steps: int = 15
    max_tokens: int = 10_000
    max_cost_usd: float = 0.50
    timeout_seconds: int = 90


class AgentDefinition(BaseModel):
    """Server-side agent configuration registered once by the engineering team."""
    agent_id: str
    description: str
    system_prompt: str
    tools: list[str]            # names of tools from the ToolRegistry this agent may call
    default_budget: RunBudget = RunBudget()
    created_at: str = ""        # ISO timestamp — set by AgentRegistry.register()


class RunRequest(BaseModel):
    """Lean public API request — callers send only runtime variables."""
    agent_id: str
    session_id: str
    user_id: str
    input: str
    budget_override: RunBudget | None = None   # tighten limits for this run only


class AgentRun(BaseModel):
    """Internal model — built by the API layer after looking up AgentDefinition."""
    agent_id: str
    session_id: str
    user_id: str
    input: str
    tools: list[str]
    system_prompt: str
    budget: RunBudget = RunBudget()
    eval_on_completion: bool = False


class AgentRunResult(BaseModel):
    run_id: str
    status: Literal["completed", "escalated", "failed", "budget_exceeded", "timeout"]
    final_answer: str | None
    trace_id: str
    steps_taken: int
    total_tokens_used: int
    total_cost_usd: float
    latency_ms: int
    eval_summary: dict[str, Any] | None = None
    failure_reason: str | None = None


# ── Internal mutable run state ─────────────────────────────────────────────────

@dataclass
class RunContext:
    run: AgentRun
    run_id: str
    trace_id: str
    budget_tracker: BudgetTracker
    trace_collector: TraceCollector

    # Conversation history sent to the LLM
    messages: list[dict[str, Any]] = field(default_factory=list)

    # Set in PROCESS_RESPONSE, consumed in EXECUTE_TOOL
    pending_tool_calls: list[Any] = field(default_factory=list)   # list[ToolUseBlock]

    # Accumulated tool results for the current step
    last_tool_results: list[ToolResult] = field(default_factory=list)

    # Raw Anthropic response from the last CALL_LLM
    last_llm_response: Any = None

    # Terminal state outputs
    final_answer: str | None = None
    failure_reason: str | None = None
    escalation_reason: str | None = None

    # Set by EXECUTE_TOOL when a tool with permission_level="escalate" is called
    force_escalate: bool = False

    # Loop and duplicate-call tracking
    state_history: list[str] = field(default_factory=list)
    seen_tool_calls: set[str] = field(default_factory=set)

    # Memory objects (injected by AgentEngine, used by StepRunner)
    session_memory: SessionMemory | None = None
    user_memory: UserMemory | None = None
    working_memory: WorkingMemory | None = None
    audit_memory: AuditMemory | None = None

    # User facts loaded from user memory at LOAD_MEMORY
    # Injected into the system prompt by ContextBuilder
    user_facts: list[str] = field(default_factory=list)
