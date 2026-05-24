"""
User Memory — long-term persistent facts about a user across all sessions.

Layer 2 session_id convention: "user:{user_id}"
e.g. agent_id="support_agent", session_id="user:user_456"

Each fact is stored as a message with role="system".
Facts are injected into the system prompt at LOAD_MEMORY time so the LLM
has context about the user before the conversation even starts.

Fact extraction: a lightweight regex pass checks for name introductions.
This keeps Phase 2 self-contained without extra LLM calls.
"""
from __future__ import annotations

import logging
import re

from engine.memory.client import MemoryClient, StoredMessage

logger = logging.getLogger(__name__)

_PREFIX = "user"

# Patterns for extracting the user's name from their message
_NAME_PATTERNS = [
    re.compile(r"\bmy name is ([A-Z][a-z]+)\b", re.IGNORECASE),
    re.compile(r"\bI(?:'m| am) ([A-Z][a-z]+)\b", re.IGNORECASE),
    re.compile(r"\bcall me ([A-Z][a-z]+)\b", re.IGNORECASE),
]


def _ns(user_id: str) -> str:
    return f"{_PREFIX}:{user_id}"


class UserMemory:
    def __init__(self, client: MemoryClient) -> None:
        self._client = client

    async def load_facts(self, agent_id: str, user_id: str) -> list[str]:
        """
        Return stored user facts as plain strings.
        Each was stored with role="system".
        """
        stored: list[StoredMessage] = await self._client.read_all(agent_id, _ns(user_id))
        return [msg.content for msg in stored if msg.role == "system"]

    async def append_fact(self, agent_id: str, user_id: str, fact: str) -> None:
        """Store one fact about the user. Deduplicated by the caller."""
        await self._client.append(agent_id, _ns(user_id), role="system", content=fact)
        logger.info("user_memory.new_fact agent=%s user=%s fact=%r", agent_id, user_id, fact)

    async def extract_and_store(
        self, agent_id: str, user_id: str, user_message: str, existing_facts: list[str]
    ) -> None:
        """
        Run regex extraction on the user's message and store any new facts.
        Currently extracts: user name.
        """
        existing_lower = {f.lower() for f in existing_facts}

        for pattern in _NAME_PATTERNS:
            match = pattern.search(user_message)
            if match:
                name = match.group(1).strip().capitalize()
                fact = f"User's name is {name}."
                if fact.lower() not in existing_lower:
                    await self.append_fact(agent_id, user_id, fact)
                break  # only store the first name match
