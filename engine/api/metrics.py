"""
Prometheus metrics for the Agent Execution Engine API.

Exported metrics:
  - agent_runs_total          (counter)   — completed runs labelled by status
  - agent_run_duration_seconds (histogram) — end-to-end latency per run
  - agent_run_tokens_total     (counter)   — cumulative tokens consumed
  - agent_active_runs          (gauge)     — runs currently in-flight
  - http_requests_total        (counter)   — HTTP requests labelled by method/path/status
  - http_request_duration_seconds (histogram) — per-request latency
"""
from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# ── Run-level metrics ──────────────────────────────────────────────────────────

RUNS_TOTAL = Counter(
    "agent_runs_total",
    "Total agent runs by status",
    ["agent_id", "status"],
)

RUN_DURATION = Histogram(
    "agent_run_duration_seconds",
    "End-to-end latency of an agent run",
    ["agent_id", "status"],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0],
)

RUN_TOKENS = Counter(
    "agent_run_tokens_total",
    "Total LLM tokens consumed",
    ["agent_id", "model"],
)

ACTIVE_RUNS = Gauge(
    "agent_active_runs",
    "Agent runs currently in flight",
    ["agent_id"],
)

# ── HTTP-level metrics ─────────────────────────────────────────────────────────

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status_code"],
)

HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "path"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)
