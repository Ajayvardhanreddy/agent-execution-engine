"""
Eval runner — executes a suite of EvalCases against the engine and produces
a scored report.

Usage:
    PYTHONPATH=. uv run python evals/runner.py --suite support
    PYTHONPATH=. uv run python evals/runner.py --suite engineering
    PYTHONPATH=. uv run python evals/runner.py --suite all
    PYTHONPATH=. uv run python evals/runner.py --suite support --case support_005
    PYTHONPATH=. uv run python evals/runner.py --suite support --no-save

The runner calls AgentEngine directly (no HTTP server required).
Agent tools and system prompts are imported from the respective demos.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env before any engine imports so API keys are available
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)

logging.basicConfig(
    level=logging.WARNING,   # suppress engine noise during evals
    format="%(levelname)s %(name)s %(message)s",
    stream=sys.stderr,
)

import demos.support_agent.agent as _support_demo
import demos.engineering_agent.agent as _eng_demo
from demos.support_agent.tools import ALL_TOOLS as _SUPPORT_TOOLS
from demos.engineering_agent.tools import ALL_TOOLS as _ENG_TOOLS
from evals.dataset.support_cases import SUPPORT_CASES
from evals.dataset.engineering_cases import ENGINEERING_CASES
from evals.report import print_report, save_report
from engine.evals.base import EvalCase, EvalResult
from engine.evals.suite import EvalSuite
from engine.models import AgentRun, RunBudget
from engine.observability.traces import get_trace
from engine.orchestrator.engine import AgentEngine
from engine.tools.registry import ToolRegistry


# ── Per-suite configuration ────────────────────────────────────────────────────

_SUITE_CONFIG = {
    "support": {
        "tools": _SUPPORT_TOOLS,
        "tool_names": _support_demo.TOOL_NAMES,
        "system_prompt": _support_demo.SYSTEM_PROMPT,
        "cases": SUPPORT_CASES,
    },
    "engineering": {
        "tools": _ENG_TOOLS,
        "tool_names": _eng_demo.TOOL_NAMES,
        "system_prompt": _eng_demo.SYSTEM_PROMPT,
        "cases": ENGINEERING_CASES,
    },
}


def _build_engine(suite: str) -> AgentEngine:
    config = _SUITE_CONFIG[suite]
    registry = ToolRegistry()
    for tool in config["tools"]:
        registry.register(tool)
    return AgentEngine(registry=registry)


def _extract_tools_called(trace_id: str) -> list[str]:
    """Pull the list of tools called from the trace store."""
    trace = get_trace(trace_id)
    if not trace:
        return []
    tools: list[str] = []
    for span in trace.spans:
        called = span.metadata.get("tools_called", [])
        tools.extend(called)
    return tools


async def _run_case(
    case: EvalCase,
    engine: AgentEngine,
    suite: EvalSuite,
    suite_name: str,
) -> EvalResult:
    config = _SUITE_CONFIG[suite_name]
    internal_run = AgentRun(
        agent_id=case.agent_id,
        session_id=case.session_id,
        user_id=case.user_id,
        input=case.input,
        tools=config["tool_names"],
        system_prompt=config["system_prompt"],
        budget=RunBudget(
            max_steps=15,
            max_tokens=10_000,
            max_cost_usd=case.max_cost_usd * 3,   # give headroom; scorer measures efficiency
            timeout_seconds=120,
        ),
    )

    try:
        result = await engine.run(internal_run)
        tools_called = _extract_tools_called(result.trace_id)
        return suite.evaluate(case, result, tools_called)
    except Exception as exc:
        # Engine crashed — create a minimal result so the scorer can record a failure
        from engine.models import AgentRunResult
        dummy = AgentRunResult(
            run_id="crashed",
            status="failed",
            final_answer=None,
            trace_id="none",
            steps_taken=0,
            total_tokens_used=0,
            total_cost_usd=0.0,
            latency_ms=0,
            failure_reason=str(exc),
        )
        return suite.evaluate(case, dummy, [], error=str(exc))


async def run_suite(
    cases: list[EvalCase],
    suite_name: str,
    save: bool = True,
    filter_case_id: str | None = None,
) -> list[EvalResult]:
    if not cases:
        print(f"No cases found for suite '{suite_name}'.")
        return []

    if filter_case_id:
        cases = [c for c in cases if c.case_id == filter_case_id]
        if not cases:
            print(f"Case '{filter_case_id}' not found.")
            return []

    engine = _build_engine(suite_name)
    eval_suite = EvalSuite()
    results: list[EvalResult] = []

    print(f"\nRunning {len(cases)} eval case(s) for suite '{suite_name}'...")
    print("Each case makes real LLM calls — this will take a few minutes.\n")

    for i, case in enumerate(cases, 1):
        print(f"  [{i:02d}/{len(cases):02d}] {case.case_id}: {case.description[:55]}...", end="", flush=True)
        result = await _run_case(case, engine, eval_suite, suite_name)
        results.append(result)
        status = "✓" if result.passed else "✗"
        print(f" {status} ({result.overall_score:.2f})")

    print_report(results, suite_name)

    if save:
        path = save_report(results, suite_name)
        print(f"Report saved to: {path}\n")

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Run agent evals")
    parser.add_argument(
        "--suite",
        choices=["support", "engineering", "all"],
        default="support",
        help="Which eval suite to run",
    )
    parser.add_argument(
        "--case",
        default=None,
        help="Run a single case by case_id (e.g. support_005)",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Don't save JSON report to evals/reports/",
    )
    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set. Add it to .env or export it.")
        sys.exit(1)

    suite_map = {
        "support": SUPPORT_CASES,
        "engineering": ENGINEERING_CASES,
    }

    if args.suite == "all":
        for name, cases in suite_map.items():
            asyncio.run(run_suite(cases, name, save=not args.no_save, filter_case_id=args.case))
    else:
        cases = suite_map[args.suite]
        asyncio.run(run_suite(cases, args.suite, save=not args.no_save, filter_case_id=args.case))


if __name__ == "__main__":
    main()
