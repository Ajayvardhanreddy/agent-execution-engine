"""
FastAPI dependency-injection helpers — singleton AgentEngine, ToolRegistry,
and AgentRegistry shared across all requests.
"""
from __future__ import annotations

import os
from functools import lru_cache

from engine.api.agent_registry import AgentRegistry
from engine.orchestrator.engine import AgentEngine
from engine.tools.registry import ToolRegistry


@lru_cache(maxsize=1)
def _build_tool_registry() -> ToolRegistry:
    """
    Singleton ToolRegistry.

    Production deployments: import this and call .register() on your tools
    at application startup (e.g. in a lifespan handler or startup script).
    See tool_template.py and docs/adding-tools.md for the pattern.
    """
    return ToolRegistry()


@lru_cache(maxsize=1)
def _build_agent_registry() -> AgentRegistry:
    return AgentRegistry(tool_registry=_build_tool_registry())


@lru_cache(maxsize=1)
def _build_engine() -> AgentEngine:
    return AgentEngine(
        registry=_build_tool_registry(),
        model=os.environ.get("EVAL_MODEL"),
        memory_url=os.environ.get("MEMORY_SERVICE_URL"),
    )


# ── FastAPI dependencies ───────────────────────────────────────────────────────

def get_tool_registry() -> ToolRegistry:
    return _build_tool_registry()


def get_agent_registry() -> AgentRegistry:
    return _build_agent_registry()


def get_engine() -> AgentEngine:
    return _build_engine()
