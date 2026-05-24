"""
Working Memory — per-run scratchpad of tool results and intermediate state.

Layer 2 session_id convention: "working:{run_id}"
e.g. agent_id="support_agent", session_id="working:run_xyz789"

Written at:  OBSERVE_RESULT — one append per tool result
Read at:     BUILD_CONTEXT — injected as supplementary context
Deleted at:  run completion (RESPOND / ESCALATE / FAIL)
TTL:         run duration + 1h (but we delete explicitly)
"""
from __future__ import annotations

import json
import logging

from engine.memory.client import MemoryClient, StoredMessage

logger = logging.getLogger(__name__)

_PREFIX = "working"


def _ns(run_id: str) -> str:
    return f"{_PREFIX}:{run_id}"


class WorkingMemory:
    def __init__(self, client: MemoryClient) -> None:
        self._client = client

    async def append_tool_result(
        self,
        agent_id: str,
        run_id: str,
        tool_name: str,
        success: bool,
        output: dict | None,
        error_msg: str | None = None,
    ) -> None:
        content = json.dumps({
            "tool": tool_name,
            "success": success,
            "output": output,
            "error": error_msg,
        })
        await self._client.append(agent_id, _ns(run_id), role="tool", content=content)
        logger.debug("working_memory.append tool=%s run=%s success=%s", tool_name, run_id, success)

    async def load(self, agent_id: str, run_id: str) -> list[dict]:
        """Return stored tool results as parsed dicts."""
        stored: list[StoredMessage] = await self._client.read_all(agent_id, _ns(run_id))
        results = []
        for msg in stored:
            try:
                results.append(json.loads(msg.content))
            except json.JSONDecodeError:
                results.append({"raw": msg.content})
        return results

    async def delete(self, agent_id: str, run_id: str) -> None:
        """Explicitly delete working memory on run completion."""
        await self._client.delete_session(agent_id, _ns(run_id))
        logger.debug("working_memory.deleted run=%s", run_id)
