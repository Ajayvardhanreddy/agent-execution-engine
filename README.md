# Agent Execution Engine

> Production runtime infrastructure for LLM agents — explicit state-machine orchestration, typed tool execution, persistent memory, per-run observability, automated evals, and MCP integration. Self-hostable. No LangChain. No LangGraph.

[![CI](https://github.com/Ajayvardhanreddy/agent-execution-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/Ajayvardhanreddy/agent-execution-engine/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![Tests](https://img.shields.io/badge/tests-140%20passing-brightgreen)
![uv](https://img.shields.io/badge/package%20manager-uv-purple)

---

> **Part of a 3-layer AI infrastructure portfolio.**
> This is Layer 3. The full stack — all three layers running together as a distributed system — is being assembled in a separate deployment repo.
>
> | Layer | Repo | What it does |
> |---|---|---|
> | Layer 1 | [distributed-kv-store](https://github.com/Ajayvardhanreddy/distributed-kv-store) | Fault-tolerant distributed KV storage with consistent hashing and node failover |
> | Layer 2 | [agent-memory-service](https://github.com/Ajayvardhanreddy/agent-memory-service) | Multi-namespace memory service (session, user, working, audit) backed by Layer 1 |
> | **Layer 3** | **agent-execution-engine (this)** | Agent runtime — orchestration, tool execution, memory, observability, evals, MCP |

---

## What This Is

This is not a chatbot. It is not a framework wrapper. It is not a tutorial project.

It is a **production runtime** for LLM agents — the same category of software as a process manager, a job queue, or a workflow engine, but purpose-built for agents that call tools, maintain memory, and need to be observable and recoverable when things go wrong.

The engine takes a structured request (agent ID, user input), looks up the agent's configuration from a server-side registry, drives execution through an explicit 12-state state machine, and returns a structured result with a full trace of every decision made along the way.

---

## Architecture

### Full Three-Layer Stack

```
  ┌─────────────────────────────────────────────────────────────────────┐
  │                         Client Layer                                │
  │                                                                     │
  │   Web UI / Mobile App         Claude Code (via MCP)                 │
  │   POST /runs  ─────────────▶  run_agent tool  ──────────────────┐  │
  └────────────────────────────────────────────────────────────────--|--┘
                                                                     │
  ┌──────────────────────────────────────────────────────────────────▼──┐
  │                    Layer 3 — Agent Execution Engine                 │
  │                         github.com/Ajayvardhanreddy/               │
  │                         agent-execution-engine  (this)             │
  │                                                                     │
  │  ┌────────────────┐   ┌─────────────────────────────────────────┐  │
  │  │  REST API      │   │           State Machine                 │  │
  │  │  FastAPI :9000 │   │                                         │  │
  │  │                │   │  START → LOAD_MEMORY → BUILD_CONTEXT    │  │
  │  │  POST /runs    │   │                            ↓            │  │
  │  │  GET  /agents  │   │                        CALL_LLM ◀──┐   │  │
  │  │  GET  /tools   │   │                            ↓        │   │  │
  │  │  GET  /traces  │   │                   PROCESS_RESPONSE  │   │  │
  │  │  GET  /metrics │   │                    ↙           ↘     │   │  │
  │  └────────────────┘   │            EXECUTE_TOOL      RESPOND ●  │  │
  │                        │                 ↓          ESCALATE ●  │  │
  │  ┌────────────────┐   │          OBSERVE_RESULT      FAIL   ●  │  │
  │  │  MCP Server    │   │                 ↓                       │  │
  │  │  FastMCP :9001 │   │          WRITE_MEMORY                   │  │
  │  │                │   │                 ↓                       │  │
  │  │  run_agent     │   │         CHECK_TERMINATION ──────────────┘  │
  │  │  list_agents   │   └─────────────────────────────────────────┘  │
  │  └────────────────┘                                                 │
  │                                                                     │
  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
  │  │ToolRegistry  │  │AgentRegistry │  │   TraceCollector         │  │
  │  │Pydantic I/O  │  │Server-side   │  │   One JSON span per      │  │
  │  │Timeout/Retry │  │agent configs │  │   state transition       │  │
  │  └──────────────┘  └──────────────┘  └──────────────────────────┘  │
  └───────────────────────────────┬─────────────────────────────────────┘
                                  │ HTTP (MEMORY_SERVICE_URL)
  ┌───────────────────────────────▼─────────────────────────────────────┐
  │                    Layer 2 — Agent Memory Service                   │
  │              github.com/Ajayvardhanreddy/agent-memory-service       │
  │                                                                     │
  │   session:{id}   user:{id}   working:{run_id}   audit:{run_id}      │
  │   24h TTL        30d TTL     run duration + 1h  90d immutable       │
  └───────────────────────────────┬─────────────────────────────────────┘
                                  │ HTTP (internal)
  ┌───────────────────────────────▼─────────────────────────────────────┐
  │                    Layer 1 — Distributed KV Store                   │
  │              github.com/Ajayvardhanreddy/distributed-kv-store       │
  │                                                                     │
  │   Node 0 :8000    Node 1 :8001    Node 2 :8002                      │
  │   Consistent hashing · Replication · Automatic failover             │
  └─────────────────────────────────────────────────────────────────────┘
```

### Request Flow (end to end)

```
1.  Client sends:  POST /runs  { agent_id, session_id, user_id, input }
2.  API layer:     Looks up AgentDefinition from AgentRegistry
3.  Engine:        START → LOAD_MEMORY
4.  Layer 2:       Returns session history + user facts for this user
5.  Layer 1:       Serves the KV reads behind Layer 2
6.  Engine:        BUILD_CONTEXT → CALL_LLM
7.  Anthropic API: Returns tool_use or end_turn
8.  Engine:        PROCESS_RESPONSE → EXECUTE_TOOL
9.  Tool:          Runs with Pydantic-validated input, timeout, retry
10. Engine:        OBSERVE_RESULT → WRITE_MEMORY
11. Layer 2:       Appends tool result to working memory
12. Engine:        CHECK_TERMINATION → (loop or RESPOND)
13. Engine:        WRITE_MEMORY (final answer) → RESPOND
14. Client gets:   { status, final_answer, trace_id, steps, tokens, cost, latency }
```

---

## Why Not LangChain or LangGraph?

**Full control over failure handling.** Every failure mode is a modeled terminal state (`FAIL`, `ESCALATE`) with a specific `failure_reason`. The behavior on tool timeout, budget exhaustion, memory unavailability, and loop detection is explicit code you can read, test in isolation, and change without touching a framework.

**Native integration with own storage.** [Layer 2](https://github.com/Ajayvardhanreddy/agent-memory-service) and [Layer 1](https://github.com/Ajayvardhanreddy/distributed-kv-store) are custom-built distributed systems. Wiring them into a framework designed around its own state persistence adds an abstraction layer between the engine and the storage backend.

**Traceability as a first-class concern.** Every state transition emits a typed `Span` with duration, metadata, and cost. This is structural — not bolted on. In a framework, this level of observability requires fighting the framework's own logging mechanisms.

**Explainability.** Every line of the orchestration loop can be explained from first principles. When an interviewer asks "how does your agent handle a tool timeout?" — the answer is one file name and a few lines of code.

---

## Quickstart

**Prerequisites:** Python 3.11+, [uv](https://docs.astral.sh/uv/), Anthropic API key.

```bash
git clone https://github.com/Ajayvardhanreddy/agent-execution-engine.git
cd agent-execution-engine

uv sync
cp .env.example .env
# Set ANTHROPIC_API_KEY in .env

# Run the support agent demo
make demo

# Run the engineering agent demo
make demo-eng

# Start the REST API (auto-registers both agents on startup)
make serve          # http://localhost:9000

# Run tests
make test           # 140 tests

# Run evals (makes real LLM calls — costs money)
make eval           # 20 support benchmark cases
make eval-engineering  # 10 engineering benchmark cases
```

### Docker (Layer 3 only)

```bash
cp .env.example .env   # set ANTHROPIC_API_KEY

docker compose up
# Engine API:  http://localhost:9000
# MCP Server:  http://localhost:9001  (SSE transport)
```

---

## Core Concepts

### AgentRegistry — server-side configuration

Agents are registered once server-side. Callers send only `agent_id + input` — they never control system prompts, tools, or budgets.

```python
# Registered at startup (engine/api/app.py)
AgentDefinition(
    agent_id      = "support_agent",
    description   = "Customer support for ShopEasy",
    system_prompt = "...",
    tools         = ["order_lookup", "refund_request", "escalate_to_human"],
    default_budget = RunBudget(max_steps=10, max_tokens=8_000, max_cost_usd=0.30),
)

# Caller sends:
POST /runs  { "agent_id": "support_agent", "session_id": "...", "user_id": "...", "input": "..." }
```

This is analogous to how AWS Lambda separates function configuration from invocation — the caller triggers execution but cannot redefine it.

### State Machine — the execution model

Every run follows this exact state machine. Invalid transitions raise immediately.

```
START → LOAD_MEMORY → BUILD_CONTEXT → CALL_LLM → PROCESS_RESPONSE
                                           ↑              ↓          ↘
                                  CHECK_TERMINATION  EXECUTE_TOOL   RESPOND ●
                                           ↑              ↓          ↗
                                     WRITE_MEMORY ← OBSERVE_RESULT     ESCALATE ●
                                                                        FAIL ●
```

Terminal states: `RESPOND`, `ESCALATE`, `FAIL`. Every non-terminal state emits a JSON span before transitioning.

### ToolRegistry — typed contracts

Every tool is a typed contract with validated input/output, timeout, retry, and explicit error policy.

```python
ToolDefinition(
    name             = "order_lookup",
    description      = "Look up an order by ID. Returns status, items, dates.",
    input_schema     = OrderLookupInput,    # Pydantic — validated before call
    output_schema    = OrderDetails,         # Pydantic — validated after call
    fn               = _order_lookup,        # async callable
    timeout_seconds  = 5,
    max_retries      = 2,
    on_timeout       = "fail",               # fail | escalate | skip
    on_error         = "return_structured_error",
)
```

Tools never raise into the agent loop. Every call returns a `ToolResult` — failures are structured and returned to the LLM as context, not exceptions.

### Memory — four namespaces via [Layer 2](https://github.com/Ajayvardhanreddy/agent-memory-service)

| Namespace | Key | Contents | Lifetime |
|---|---|---|---|
| Session | `session:{session_id}` | Conversation history for this session | 24h |
| User | `user:{user_id}` | Persistent facts across all sessions | 30 days |
| Working | `working:{run_id}` | Tool results for the current run | Run + 1h |
| Audit | `audit:{run_id}` | Immutable run record | 90 days |

Layer 2 writes these to [Layer 1](https://github.com/Ajayvardhanreddy/distributed-kv-store) — the distributed KV store with consistent hashing and automatic failover.

**Memory failure modes:** 503 from Layer 2 → `FAIL` immediately. Layer 2 unreachable → graceful degrade (run without memory, useful for local dev).

### Traces — per-step observability

Every state transition produces one JSON span:

```json
{
  "span_id": "sp_000004",
  "trace_id": "trace_ab70283be2e2",
  "step": 2,
  "from_state": "CALL_LLM",
  "to_state": "PROCESS_RESPONSE",
  "duration_ms": 1495,
  "metadata": {
    "model": "claude-haiku-4-5-20251001",
    "input_tokens": 1408,
    "output_tokens": 129,
    "stop_reason": "tool_use",
    "total_cost_usd": 0.0016
  }
}
```

Replay any run step-by-step:

```bash
GET /traces/{trace_id}/replay
```

### Budget — hard limits per run

```python
RunBudget(
    max_steps       = 10,    # state machine iterations
    max_tokens      = 8_000, # total tokens across all LLM calls
    max_cost_usd    = 0.30,  # maximum USD spend
    timeout_seconds = 120,   # wall-clock timeout
)
```

Enforced at `CHECK_TERMINATION` after every tool round-trip. Any limit hit → `FAIL` with `status="budget_exceeded"`.

---

## REST API

```
POST   /runs                      Submit a run (agent_id + session_id + user_id + input)
GET    /runs/{run_id}             Get a completed run result

GET    /agents                    List registered agents (summary)
GET    /agents/{agent_id}         Full agent definition
POST   /agents                    Register a new agent
PUT    /agents/{agent_id}         Update agent definition
DELETE /agents/{agent_id}         Remove agent

GET    /tools                     List all registered tools with JSON schemas
GET    /tools/{name}              One tool schema
POST   /tools/{name}/test         Run a tool directly with test input

GET    /traces/{trace_id}         Raw trace
GET    /traces/{trace_id}/replay  Step-by-step replay

GET    /health                    Liveness probe
GET    /ready                     Readiness probe (checks Layer 2)
GET    /metrics                   Prometheus metrics
```

Interactive docs at `http://localhost:9000/docs` when the server is running.

---

## MCP Integration

The engine ships an MCP server — any MCP-compatible AI client can discover and call agents without writing integration code.

### Claude Code (stdio — local dev)

The repo includes `.mcp.json` — Claude Code picks it up automatically:

```bash
make serve   # engine on :9000
# restart Claude Code in this directory
```

Then in Claude Code:
```
List the available agents.
Use the support agent to check order ORD-789 for user u-001.
```

Claude Code calls `list_agents` and `run_agent` via your MCP server — no curl, no integration code.

### Docker (SSE — remote clients)

```bash
docker compose up
# MCP server on :9001 with SSE transport
```

Connect any SSE-capable MCP client to `http://localhost:9001/sse`.

See [docs/mcp-setup.md](docs/mcp-setup.md) for Claude Desktop config.

---

## Demo Agents

### Demo 1 — Customer Support Agent

**Location:** `demos/support_agent/`

Five tools, seven scenarios, 20 benchmark eval cases. Proves multi-turn tool execution, policy-grounded decisions, escalation logic, retry on tool failure, and cross-session memory.

| Tool | What it does |
|---|---|
| `order_lookup` | Look up order status, items, and dates |
| `refund_policy_search` | Retrieve applicable refund policy |
| `refund_request` | Submit a refund for an eligible order |
| `ticket_create` | Open a support ticket |
| `escalate_to_human` | Hand off to human — triggers `ESCALATE` state immediately |

```bash
make demo                                                    # eligible_refund scenario
PYTHONPATH=. uv run python demos/support_agent/agent.py --list   # all scenarios
PYTHONPATH=. uv run python demos/support_agent/agent.py --scenario fraud_risk_escalation
```

| Scenario | Tests | Expected |
|---|---|---|
| `eligible_refund` | Happy path — damaged item, refund approved | `completed` |
| `ineligible_refund` | Order outside 30-day window | `completed` |
| `missing_order_id` | Agent asks for order ID before calling tools | `completed` |
| `frustrated_customer` | Angry user, valid claim | `completed` |
| `tool_timeout_retry` | `order_lookup` times out once, succeeds on retry | `completed` |
| `policy_conflict_nonrefundable` | Digital product — non-refundable exception | `completed` |
| `fraud_risk_escalation` | High-value order + repeated claim → escalate | `escalated` |

### Demo 2 — Engineering Assistant Agent

**Location:** `demos/engineering_agent/`

Four tools, five scenarios, 10 benchmark eval cases. Same engine, completely different domain — proves the runtime is domain-agnostic.

| Tool | What it does |
|---|---|
| `code_search` | Search codebase for functions, classes, patterns |
| `file_read` | Read a specific file by path |
| `pr_review` | Review a pull request for bugs, security issues, style |
| `dependency_check` | Audit dependencies for outdated versions and CVEs |

```bash
make demo-eng                                                        # review_pr scenario
PYTHONPATH=. uv run python demos/engineering_agent/agent.py --list  # all scenarios
PYTHONPATH=. uv run python demos/engineering_agent/agent.py --scenario security_investigation
```

| Scenario | Tests | Expected |
|---|---|---|
| `find_function` | Locate function definition across codebase | `completed` |
| `review_pr` | PR-42 has critical timing-attack — must be called out | `completed` |
| `dependency_audit` | cryptography CRITICAL CVE must be surfaced | `completed` |
| `inspect_file` | Read and explain a source file | `completed` |
| `security_investigation` | Multi-step: find SQL injection, then read vulnerable file | `completed` |

---

## Eval Harness

30 benchmark conversations scored across 6 weighted dimensions with hard-fail semantics for safety-critical cases.

```bash
make eval              # 20 support cases
make eval-engineering  # 10 engineering cases
make eval-all          # all 30 cases
make eval-case CASE=support_005   # single case
```

| Scorer | Weight | Hard fail? | What it measures |
|---|---|---|---|
| `task_completion` | 2.0 | Yes | Did the run reach the expected terminal state? |
| `tool_selection` | 1.5 | No | Right tools called, no unexpected tools? |
| `answer_quality` | 1.5 | No | Required keywords present, forbidden terms absent? |
| `escalation_accuracy` | 1.5 | Yes | Escalated when required? False negative = security failure |
| `cost_efficiency` | 0.5 | No | Cost within the case budget? |
| `latency` | 0.5 | No | Response within latency threshold? |

**Hard-fail semantics:** If a case misses a required escalation (e.g. fraud scenario completed instead of escalating), it auto-fails regardless of other scores. A false negative on escalation is a security failure — weighted average alone cannot pass it.

Pass threshold: **0.70** overall weighted score.

---

## Failure Modes

Every failure mode is modeled. None crash the engine or produce an infinite loop.

| Failure | Trigger | Behavior |
|---|---|---|
| Tool timeout | Exceeds `timeout_seconds` | Retry up to `max_retries`, then apply `on_timeout` policy |
| Malformed tool output | Fails Pydantic validation | Structured error returned to LLM — no retry |
| Empty tool result | Returns `None` or `{}` | Recoverable error — LLM decides next step |
| Unknown tool called | LLM calls unregistered name | `"Tool X not available. Available: [...]"` injected |
| Duplicate tool call | Same tool + input called twice | Loop guard injects alternative approach hint |
| Context overflow | Token budget approaching limit | Compressor trims oldest messages, preserves last 6 + original |
| Budget exceeded | Steps / tokens / cost / time | `FAIL` with `status="budget_exceeded"` or `"timeout"` |
| Infinite loop | Same state sequence 3× | Loop guard forces `FAIL` |
| Layer 2 down (503) | Memory service returns 503 | `FAIL` — do not continue without memory |
| Layer 2 unreachable | Not running | Graceful degrade — run without memory (dev mode) |
| LLM API error | Anthropic 5xx | Retry 3× with exponential backoff, then `FAIL` |
| Escalation triggered | Tool with `permission_level="escalate"` | Immediate `ESCALATE` from `EXECUTE_TOOL` |

---

## Tech Stack

| Concern | Choice |
|---|---|
| Language | Python 3.11+ |
| LLM | Anthropic SDK — direct, no framework |
| API | FastAPI + Uvicorn |
| Validation | Pydantic v2 |
| MCP server | FastMCP |
| Memory backend | [Layer 2 — agent-memory-service](https://github.com/Ajayvardhanreddy/agent-memory-service) |
| KV backend | [Layer 1 — distributed-kv-store](https://github.com/Ajayvardhanreddy/distributed-kv-store) |
| HTTP client | httpx (async) |
| Observability | Structured JSON spans + Prometheus metrics |
| Testing | pytest + pytest-asyncio + pytest-httpx |
| Package manager | uv |
| Containerisation | Docker + Docker Compose |

---

## Project Structure

```
engine/
  api/           REST API — routes, agent registry, dependencies, middleware
  evals/         Eval framework — base contracts, 6 scorers, EvalSuite
  memory/        Layer 2 client — 4 namespaces, graceful degrade
  mcp/           MCP server — run_agent, list_agents, stdio + SSE
  observability/ Trace collection, Prometheus metrics
  orchestrator/  State machine, engine loop, step runner, loop guard, budget
  tools/         ToolDefinition, ToolRegistry, ToolExecutor, error types

demos/
  support_agent/    5 tools, 7 scenarios, system prompt
  engineering_agent/ 4 tools, 5 scenarios, system prompt

evals/
  dataset/       30 benchmark EvalCases (support + engineering)
  reports/       JSON regression reports (gitignored)
  runner.py      CLI runner — --suite, --case, --no-save
  report.py      Terminal output + JSON report formatter

docs/
  mcp-setup.md         Claude Code + Docker MCP setup guide
  adding-tools.md      How to write and register custom tools
  registering-agents.md How to register agents via the API
  tool_template.py     Copy-paste starting point for tool authors

tests/
  unit/          State machine, scorers, registry, executor, budget, traces
  integration/   API routes, MCP server, memory client
```

---

## Build Status

All 6 phases complete.

| Phase | What | Status |
|---|---|---|
| Phase 1 | State machine, tool execution, budget, loop detection, support agent demo | ✅ |
| Phase 2 | Memory integration — session, user, working, audit namespaces | ✅ |
| Phase 3 | REST API, AgentRegistry, trace replay, Prometheus metrics | ✅ |
| Phase 4 | Eval harness — 6 scorers, hard-fail semantics, 20 support cases, regression reports | ✅ |
| Phase 5 | Engineering agent — 4 tools, 5 scenarios, 10 eval cases | ✅ |
| Phase 6 | MCP server, Docker Compose, Claude Code `.mcp.json`, startup agent registration | ✅ |
