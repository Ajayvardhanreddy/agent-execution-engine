# Registering Agents

An agent definition is the server-side configuration for one agent — its identity, instructions, tools, and spending limits. You register it once. After that, your application just sends `agent_id + input` to run it.

---

## The request

```bash
curl -X POST http://localhost:8000/agents \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "support_agent",
    "description": "Customer support agent for ShopEasy",
    "system_prompt": "You are a helpful support agent for ShopEasy...",
    "tools": ["order_lookup", "refund_request", "escalate_to_human"],
    "default_budget": {
      "max_steps": 15,
      "max_tokens": 10000,
      "max_cost_usd": 0.50,
      "timeout_seconds": 90
    }
  }'
```

---

## Fields

### `agent_id`
The name your application uses when submitting runs. Use snake_case. Examples: `support_agent`, `triage_bot`, `billing_assistant`.

### `description`
One sentence. Shown in `GET /agents` listings. Not sent to the LLM.

### `system_prompt`
The LLM reads this before every turn. It defines the agent's personality, scope, and constraints. Keep it focused — a prompt that tries to do everything does nothing well.

Good structure:
1. Who the agent is (role + company)
2. What it can help with
3. What it should NOT do
4. How it should behave (tone, escalation policy)

Example:
```
You are a customer support agent for ShopEasy, an e-commerce platform.

You help customers with:
- Order status and tracking
- Refund requests for eligible orders
- General account questions

You do NOT:
- Discuss competitor products
- Promise outcomes you cannot guarantee
- Share information about other customers

If you cannot resolve an issue with the tools available, escalate to a human agent.
Be concise. Confirm before processing any refund.
```

### `tools`
List of tool names this agent may call. Names must match exactly what's registered in the ToolRegistry — call `GET /tools` to see what's available.

The engine enforces this at run time — the LLM only sees the tools listed here. If the LLM tries to call a tool not in this list, the engine returns an error to the LLM and it must try another approach.

### `default_budget`
Hard limits per run. The engine kills any run that exceeds any of these:

| Field | Default | What it controls |
|-------|---------|-----------------|
| `max_steps` | 15 | LLM calls (each tool call + response = 1 step) |
| `max_tokens` | 10,000 | Total tokens across the entire run |
| `max_cost_usd` | 0.50 | Total API cost |
| `timeout_seconds` | 90 | Wall-clock time from start to finish |

Set these based on what your use case needs. A support agent doing simple lookups might use 5 steps and $0.05. A research agent might need 20 steps and $2.00.

---

## Running the agent

After registration, your application submits runs like this:

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

The `session_id` ties conversations together — the agent remembers what was said in earlier turns of the same session (if memory service is running). Use a stable ID per conversation, not per message.

The `user_id` is used to store persistent user facts across all sessions. If the user says "my name is Alice" in any session, the agent will remember it in future sessions.

---

## Multiple agents, shared tools

The same tool code can be used by any number of agents:

```
Tool shelf:
  order_lookup, refund_request, ticket_create, escalate_to_human

support_agent  → order_lookup, refund_request, escalate_to_human
triage_agent   → order_lookup, escalate_to_human
billing_agent  → refund_request, ticket_create
```

The engine enforces tool boundaries at runtime — `triage_agent` cannot call `refund_request` even if the LLM tries. The agent simply doesn't know it exists.

---

## Updating an agent

```bash
curl -X PUT http://localhost:8000/agents/support_agent \
  -H "Content-Type: application/json" \
  -d '{ ...updated definition... }'
```

The `created_at` timestamp is preserved. Existing completed runs are not affected — traces store what tools and prompt were used at run time.

---

## Listing and inspecting agents

```bash
# List all agents (summary — no system_prompt)
curl http://localhost:8000/agents

# Full definition including system_prompt
curl http://localhost:8000/agents/support_agent
```
