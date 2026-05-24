"""
Unit tests for the trace replay endpoint.

Uses FastAPI's TestClient (httpx-based) with a pre-populated trace store.
No real agent runs — traces are injected directly into the module-level store.
"""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from engine.api.app import app
from engine.observability.spans import Span
from engine.observability.traces import Trace, store_trace

client = TestClient(app)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_trace(trace_id: str, status: str = "completed", n_steps: int = 3) -> Trace:
    """Build a minimal Trace with n_steps spans and store it."""
    now_ms = int(time.time() * 1000)
    states = ["START", "LOAD_MEMORY", "BUILD_CONTEXT", "CALL_LLM", "PROCESS_RESPONSE", "RESPOND"]

    spans = []
    for i in range(n_steps):
        spans.append(Span(
            span_id=f"sp_{i:06d}",
            trace_id=trace_id,
            step=i,
            from_state=states[i % len(states)],
            to_state=states[(i + 1) % len(states)],
            timestamp_ms=now_ms + i * 100,
            duration_ms=50 + i * 10,
            metadata={"model": "claude-haiku-4-5-20251001"} if i == 2 else {},
        ))

    trace = Trace(
        trace_id=trace_id,
        run_id=f"run_{trace_id}",
        agent_id="test_agent",
        session_id="sess_test",
        user_id="user_test",
        started_at="2026-01-01T00:00:00",
        ended_at="2026-01-01T00:00:05",
        status=status,
        spans=spans,
        total_tokens=500,
        total_cost_usd=0.002,
        total_latency_ms=5000,
        steps_taken=n_steps,
    )
    store_trace(trace)
    return trace


# ── GET /traces/{trace_id} ─────────────────────────────────────────────────────

def test_get_trace_raw_returns_full_trace():
    trace = _make_trace("trace_raw_001")
    resp = client.get(f"/traces/{trace.trace_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["trace_id"] == "trace_raw_001"
    assert data["status"] == "completed"
    assert len(data["spans"]) == 3


def test_get_trace_raw_404_for_unknown():
    resp = client.get("/traces/trace_does_not_exist")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


# ── GET /traces/{trace_id}/replay ─────────────────────────────────────────────

def test_replay_returns_steps_in_order():
    trace = _make_trace("trace_replay_001", n_steps=4)
    resp = client.get(f"/traces/{trace.trace_id}/replay")
    assert resp.status_code == 200
    data = resp.json()

    assert data["trace_id"] == "trace_replay_001"
    assert data["total_steps"] == 4
    assert len(data["steps"]) == 4

    # Steps must be ordered by step index
    step_nums = [s["step"] for s in data["steps"]]
    assert step_nums == sorted(step_nums)


def test_replay_cumulative_duration_accumulates():
    trace = _make_trace("trace_replay_002", n_steps=3)
    resp = client.get(f"/traces/{trace.trace_id}/replay")
    assert resp.status_code == 200
    steps = resp.json()["steps"]

    # cumulative_duration_ms must be non-decreasing
    for i in range(1, len(steps)):
        assert steps[i]["cumulative_duration_ms"] >= steps[i - 1]["cumulative_duration_ms"]

    # Final cumulative equals sum of all durations
    total = sum(s["duration_ms"] for s in steps)
    assert steps[-1]["cumulative_duration_ms"] == total


def test_replay_step_has_required_fields():
    trace = _make_trace("trace_replay_003", n_steps=2)
    resp = client.get(f"/traces/{trace.trace_id}/replay")
    assert resp.status_code == 200
    step = resp.json()["steps"][0]

    assert "step" in step
    assert "span_id" in step
    assert "from_state" in step
    assert "to_state" in step
    assert "duration_ms" in step
    assert "cumulative_duration_ms" in step
    assert "metadata" in step


def test_replay_404_for_unknown_trace():
    resp = client.get("/traces/trace_xyz_unknown/replay")
    assert resp.status_code == 404


def test_replay_metadata_preserved():
    trace = _make_trace("trace_replay_004", n_steps=3)
    resp = client.get(f"/traces/{trace.trace_id}/replay")
    assert resp.status_code == 200
    steps = resp.json()["steps"]
    # step index 2 has metadata with model key (see _make_trace)
    step_with_meta = next(s for s in steps if s["step"] == 2)
    assert step_with_meta["metadata"].get("model") == "claude-haiku-4-5-20251001"


def test_replay_escalated_trace():
    trace = _make_trace("trace_replay_005", status="escalated", n_steps=2)
    resp = client.get(f"/traces/{trace.trace_id}/replay")
    assert resp.status_code == 200
    assert resp.json()["status"] == "escalated"


# ── GET /health ────────────────────────────────────────────────────────────────

def test_health_returns_ok():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ── GET /metrics ───────────────────────────────────────────────────────────────

def test_metrics_endpoint_returns_prometheus_format():
    resp = client.get("/metrics")
    assert resp.status_code == 200
    # Prometheus text format always contains TYPE lines
    assert b"# TYPE" in resp.content


# ── GET / (root) ──────────────────────────────────────────────────────────────

def test_root_returns_service_info():
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["service"] == "agent-execution-engine"
    assert "docs" in data
