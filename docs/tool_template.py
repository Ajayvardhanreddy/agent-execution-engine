"""
Tool Template — copy this file, fill in the four sections, register.

One tool = one file. Keep this pattern and your tools/ folder stays clean.

Quick checklist:
  [ ] Replace MyToolInput fields with your actual inputs
  [ ] Replace MyToolOutput fields with what your tool returns
  [ ] Replace my_tool_fn body with your real logic (DB call, API call, etc.)
  [ ] Fill in the ToolDefinition fields
  [ ] Import and register in your tools/register.py
"""
from __future__ import annotations

import asyncio

from pydantic import BaseModel

from engine.tools.schemas import ToolDefinition


# ── Step 1: Define what goes IN ───────────────────────────────────────────────
# Every field here is validated before your function is called.
# The LLM fills these fields — name them clearly.

class MyToolInput(BaseModel):
    order_id: str           # replace with your actual inputs
    customer_id: str | None = None


# ── Step 2: Define what comes OUT ─────────────────────────────────────────────
# The engine validates your return value against this schema.
# If your function returns something that doesn't match, the engine
# catches it and returns a structured error — your agent keeps running.

class MyToolOutput(BaseModel):
    status: str             # replace with your actual outputs
    detail: str


# ── Step 3: Write the function ────────────────────────────────────────────────
# Rules:
#   - Must be async
#   - Must return a plain dict (not MyToolOutput directly)
#   - Raise exceptions freely — the executor catches and retries them
#   - Keep it focused: one tool, one job

async def my_tool_fn(input: MyToolInput) -> dict:
    # Replace this with your actual logic:
    #   result = await your_db.query(input.order_id)
    #   result = requests.get(f"https://your-api.com/orders/{input.order_id}")
    await asyncio.sleep(0)  # remove this placeholder
    return {
        "status": "delivered",
        "detail": f"Order {input.order_id} was delivered.",
    }


# ── Step 4: Define the tool ───────────────────────────────────────────────────
# The description is what the LLM reads to decide WHEN to call this tool.
# Write it like instructions to a junior employee, not a docstring.
# See docs/tool-description-guide.md for good/bad examples.

TOOL_DEFINITION = ToolDefinition(
    name="my_tool",                        # unique name, snake_case
    description=(
        "Look up the status and details for a customer order. "
        "Use this when the user mentions an order number, asks where their "
        "package is, or wants to know if their order has shipped. "
        "Requires an order_id — ask the user for it if not provided."
    ),
    fn=my_tool_fn,
    input_schema=MyToolInput,
    output_schema=MyToolOutput,
    timeout_seconds=10,                    # fail if your API takes longer than this
    max_retries=2,                         # retry on transient failures
    permission_level="read",               # "read" | "write" | "escalate"
    on_timeout="fail",                     # "fail" | "skip"
    on_error="return_structured_error",    # "fail" | "return_structured_error"
)
