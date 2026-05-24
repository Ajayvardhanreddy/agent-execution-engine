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
import os

from fastapi import FastAPI
from prometheus_client import make_asgi_app

from engine.api.middleware import PrometheusMiddleware
from engine.api.routes import agents, health, runs, traces

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

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
