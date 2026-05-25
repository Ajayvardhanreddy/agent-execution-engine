"""
MCP server for the Agent Execution Engine.

Exposes two MCP tools:
  run_agent   — submit a run to any registered agent, return its final answer
  list_agents — discover which agents are registered in the engine

Transport is controlled by MCP_TRANSPORT (default: stdio for local/Claude Desktop):
  stdio  — pipe-based, for Claude Desktop and CLI usage
  sse    — HTTP + Server-Sent Events, for Docker / remote clients

In Docker Compose the server runs with MCP_TRANSPORT=sse on port MCP_PORT (default 9001).
For Claude Desktop, run locally without MCP_TRANSPORT set (defaults to stdio).

Usage:
    # Docker (SSE)
    MCP_TRANSPORT=sse MCP_PORT=9001 ENGINE_URL=http://localhost:9000 python -m engine.mcp.server

    # Claude Desktop (stdio) — add to claude_desktop_config.json:
    {
      "mcpServers": {
        "agent-engine": {
          "command": "uv",
          "args": ["run", "python", "-m", "engine.mcp.server"],
          "env": {"ENGINE_URL": "http://localhost:9000"}
        }
      }
    }
"""
from __future__ import annotations

import os

import httpx
from fastmcp import FastMCP

ENGINE_URL = os.environ.get("ENGINE_URL", "http://localhost:9000").rstrip("/")

mcp = FastMCP(
    "Agent Execution Engine",
    instructions=(
        "Use list_agents to discover available agents, then run_agent to submit a request. "
        "Each agent is purpose-built: support agents handle customer issues, "
        "engineering agents help with code search, PR review, and dependency audits."
    ),
)


@mcp.tool()
async def run_agent(agent_id: str, session_id: str, user_id: str, input: str) -> str:
    """
    Submit a request to a registered agent and return its final answer.

    Call list_agents first to discover valid agent_id values.

    Args:
        agent_id:   ID of a registered agent (e.g. "support_agent", "engineering_agent")
        session_id: Stable identifier for this conversation (use the same value across
                    turns to maintain memory context)
        user_id:    End-user identifier (used for memory scoping and audit)
        input:      The user's message or request

    Returns:
        The agent's final answer as a string, or an error description prefixed with [status].
    """
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{ENGINE_URL}/runs",
            json={
                "agent_id": agent_id,
                "session_id": session_id,
                "user_id": user_id,
                "input": input,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    if data.get("final_answer"):
        return data["final_answer"]
    return f"[{data['status']}] {data.get('failure_reason') or 'no answer returned'}"


@mcp.tool()
async def list_agents() -> list[dict]:
    """
    List all agents registered with the engine.

    Returns a list of agent summaries. Each entry includes:
      agent_id    — pass this to run_agent
      description — what the agent does
      tools       — which tools it has access to

    Use this to discover available agents before calling run_agent.
    """
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{ENGINE_URL}/agents")
        resp.raise_for_status()
        return resp.json()


if __name__ == "__main__":
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport == "sse":
        host = os.environ.get("MCP_HOST", "0.0.0.0")
        port = int(os.environ.get("MCP_PORT", "9001"))
        mcp.run(transport="sse", host=host, port=port)
    else:
        mcp.run(transport="stdio")
