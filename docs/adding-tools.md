# Adding Tools

Tools are the bridge between the LLM and your actual systems — your database, your API, your internal service.

---

## The Pattern

One tool = one file. Every tool follows this exact structure:

```
my_tools/
  __init__.py
  order_lookup.py        ← one file per tool
  refund_request.py
  ticket_create.py
  escalate_to_human.py
  register.py            ← imports all tools, registers them at startup
```

Copy `tool_template.py` from the repo root for each new tool. Fill in four things:

1. **Input model** — what the LLM sends to your tool
2. **Output model** — what your tool sends back
3. **Function** — your real logic (DB call, API call, etc.)
4. **ToolDefinition** — metadata the engine uses to manage execution

---

## Full example — `order_lookup.py`

```python
from __future__ import annotations
from pydantic import BaseModel
from engine.tools.schemas import ToolDefinition

class OrderLookupInput(BaseModel):
    order_id: str

class OrderLookupOutput(BaseModel):
    order_id: str
    status: str           # "processing" | "shipped" | "delivered" | "cancelled"
    items: list[str]
    estimated_delivery: str | None

async def order_lookup_fn(input: OrderLookupInput) -> dict:
    # Replace with your actual data source
    result = await your_database.get_order(input.order_id)
    return {
        "order_id": input.order_id,
        "status": result["status"],
        "items": result["items"],
        "estimated_delivery": result.get("eta"),
    }

TOOL_DEFINITION = ToolDefinition(
    name="order_lookup",
    description=(
        "Look up the current status, items, and delivery estimate for a customer order. "
        "Use this when the user asks about an order, mentions an order number, or wants "
        "to know if something has shipped. Ask for the order_id if the user hasn't provided it."
    ),
    fn=order_lookup_fn,
    input_schema=OrderLookupInput,
    output_schema=OrderLookupOutput,
    timeout_seconds=10,
    max_retries=2,
    permission_level="read",
    on_error="return_structured_error",
)
```

---

## `register.py` — wire everything together

```python
from engine.api.dependencies import get_tool_registry
from my_tools.order_lookup import TOOL_DEFINITION as order_lookup
from my_tools.refund_request import TOOL_DEFINITION as refund_request
from my_tools.escalate_to_human import TOOL_DEFINITION as escalate

def register_all():
    registry = get_tool_registry()
    registry.register(order_lookup)
    registry.register(refund_request)
    registry.register(escalate)
```

Call `register_all()` once before starting the server. After that, tools are available for any agent to reference by name.

---

## Tool options explained

### `permission_level`
- `"read"` — tool only reads data. Default.
- `"write"` — tool modifies data (creates a refund, sends an email). Use for actions with side effects.
- `"escalate"` — calling this tool immediately ends the run and sets status to `"escalated"`. Use for human handoff.

### `on_error`
- `"return_structured_error"` — if your tool raises, the agent gets a structured error message and can try to recover. **Default — use this.**
- `"fail"` — if your tool raises, the entire run fails immediately. Use only when a failure is truly unrecoverable (e.g. a required auth service is down).

### `on_timeout`
- `"fail"` — run fails if your tool exceeds `timeout_seconds`. **Default.**
- `"skip"` — run continues without the tool result. Use for optional enrichment tools.

### `max_retries`
The engine retries your tool on transient failures (timeouts, empty results) up to this many times before giving up. Default: `2`.

---

## Testing a tool before wiring it into an agent

Once the server is running with your tools registered, test any tool directly:

```bash
curl -X POST http://localhost:8000/tools/order_lookup/test \
  -H "Content-Type: application/json" \
  -d '{"input": {"order_id": "ORD-789"}}'
```

Response:
```json
{
  "tool_name": "order_lookup",
  "success": true,
  "output": {"order_id": "ORD-789", "status": "delivered", ...},
  "error": null,
  "latency_ms": 45,
  "retries_used": 0
}
```

This calls your tool directly — no LLM, no agent, no memory. Use it to verify your function works before you write a single agent.

See what tools are registered at any time:

```bash
curl http://localhost:8000/tools
```

---

## Common mistakes

**Returning the Pydantic model instead of a dict:**
```python
# Wrong
return OrderLookupOutput(status="delivered", ...)

# Right
return {"status": "delivered", ...}
```

**Writing a description for other engineers:**
```
# Wrong — LLM won't know when to call this
"Looks up an order by ID"

# Right — LLM knows exactly when and how to use this
"Look up the status and delivery info for a customer order. Use this when
the user mentions an order number or asks where their package is."
```

See [tool-description-guide.md](tool-description-guide.md) for the full guide on writing good descriptions.

**Not making the function async:**
```python
# Wrong — will crash at runtime
def my_tool_fn(input: MyInput) -> dict:
    ...

# Right
async def my_tool_fn(input: MyInput) -> dict:
    ...
```

**Registering a tool that references an unknown tool name in an agent:**
The engine validates at `POST /agents` time — you'll get a 422 with a clear message listing what's registered.
