# Agent Execution Engine

> Production runtime infrastructure for LLM agents — explicit state-machine orchestration, typed tool execution, persistent memory, per-run trace observability, and automated evals. Self-hostable. No LangChain. No LangGraph.

[![CI](https://github.com/Ajayvardhanreddy/agent-execution-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/Ajayvardhanreddy/agent-execution-engine/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![uv](https://img.shields.io/badge/package%20manager-uv-purple)

---

## What This Is

This is not a chatbot. It is not a framework wrapper. It is not a tutorial project.

It is a **production runtime** for LLM agents — the same category of software as a process manager, a job queue, or a workflow engine, but purpose-built for agents that call tools, maintain memory, and need to be observable and recoverable when things go wrong.

The engine takes a structured `AgentRun` request (agent type, user input, available tools, budget limits), drives execution through an explicit 12-state state machine, and returns a structured `AgentRunResult` with a full trace of every decision made along the way.

**The three-layer portfolio this completes:**

| Layer | Project | What it does |
|---|---|---|
| Layer 1 | [distributed-kv-store](https://github.com/Ajayvardhanreddy/distributed-kv-store) | Fault-tolerant distributed KV storage |
| Layer 2 | [agent-memory-service](https://github.com/Ajayvardhanreddy/agent-memory-service) | Multi-namespace memory service backed by Layer 1 |
| **Layer 3** | **agent-execution-engine (this)** | Agent runtime on top of Layers 1 and 2 |

---

## Why Agent Execution Needs a Runtime

A raw while loop is the first thing every engineer writes when building an agent. It breaks in production for predictable reasons:

- **No state visibility** — you can't tell what the agent was doing when it failed
- **No failure recovery** — a tool timeout crashes the whole run
- **No budget enforcement** — a misbehaving agent burns your API budget silently
- **No loop detection** — agents get stuck calling the same tool forever
- **No memory** — every run starts from scratch, the agent can't recall prior context
- **No observability** — you can't replay a run to understand why the agent made a decision

This engine solves all of these. Every execution follows an explicit state machine. Every state transition is logged as a structured JSON span. Tools are typed contracts with timeout, retry, and validated input/output. Budget limits on steps, tokens, cost, and wall-clock time are enforced at every step. Memory persists across runs through Layer 2.

---

## Why Not LangGraph?

LangGraph is a mature framework with good documentation. The choice to build a custom orchestration layer comes down to a few concrete reasons:

**Full control over failure handling.** In LangGraph, failures surface through framework-level abstractions. Here, every failure mode is a modeled terminal state (`FAIL`, `ESCALATE`) with a specific `failure_reason` string. The behavior on tool timeout, memory unavailability, budget exhaustion, and loop detection is explicit code you can read, test in isolation, and change without touching the framework.

**Native integration with own storage.** The memory layer (Layer 2) and KV store (Layer 1) are custom-built distributed systems. Wiring them into a framework designed around its own state persistence adds an abstraction layer between the engine and the storage backend. Direct integration keeps the code readable and the data model obvious.

**Traceability as a first-class concern.** Every state transition in the custom state machine emits a typed `Span` with duration, metadata, and cost. This isn't bolted on — it's structural. In a framework, adding this level of observability requires fighting the framework's own logging and tracing mechanisms.

**Explainability.** Every line of the orchestration loop can be explained from first principles. When an interviewer asks "how does your agent handle a tool timeout?" — the answer is one file name and a few lines of code, not "it depends on the LangGraph version."

---

## Architecture

```
 ┌─────────────┐                     ┌────────────────────────────────────────────────┐
 │   Caller    │   AgentRun          │                  AgentEngine                   │
 │  (CLI/API)  │ ──────────────────▶ │                                                │
 └─────────────┘                     │  ┌──────────────────────────────────────────┐  │
                                     │  │              State Machine               │  │
                                     │  │                                          │  │
                                     │  │  START → LOAD_MEMORY → BUILD_CONTEXT     │  │
                                     │  │                              ↓            │  │
                                     │  │                         CALL_LLM ◀──┐    │  │
                                     │  │                              ↓       │    │  │
                                     │  │                     PROCESS_RESPONSE  │    │  │
                                     │  │                       ↙         ↘     │    │  │
                                     │  │              EXECUTE_TOOL      RESPOND ●   │  │
                                     │  │                   ↓          ESCALATE ●    │  │
                                     │  │            OBSERVE_RESULT      FAIL   ●    │  │
                                     │  │                   ↓                        │  │
                                     │  │            WRITE_MEMORY                    │  │
                                     │  │                   ↓                        │  │
                                     │  │           CHECK_TERMINATION ───────────────┘  │
                                     │  └──────────────────────────────────────────┘  │
                                     │        ↓                ↓              ↓        │
                                     │  ┌──────────┐   ┌───────────┐   ┌──────────┐  │
                                     │  │   Tool   │   │  Layer 2  │   │Anthropic │  │
                                     │  │ Registry │   │  Memory   │   │   LLM    │  │
                                     │  │ Executor │   │  Service  │   │   API    │  │
                                     │  └──────────┘   └───────────┘   └──────────┘  │
                                     │                                                │
                                     │  TraceCollector → one JSON Span per transition │
                                     └────────────────────────────────────────────────┘
                                                           ↓
                                                    AgentRunResult
                                           { status, final_answer, trace_id,
                                             steps_taken, tokens_used, cost_usd }
```

---

## Core Concepts

### AgentRun — the input contract

Every execution starts with a structured request:

```python
AgentRun(
    agent_id    = "support_agent",
    session_id  = "sess_abc123",
    user_id     = "user_456",
    input       = "I need a refund for order ORD-789.",
    tools       = ["order_lookup", "refund_request", "escalate_to_human"],
    system_prompt = "You are a customer support agent...",
    budget      = RunBudget(max_steps=15, max_tokens=10_000, max_cost_usd=0.50),
)
```

### State machine — the execution model

The agent never runs in a free-form loop. Every execution follows this exact state machine. Each arrow is a valid transition; invalid transitions raise immediately.

```
START → LOAD_MEMORY → BUILD_CONTEXT → CALL_LLM → PROCESS_RESPONSE
                                          ↑              ↓         ↘
                               CHECK_TERMINATION    EXECUTE_TOOL   RESPOND ●
                                          ↑              ↓         ↗
                                    WRITE_MEMORY  ← OBSERVE_RESULT     ESCALATE ●
                                                                        FAIL ●
```

Terminal states: `RESPOND`, `ESCALATE`, `FAIL`. Every non-terminal state emits a JSON span before transitioning.

### Tools — the typed contract

Every tool registered in the engine must provide:

```python
ToolDefinition(
    name             = "order_lookup",
    description      = "Look up an order by ID...",   # shown to the LLM
    input_schema     = OrderLookupInput,               # Pydantic model — validated before call
    output_schema    = OrderDetails,                   # Pydantic model — validated after call
    fn               = _order_lookup,                  # async callable
    timeout_seconds  = 5,
    max_retries      = 2,
    permission_level = "read",                         # read | write | escalate
    on_timeout       = "fail",                         # fail | escalate | skip
    on_error         = "return_structured_error",      # fail | escalate | return_structured_error
)
```

Tools never raise into the agent loop. Every call returns a `ToolResult` with `success`, `output`, `error`, `latency_ms`, and `retries_used`. Failures are structured and returned to the LLM as context, not exceptions.

### Memory — four namespaces

All memory goes through the [Layer 2 Memory Service](https://github.com/Ajayvardhanreddy/agent-memory-service) HTTP API. The engine uses four distinct namespaces:

| Namespace | Key convention | Contents | Lifetime |
|---|---|---|---|
| Session | `session:{session_id}` | Conversation history for this session | 24 hours |
| User | `user:{user_id}` | Persistent facts about the user across all sessions | 30 days |
| Working | `working:{run_id}` | Tool results for the current run | Run duration + 1h; deleted explicitly |
| Audit | `audit:{run_id}` | Immutable run record (status, cost, trace_id) | 90 days |

**Memory availability:** If Layer 2 returns 503 (KV store down), the engine fails fast with `status="failed"`. If Layer 2 is unreachable (not running), the engine degrades gracefully and runs without memory — useful for local development.

### Traces — observability contract

Every run produces one `Trace` stored in memory. Every state transition produces one `Span`:

```json
{
  "event": "span",
  "span_id": "sp_000004",
  "trace_id": "trace_ab70283be2e2",
  "step": 1,
  "from_state": "CALL_LLM",
  "to_state": "PROCESS_RESPONSE",
  "timestamp_ms": 1779340477548,
  "duration_ms": 1495,
  "metadata": {
    "model": "claude-haiku-4-5-20251001",
    "input_tokens": 1408,
    "output_tokens": 129,
    "stop_reason": "tool_use",
    "total_cost_usd": 0.001642
  }
}
```

### Budget — hard limits per run

```python
RunBudget(
    max_steps       = 15,    # maximum state machine iterations
    max_tokens      = 10000, # total tokens across all LLM calls
    max_cost_usd    = 0.50,  # maximum USD spend for this run
    timeout_seconds = 90,    # wall-clock timeout
)
```

Budget is checked at `CHECK_TERMINATION` after every tool round-trip. If any limit is hit, the run transitions to `FAIL` with `status="budget_exceeded"` or `status="timeout"`.

---

## Quickstart

**Prerequisites:** Python 3.11+, [uv](https://docs.astral.sh/uv/), an Anthropic API key.

```bash
git clone https://github.com/Ajayvardhanreddy/agent-execution-engine.git
cd agent-execution-engine

# Install dependencies
uv sync

# Set up environment
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY=your-key-here

# Run a demo scenario
PYTHONPATH=. uv run python demos/support_agent/agent.py --scenario eligible_refund

# Run all 7 scenarios
PYTHONPATH=. uv run python demos/support_agent/agent.py

# Run tests
uv run pytest
```

> **Docker Compose** (full stack with Layer 1 + Layer 2): wired up in Phase 6.
> Until then, run the engine directly as shown above.

---

## Demo 1: Customer Support Agent

**Location:** `demos/support_agent/`

An e-commerce customer support agent with 5 tools and 7 demo scenarios. Proves multi-turn tool execution, policy-grounded decisions, escalation logic, and retry on tool failure.

### Tools

| Tool | Permission | What it does |
|---|---|---|
| `order_lookup` | read | Look up order status, items, dates by order ID |
| `refund_policy_search` | read | Retrieve applicable policy for a given situation |
| `refund_request` | write | Submit a refund for an eligible order |
| `ticket_create` | write | Open a support ticket |
| `escalate_to_human` | **escalate** | Hand off to a human — triggers immediate `ESCALATE` state |

All tools are mocked with deterministic fixture data. No external dependencies.

### Scenarios

```bash
PYTHONPATH=. uv run python demos/support_agent/agent.py --scenario <name>
```

| Scenario | What it tests | Expected status |
|---|---|---|
| `eligible_refund` | Happy path: damaged item, refund approved | `completed` |
| `ineligible_refund` | Order outside 30-day window | `completed` |
| `missing_order_id` | Agent must ask for order ID before calling tools | `completed` |
| `frustrated_customer` | Angry user, valid claim — agent stays professional | `completed` |
| `tool_timeout_retry` | `order_lookup` times out once, succeeds on retry | `completed` |
| `policy_conflict_nonrefundable` | Digital product — non-refundable exception | `completed` |
| `fraud_risk_escalation` | High-value order + repeated claim → escalate | `escalated` |

### Sample run output

```
SCENARIO: eligible_refund
INPUT: Hi, I received my order ORD-789 last week and the item arrived damaged...

{"event":"span","from_state":"CALL_LLM","to_state":"PROCESS_RESPONSE","step":1,
 "duration_ms":1495,"metadata":{"input_tokens":1408,"stop_reason":"tool_use","total_cost_usd":0.0016}}

{"event":"span","from_state":"EXECUTE_TOOL","to_state":"OBSERVE_RESULT","step":1,
 "metadata":{"tools_called":["order_lookup","refund_policy_search"],"all_succeeded":true}}

{"event":"span","from_state":"CALL_LLM","to_state":"PROCESS_RESPONSE","step":3,
 "metadata":{"stop_reason":"end_turn","total_cost_usd":0.0064}}

RESULT
{
  "status": "completed",
  "final_answer": "Refund Approved ✓\n- Refund ID: REF-29637\n- Amount: $89.99\n- Timeline: 5 business days",
  "steps_taken": 3,
  "total_tokens_used": 5817,
  "total_cost_usd": 0.0064,
  "latency_ms": 5284
}
Match: ✓ PASS
```

### Phase 2 memory demo

Requires Layer 2 running on `localhost:8080`:

```bash
PYTHONPATH=. uv run python demos/support_agent/agent.py --memory-demo
```

Run 1: user introduces themselves as Alex → name stored in user memory.
Run 2: same user, new session → agent greets Alex by name without being told again.

---

## Demo 2: Engineering Assistant Agent

> **Status: Phase 5 — not yet built.** Placeholder directory exists at `demos/engineering_agent/`.

Will prove the same engine runs in a completely different domain. Tools: `github_issue_read`, `repo_file_search`, `code_context_retrieval`, `fix_plan_create`. Five scenarios: clear bug, missing context, large codebase, conflicting comments, test failure triage.

---

## Trace Replay

> **Status: Phase 3 — not yet built.**

Once built, the REST API will expose:

```bash
# Run the agent
curl -X POST http://localhost:9000/runs -d '{"agent_id":"support_agent",...}'
# → {"run_id":"run_abc","trace_id":"trace_xyz",...}

# Replay every decision
curl http://localhost:9000/traces/trace_xyz/replay
```

The replay endpoint returns an ordered, human-readable list of every state the agent visited, every tool call made, and every LLM decision with inputs, outputs, latency, and cost at each step.

---

## Eval Methodology

> **Status: Phase 4 — not yet built.**

Once built:

```bash
make eval AGENT=support_agent          # run 20 benchmark cases, emit regression report
make eval AGENT=engineering_agent      # run 10 benchmark cases
make eval-compare AGENT=support_agent PREV=reports/report_20260514.md
```

**Metrics measured:**

| Metric | What it measures |
|---|---|
| Task success | Did the agent complete the user's goal? |
| Tool correctness | Right tools in the right order? |
| Escalation accuracy | Escalated exactly when it should have? |
| Groundedness | Final answer based on tool outputs, not hallucination? |
| Step efficiency | Minimum necessary steps? |
| Cost per run | USD spent per execution |
| Latency | Wall-clock time to completion |
| Failure recovery | Tool failures handled gracefully? |

**Regression report format:**
```
Task success:        17/20  (85.0%)  [prev: 16/20  +1]
Tool correctness:    19/20  (95.0%)  [prev: 19/20   0]
Escalation accuracy: 17/20  (85.0%)  [prev: 15/20  +2]
Avg cost per run:    $0.038          [prev: $0.041 improved]

REGRESSIONS (1)
- case_012: task_success 1.0 → 0.0
  Reason: agent called refund_request before order_lookup
```

---

## Failure Modes

Every failure mode has explicit handling. None of them crash the engine or produce an infinite loop.

| Failure mode | Trigger | Engine behavior |
|---|---|---|
| Tool timeout | Tool exceeds `timeout_seconds` | `ToolError(error_type="timeout")`, retry up to `max_retries`, then `on_timeout` policy |
| Tool malformed output | Output fails Pydantic validation | `ToolError(error_type="validation_error")`, no retry, structured error returned to LLM |
| Tool empty result | Tool returns `None` or `{}` | `ToolError(error_type="empty_result", recoverable=True)`, LLM decides next step |
| Unknown tool called | LLM calls unregistered tool name | Error message injected: `"Tool X is not available. Available: [...]"` |
| Duplicate tool call | Same tool + same input called twice | Loop guard injects: `"You already called this tool. Use a different approach."` |
| Context window overflow | Token budget approaching limit | Compressor trims oldest messages, preserves last 6 + original user message |
| Budget exceeded | Steps / tokens / cost / time limit hit | `FAIL` with `status="budget_exceeded"` or `status="timeout"` |
| Memory service down (503) | Layer 2 returns 503 | `FAIL` with `failure_reason="memory_unavailable"` — do not continue |
| Memory service unreachable | Layer 2 not running | Degrade gracefully — run without memory (dev mode) |
| LLM API error | Anthropic returns 5xx | Retry up to 3× with exponential backoff, then `FAIL` |
| Infinite loop detected | Same state sequence repeats 3× | Loop guard forces `FAIL` with `failure_reason="Infinite loop detected"` |
| Escalation required | Tool with `permission_level="escalate"` called | Immediate `ESCALATE` from `EXECUTE_TOOL`, bypasses `CHECK_TERMINATION` |

---

## MCP Integration

> **Status: Phase 6 — not yet built.**

Once built, Claude Desktop can run agents and replay traces directly:

```json
{
  "mcpServers": {
    "agent-execution-engine": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/path/to/agent-execution-engine"
    }
  }
}
```

Exposed tools: `run_agent`, `get_trace`, `replay_trace`, `run_eval`, `list_tools`.

---

## Layer Integration

The engine is the top layer of a three-layer AI infrastructure stack. Every layer is independently deployable and tested.

```
┌─────────────────────────────────┐
│   Layer 3: Agent Execution      │  ← this repo
│   Engine (port 9000)            │
│   Orchestration, tools, evals   │
└─────────────┬───────────────────┘
              │ HTTP (localhost:8080)
              ▼
┌─────────────────────────────────┐
│   Layer 2: Agent Memory         │  github.com/Ajayvardhanreddy/agent-memory-service
│   Service (port 8080)           │
│   4 memory namespaces, streams  │
└─────────────┬───────────────────┘
              │ internal
              ▼
┌─────────────────────────────────┐
│   Layer 1: Distributed KV       │  github.com/Ajayvardhanreddy/distributed-kv-store
│   Store (ports 8000–8002)       │
│   Consistent hashing, failover  │
└─────────────────────────────────┘
```

---

## Build Status

| Phase | What | Status |
|---|---|---|
| Phase 1 | Orchestrator, state machine, tool execution, support agent demo | ✅ Complete |
| Phase 2 | Memory integration (session, user, working, audit) | ✅ Complete |
| Phase 3 | REST API, trace replay, Prometheus metrics | 🔲 Not started |
| Phase 4 | Eval harness, 6 scorers, 30 benchmark cases, regression reports | 🔲 Not started |
| Phase 5 | Engineering assistant agent demo | 🔲 Not started |
| Phase 6 | MCP server, Docker Compose full stack | 🔲 Not started |

---

## Architectural Decision Records

Written as each phase is stabilised:

| ADR | Decision |
|---|---|
| [001](docs/decisions/001-custom-orchestration-over-langgraph.md) | Custom orchestration over LangGraph |
| [002](docs/decisions/002-anthropic-sdk-direct-over-langchain.md) | Anthropic SDK direct over LangChain |
| [003](docs/decisions/003-state-machine-over-while-loop.md) | Explicit state machine over while loop |
| [004](docs/decisions/004-typed-tool-registry.md) | Typed tool registry with Pydantic |
| [005](docs/decisions/005-eval-methodology.md) | Structured eval methodology |

> ADR documents are written as phases complete. Pending Phase 1 + 2 stabilisation.

---

## Known Limitations

| Limitation | Notes |
|---|---|
| No REST API yet | Engine is runnable via Python only until Phase 3 |
| No eval scoring yet | Eval harness built in Phase 4 |
| No MCP server yet | Claude Desktop integration in Phase 6 |
| Docker Compose not wired | Skeletons exist; full stack in Phase 6 |
| Tools are mocked | Support agent uses fixture data, no real order database |
| No auth on any endpoint | By design for portfolio; production would add API key auth |
| Single-node memory in dev mode | When Layer 2 is unavailable, no memory persistence |
| User fact extraction is regex-only | Name patterns only; no LLM-based extraction yet |
| No streaming responses | All runs are synchronous; streaming added in Phase 3 |

---

## Roadmap

Phases 3–6 in order:

**Phase 3 — REST API + Trace Replay**
`POST /runs`, `GET /runs/{id}`, `GET /traces/{id}/replay`, `GET /metrics` (Prometheus). Full trace reconstructed as human-readable ordered event list.

**Phase 4 — Eval Harness**
`make eval AGENT=support_agent`. 6 scorers (task success, tool correctness, escalation, groundedness, cost, latency). 30 benchmark cases. Regression report with diff from previous run.

**Phase 5 — Engineering Assistant Agent**
Same engine, different domain. 4 tools (GitHub issue read, repo file search, code context retrieval, fix plan creation). 5 scenarios. 10 eval cases.

**Phase 6 — MCP Server + Docker Compose**
FastMCP server exposing engine as 5 MCP tools. `docker-compose up` brings up all three layers in one command.

---

## Tech Stack

| Concern | Choice |
|---|---|
| Language | Python 3.11+ |
| LLM | Anthropic SDK (direct — no LangChain) |
| API framework | FastAPI + Uvicorn (Phase 3) |
| Data validation | Pydantic v2 |
| Memory backend | Layer 2 Memory Service (HTTP) |
| KV backend | Layer 1 Distributed KV Store |
| HTTP client | httpx (async) |
| MCP server | fastmcp (Phase 6) |
| Testing | pytest + pytest-asyncio + pytest-httpx |
| Package manager | uv |
| Observability | Structured JSON spans, Prometheus metrics (Phase 3) |
