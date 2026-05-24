# Writing Tool Descriptions

The `description` field in a `ToolDefinition` is the most important thing you write. The LLM reads it to decide whether to call your tool, and when. A bad description means the agent calls the wrong tool, misses when it should call it, or asks the user for information it could have looked up itself.

**Write for the LLM, not for other engineers.**

---

## The pattern

A good description answers four questions:

1. **What does this tool do?** (one sentence, plain English)
2. **When should the LLM call it?** (trigger conditions)
3. **What does the LLM need to provide?** (required inputs)
4. **What happens if the input is missing?** (fallback instruction)

---

## Examples — order lookup

**Bad:**
```
"Looks up an order by ID"
```
Problems: Too short. The LLM doesn't know when to call it or what triggers it. Doesn't mention that it needs an order_id, or what to do if the user hasn't provided one.

**Good:**
```
"Look up the current status, items, and estimated delivery date for a customer order.
Use this when the user asks where their package is, mentions an order number, asks
if something has shipped, or wants to know the status of a purchase.
Requires an order_id (format: ORD-XXXX) — if the user hasn't provided one, ask for it
before calling this tool."
```

---

## Examples — refund request

**Bad:**
```
"Processes a refund"
```

**Good:**
```
"Submit a refund request for an eligible order. Use this after you have confirmed the
order status and the customer explicitly asks for a refund. Do NOT call this speculatively —
confirm with the customer first ('Would you like me to process a refund for ORD-789?').
Requires order_id and reason. Returns whether the refund was approved or denied and the
expected timeline."
```

---

## Examples — escalate to human

**Bad:**
```
"Escalates the conversation"
```

**Good:**
```
"Transfer this conversation to a human support agent. Use this when:
- The customer is angry or frustrated and requests a human
- The issue cannot be resolved with the available tools
- A refund was denied and the customer wants to appeal
- You are uncertain how to proceed and need human judgment.
Do not use this as a first resort — always try to resolve the issue yourself first."
```

---

## Rules

**Do say when to call it.** The LLM needs trigger conditions, not a function signature.

**Do say what inputs are required.** If `order_id` is required, say so. If the user might not have provided it yet, tell the LLM to ask.

**Do say what NOT to do.** For write tools (refunds, escalation), be explicit about when NOT to call them. This prevents the agent from taking actions prematurely.

**Don't write it like a docstring.** `"Retrieves order information from the database"` is for engineers reading code. The LLM needs to understand intent, not implementation.

**Don't be too long.** 3–5 sentences is ideal. More than 8 sentences and the LLM starts to ignore parts of it.

---

## Testing whether your description works

After registering a tool, test it by asking your agent something you expect to trigger it. If the agent:

- Calls the wrong tool → your description overlaps with another tool's description. Make them more distinct.
- Doesn't call the tool when it should → your trigger conditions are too narrow or missing.
- Asks for information it should have looked up → you didn't tell it to call the tool proactively.
- Calls the tool without asking the user for required info → you didn't say "ask the user for X if not provided."

Use `GET /traces/{trace_id}/replay` to see exactly which tool was called and why — the LLM's reasoning is in the response content.
