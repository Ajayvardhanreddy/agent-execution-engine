# Quickstart — Running Your First Agent in 5 Steps

You should have a working agent calling your own tools within 30 minutes.

---

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) installed
- An Anthropic API key

---

## Step 1 — Install

```bash
git clone https://github.com/Ajayvardhanreddy/agent-execution-engine
cd agent-execution-engine
uv sync
cp .env.example .env
# Edit .env — add your ANTHROPIC_API_KEY
```

---

## Step 2 — Write your first tool

Copy the template and fill it in:

```bash
cp docs/tool_template.py my_tools/order_lookup.py
```

Edit `my_tools/order_lookup.py`. Replace the input/output models and function body with your real logic. The only rule: the function must be `async` and return a plain `dict`.

See [adding-tools.md](adding-tools.md) for the full pattern and [tool-description-guide.md](tool-description-guide.md) for how to write good tool descriptions.

---

## Step 3 — Register your tools at startup

Create `my_tools/register.py`:

```python
from engine.api.dependencies import get_tool_registry
from my_tools.order_lookup import TOOL_DEFINITION as order_lookup

def register_all():
    registry = get_tool_registry()
    registry.register(order_lookup)
    # registry.register(another_tool)
```

Then add a startup call in your entry point (or call it before starting the server):

```python
from my_tools.register import register_all
register_all()
```

Alternatively, test the full demo that ships with the engine:

```bash
# The demo registers its own tools — no setup needed
PYTHONPATH=. uv run python demos/support_agent/agent.py --scenario eligible_refund
```

---

## Step 4 — Start the server

```bash
uv run uvicorn engine.api.app:app --reload
```

Check it's alive:

```bash
curl http://localhost:8000/health
# {"status":"ok","version":"0.1.0"}

curl http://localhost:8000/tools
# [] — empty until you register tools at startup
```

---

## Step 5 — Register an agent and run it

**Register your agent once** (engineering team, one-time setup):

```bash
curl -X POST http://localhost:8000/agents \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "support_agent",
    "description": "Customer support agent for ShopEasy",
    "system_prompt": "You are a helpful support agent. Help customers with orders and refunds. Be concise and friendly.",
    "tools": ["order_lookup"],
    "default_budget": {
      "max_steps": 10,
      "max_tokens": 5000,
      "max_cost_usd": 0.25,
      "timeout_seconds": 60
    }
  }'
```

**Submit a run** (your application, every user message):

```bash
curl -X POST http://localhost:8000/runs \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "support_agent",
    "session_id": "sess_abc123",
    "user_id": "user_456",
    "input": "Where is my order ORD-789?"
  }'
```

**Inspect the trace** (debugging):

```bash
curl http://localhost:8000/traces/{trace_id}/replay
```

---

## What runs in the background automatically

Once you've done Steps 3–5, the engine handles:

- **Memory** — session history, user facts, working memory, audit records (if Layer 2 is running)
- **Budget** — kills runs that exceed step/token/cost/time limits
- **Retries** — transient tool failures are retried automatically
- **Loop detection** — duplicate tool calls and state cycles are caught
- **Traces** — every state transition is recorded with timing

You write the tool. The engine handles the rest.

---

## Next steps

- [adding-tools.md](adding-tools.md) — full tool authoring guide
- [registering-agents.md](registering-agents.md) — agent registration walkthrough
- [tool-description-guide.md](tool-description-guide.md) — how to write descriptions the LLM understands
