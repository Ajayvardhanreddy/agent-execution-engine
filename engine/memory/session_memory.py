"""
Session Memory — short-term conversation history for one session.

Layer 2 session_id convention: "session:{session_id}"
e.g. agent_id="support_agent", session_id="session:sess_abc123"

Stores the plain-text user↔assistant exchanges so the agent can recall
what was said in previous turns of the same conversation.
"""
from __future__ import annotations

import json
import logging

from engine.memory.client import MemoryClient, StoredMessage

logger = logging.getLogger(__name__)

_PREFIX = "session"


def _ns(session_id: str) -> str:
    return f"{_PREFIX}:{session_id}"


class SessionMemory:
    def __init__(self, client: MemoryClient) -> None:
        self._client = client

    async def load(self, agent_id: str, session_id: str, last_n: int = 50) -> list[dict]:
        """
        Return the last N messages in Anthropic message-list format:
        [{"role": "user"|"assistant", "content": str}, ...]
        """
        stored: list[StoredMessage] = await self._client.read_window(
            agent_id, _ns(session_id), last_n=last_n
        )
        messages = []
        for msg in stored:
            # Content is stored as-is (plain text for user/assistant turns)
            content = msg.content
            # Try to deserialize JSON content (for assistant messages with rich content)
            try:
                parsed = json.loads(content)
                # Only use parsed form if it's a dict/list (not a bare string)
                if isinstance(parsed, (dict, list)):
                    content = parsed
            except (json.JSONDecodeError, ValueError):
                pass
            messages.append({"role": msg.role, "content": content})
        return messages

    async def append_user_message(self, agent_id: str, session_id: str, content: str) -> None:
        await self._client.append(agent_id, _ns(session_id), role="user", content=content)
        logger.debug("session_memory.append user agent=%s session=%s", agent_id, session_id)

    async def append_assistant_message(self, agent_id: str, session_id: str, content: str) -> None:
        await self._client.append(agent_id, _ns(session_id), role="assistant", content=content)
        logger.debug("session_memory.append assistant agent=%s session=%s", agent_id, session_id)
