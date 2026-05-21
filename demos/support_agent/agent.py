"""
Customer Support Agent demo entry point.

Usage:
    uv run python demos/support_agent/agent.py
    uv run python demos/support_agent/agent.py --scenario eligible_refund
    uv run python demos/support_agent/agent.py --scenario fraud_risk_escalation
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

# Configure structured JSON logging to stdout
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(message)s",
    stream=sys.stdout,
)

from demos.support_agent.scenarios import SCENARIOS, SCENARIOS_BY_NAME
from demos.support_agent.tools import ALL_TOOLS
from engine.models import AgentRun, RunBudget
from engine.orchestrator.engine import AgentEngine
from engine.tools.registry import ToolRegistry

SYSTEM_PROMPT = """You are a customer support agent for ShopEasy, an e-commerce company.

Your responsibilities:
- Help customers with order inquiries, refunds, and complaints
- Always look up the order before processing any refund
- Always check refund policy before approving or denying a refund
- Be professional and empathetic, even with frustrated customers
- Escalate to a human agent if you detect fraud risk (large order + repeated claims) or if the customer is abusive

Rules:
- Never process a refund without first calling order_lookup and refund_policy_search
- If the customer hasn't provided an order ID, ask for it before calling any tools
- If an order is outside the 30-day refund window, politely explain the policy
- If an item is non-refundable (digital, software license), explain why
- If fraud risk is detected, call escalate_to_human immediately"""

TOOL_NAMES = [
    "order_lookup",
    "refund_policy_search",
    "refund_request",
    "ticket_create",
    "escalate_to_human",
]


def build_engine() -> AgentEngine:
    registry = ToolRegistry()
    for tool in ALL_TOOLS:
        registry.register(tool)
    return AgentEngine(registry=registry)


async def run_scenario(engine: AgentEngine, scenario_name: str) -> None:
    scenario = SCENARIOS_BY_NAME.get(scenario_name)
    if scenario is None:
        print(f"Unknown scenario: {scenario_name!r}")
        print(f"Available: {list(SCENARIOS_BY_NAME)}")
        return

    print(f"\n{'='*60}")
    print(f"SCENARIO: {scenario.name}")
    print(f"DESC:     {scenario.description}")
    print(f"INPUT:    {scenario.input}")
    print(f"{'='*60}\n")

    request = AgentRun(
        agent_id="support_agent",
        session_id=scenario.session_id,
        user_id=scenario.user_id,
        input=scenario.input,
        tools=TOOL_NAMES,
        system_prompt=SYSTEM_PROMPT,
        budget=RunBudget(max_steps=12, max_tokens=8000, max_cost_usd=0.10, timeout_seconds=60),
    )

    result = await engine.run(request)

    print(f"\n{'─'*60}")
    print(f"RESULT")
    print(f"{'─'*60}")
    print(json.dumps(result.model_dump(), indent=2))
    print(f"\nExpected status : {scenario.expected_status}")
    print(f"Actual status   : {result.status}")
    match = "✓ PASS" if result.status == scenario.expected_status else "✗ FAIL"
    print(f"Match           : {match}")


async def run_all(engine: AgentEngine) -> None:
    for scenario in SCENARIOS:
        await run_scenario(engine, scenario.name)
        print()


async def main() -> None:
    parser = argparse.ArgumentParser(description="Customer Support Agent demo")
    parser.add_argument(
        "--scenario",
        default=None,
        help=f"Scenario name. Options: {[s.name for s in SCENARIOS]}. Omit to run all.",
    )
    args = parser.parse_args()

    engine = build_engine()

    if args.scenario:
        await run_scenario(engine, args.scenario)
    else:
        await run_all(engine)


if __name__ == "__main__":
    asyncio.run(main())
