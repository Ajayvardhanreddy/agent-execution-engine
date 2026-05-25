# MCP Server Setup

The agent execution engine ships an MCP server that exposes two tools:

| Tool | What it does |
|---|---|
| `run_agent` | Submit a request to any registered agent and get its final answer |
| `list_agents` | Discover which agents are registered in the engine |

---

## Option A — Claude Desktop (local, stdio)

Add this block to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "agent-engine": {
      "command": "uv",
      "args": ["run", "python", "-m", "engine.mcp.server"],
      "cwd": "/path/to/agent-execution-engine",
      "env": {
        "ENGINE_URL": "http://localhost:9000",
        "PYTHONPATH": "/path/to/agent-execution-engine"
      }
    }
  }
}
```

Start the engine API first, then restart Claude Desktop:

```bash
make serve          # engine API on :9000
# restart Claude Desktop
```

---

## Option B — Docker Compose (SSE, remote clients)

```bash
cp .env.example .env
# set ANTHROPIC_API_KEY in .env

docker compose up
# engine API on :9000
# MCP server (SSE) on :9001
```

Connect any SSE-capable MCP client to `http://localhost:9001/sse`.

---

## Verifying the connection

In Claude Desktop, ask:

> List the available agents.

Claude should call `list_agents` and return the registered agents. Then:

> Use the support agent to check order ORD-123.

This calls `run_agent` with `agent_id="support_agent"`.
