"""
Agent Execution Engine — FastAPI application.

Entry point:
    uvicorn engine.api.app:app --reload

Routes:
    POST   /runs                         Submit an agent run
    GET    /runs/{run_id}                Retrieve a completed run
    GET    /traces/{trace_id}            Raw trace
    GET    /traces/{trace_id}/replay     Step-by-step trace replay
    GET    /health                       Liveness probe
    GET    /ready                        Readiness probe (checks memory service)
    GET    /metrics                      Prometheus metrics scrape endpoint
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from prometheus_client import make_asgi_app

from engine.api.dependencies import get_agent_registry, get_tool_registry
from engine.api.middleware import PrometheusMiddleware
from engine.api.routes import agents, health, runs, traces

logger = logging.getLogger(__name__)

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


# ── Startup: register demo tools and agents ────────────────────────────────────

def _register_demos() -> None:
    """
    Register the bundled demo tools and agents so the server is useful out of
    the box — no manual curl commands required.

    This runs once at startup. Production deployments can replace or extend this
    by importing their own tools and registering additional AgentDefinitions.
    """
    from demos.engineering_agent.agent import SYSTEM_PROMPT as ENG_PROMPT
    from demos.engineering_agent.agent import TOOL_NAMES as ENG_TOOL_NAMES
    from demos.engineering_agent.tools import ALL_TOOLS as ENG_TOOLS
    from demos.support_agent.agent import SYSTEM_PROMPT as SUPPORT_PROMPT
    from demos.support_agent.agent import TOOL_NAMES as SUPPORT_TOOL_NAMES
    from demos.support_agent.tools import ALL_TOOLS as SUPPORT_TOOLS
    from engine.models import AgentDefinition, RunBudget

    tool_registry = get_tool_registry()
    agent_registry = get_agent_registry()

    for tool in SUPPORT_TOOLS + ENG_TOOLS:
        try:
            tool_registry.register(tool)
        except Exception:
            pass  # already registered (e.g. on hot-reload)

    demo_agents = [
        AgentDefinition(
            agent_id="support_agent",
            description="Customer support agent for ShopEasy — handles order lookups, refunds, and escalations.",
            system_prompt=SUPPORT_PROMPT,
            tools=SUPPORT_TOOL_NAMES,
            default_budget=RunBudget(max_steps=10, max_tokens=8_000, max_cost_usd=0.30, timeout_seconds=120),
        ),
        AgentDefinition(
            agent_id="engineering_agent",
            description="Engineering assistant — code search, file read, PR review, dependency audit.",
            system_prompt=ENG_PROMPT,
            tools=ENG_TOOL_NAMES,
            default_budget=RunBudget(max_steps=10, max_tokens=8_000, max_cost_usd=0.30, timeout_seconds=120),
        ),
    ]

    for definition in demo_agents:
        try:
            agent_registry.register(definition)
            logger.info("Registered agent: %s", definition.agent_id)
        except Exception:
            pass  # already registered on hot-reload


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    _register_demos()
    yield


# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Agent Execution Engine",
    description=(
        "Self-hostable production runtime for LLM agents. "
        "State-machine orchestration, typed tool execution, persistent memory, "
        "trace replay, and automated evals."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Prometheus middleware — must be added before routes
app.add_middleware(PrometheusMiddleware)

# ── Routes ─────────────────────────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(agents.router)
app.include_router(runs.router)
app.include_router(traces.router)

# ── Prometheus metrics scrape endpoint ─────────────────────────────────────────
# Mounted at /metrics — standard Prometheus scrape target
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


# ── Root ───────────────────────────────────────────────────────────────────────
@app.get("/", include_in_schema=False)
async def root() -> dict:
    return {
        "service": "agent-execution-engine",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
        "metrics": "/metrics",
    }
