"""
Engineering Assistant Agent demo entry point.

Usage:
    PYTHONPATH=. uv run python demos/engineering_agent/agent.py
    PYTHONPATH=. uv run python demos/engineering_agent/agent.py --scenario review_pr
    PYTHONPATH=. uv run python demos/engineering_agent/agent.py --scenario security_investigation
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env", override=True)

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "WARNING"),
    format="%(message)s",
    stream=sys.stdout,
)

from demos.engineering_agent.scenarios import SCENARIOS, SCENARIOS_BY_NAME
from demos.engineering_agent.tools import ALL_TOOLS, TOOL_NAMES
from engine.models import AgentRun, RunBudget
from engine.orchestrator.engine import AgentEngine
from engine.tools.registry import ToolRegistry

SYSTEM_PROMPT = """You are an engineering assistant for a software development team.

Your capabilities:
- Search the codebase for functions, classes, and patterns
- Read specific files to inspect code
- Review pull requests and identify bugs, security issues, and style problems
- Check dependencies for outdated versions and security vulnerabilities

How to work:
- Always use the available tools to look up real data — do not guess or make up code
- When reviewing a PR, clearly separate critical issues from warnings and style notes
- When reporting vulnerabilities, include the CVE number and a concrete fix suggestion
- Be precise: include file names, line numbers, and version numbers in your responses
- If asked to investigate something, search first, then read the relevant files

Tone: direct and technical. Your audience is engineers, not end users."""


def build_engine() -> AgentEngine:
    registry = ToolRegistry()
    for tool in ALL_TOOLS:
        registry.register(tool)
    return AgentEngine(registry=registry)


async def run_scenario(name: str) -> None:
    scenario = SCENARIOS_BY_NAME.get(name)
    if scenario is None:
        available = ", ".join(SCENARIOS_BY_NAME)
        print(f"Unknown scenario '{name}'. Available: {available}")
        return

    engine = build_engine()
    request = AgentRun(
        agent_id="engineering_agent",
        session_id=scenario.session_id,
        user_id=scenario.user_id,
        input=scenario.input,
        tools=TOOL_NAMES,
        system_prompt=SYSTEM_PROMPT,
        budget=RunBudget(max_steps=10, max_tokens=8_000, max_cost_usd=0.30, timeout_seconds=120),
    )

    print(f"\n{'=' * 60}")
    print(f"  Scenario : {scenario.name}")
    print(f"  {scenario.description}")
    print(f"{'=' * 60}")
    print(f"\nUser: {scenario.input}\n")

    result = await engine.run(request)

    print(f"Agent: {result.final_answer or '[no answer]'}\n")
    print(f"{'─' * 60}")
    print(f"  Status  : {result.status}")
    print(f"  Steps   : {result.steps_taken}")
    print(f"  Tokens  : {result.total_tokens_used}")
    print(f"  Cost    : ${result.total_cost_usd:.4f}")
    print(f"  Latency : {result.latency_ms}ms")
    if result.failure_reason:
        print(f"  Reason  : {result.failure_reason}")
    print(f"{'=' * 60}\n")


async def run_all() -> None:
    for scenario in SCENARIOS:
        await run_scenario(scenario.name)


def main() -> None:
    parser = argparse.ArgumentParser(description="Engineering Assistant Agent demo")
    parser.add_argument("--scenario", help="Run a specific scenario by name")
    parser.add_argument("--list", action="store_true", help="List available scenarios")
    args = parser.parse_args()

    if args.list:
        print("\nAvailable scenarios:")
        for s in SCENARIOS:
            print(f"  {s.name:<26} — {s.description}")
        return

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set. Add it to .env or export it.")
        sys.exit(1)

    if args.scenario:
        asyncio.run(run_scenario(args.scenario))
    else:
        asyncio.run(run_all())


if __name__ == "__main__":
    main()
