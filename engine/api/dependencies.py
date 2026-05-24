"""
FastAPI dependency-injection helpers.

The AgentEngine is expensive to create (opens an Anthropic client, sets up
memory client, etc.) so we build one singleton at startup and inject it into
every route via FastAPI's dependency system.
"""
from __future__ import annotations

import os
from functools import lru_cache

from engine.orchestrator.engine import AgentEngine
from engine.tools.registry import ToolRegistry


@lru_cache(maxsize=1)
def _build_engine() -> AgentEngine:
    """
    Build the shared AgentEngine singleton.

    Tool registry is empty by default — production deployments should
    sub-class or replace this function to register their tools.
    Use the /runs endpoint's `tools` list to gate which tools each run
    may call; the registry is the superset of what's available.
    """
    registry = ToolRegistry()
    return AgentEngine(
        registry=registry,
        model=os.environ.get("EVAL_MODEL"),
        memory_url=os.environ.get("MEMORY_SERVICE_URL"),
    )


def get_engine() -> AgentEngine:
    """FastAPI dependency — returns the singleton AgentEngine."""
    return _build_engine()


def get_registry() -> ToolRegistry:
    """FastAPI dependency — returns the singleton ToolRegistry."""
    return _build_engine()._registry  # type: ignore[attr-defined]
