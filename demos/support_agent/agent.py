"""
Customer Support Agent demo entry point.

Usage:
    uv run python demos/support_agent/agent.py
    uv run python demos/support_agent/agent.py --scenario eligible_refund
    uv run python demos/support_agent/agent.py --scenario fraud_risk_escalation

    # Phase 2 — memory persistence demo (requires Layer 2 running on localhost:8080)
    uv run python demos/support_agent/agent.py --memory-demo
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
    print("RESULT")
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


async def run_memory_demo(engine: AgentEngine) -> None:
    """
    Phase 2 memory demo — requires Layer 2 running on localhost:8080.

    Run 1: User introduces themselves and requests a refund.
           Engine stores name in user memory, conversation in session memory.
    Run 2: Same user, new session. Engine loads user facts from user memory.
           Agent greets the user by name without being told again.
    """
    user_id = "user_memory_demo"
    agent_id = "support_agent"

    print("\n" + "=" * 60)
    print("PHASE 2 MEMORY DEMO")
    print("=" * 60)

    # ── Run 1 ──────────────────────────────────────────────────────────────────
    print("\n[RUN 1] User introduces themselves + requests refund")
    print("─" * 60)

    run1 = AgentRun(
        agent_id=agent_id,
        session_id="memory_demo_sess_001",
        user_id=user_id,
        input=(
            "Hi, my name is Alex. I need help with order ORD-789. "
            "It arrived damaged and I'd like a refund."
        ),
        tools=TOOL_NAMES,
        system_prompt=SYSTEM_PROMPT,
        budget=RunBudget(max_steps=12, max_tokens=8000, max_cost_usd=0.10, timeout_seconds=60),
    )
    result1 = await engine.run(run1)
    print(f"Status:       {result1.status}")
    print(f"Final answer: {result1.final_answer[:120] if result1.final_answer else 'N/A'}...")
    print("User facts stored in memory ↑ (name: Alex)")

    # ── Run 2 ──────────────────────────────────────────────────────────────────
    print("\n[RUN 2] Same user, new session — agent should greet Alex by name")
    print("─" * 60)

    run2 = AgentRun(
        agent_id=agent_id,
        session_id="memory_demo_sess_002",   # different session
        user_id=user_id,                      # same user
        input="Hi, what's the status of the refund I requested earlier?",
        tools=TOOL_NAMES,
        system_prompt=SYSTEM_PROMPT,
        budget=RunBudget(max_steps=8, max_tokens=5000, max_cost_usd=0.05, timeout_seconds=60),
    )
    result2 = await engine.run(run2)
    print(f"Status:       {result2.status}")
    print(f"Final answer: {result2.final_answer[:200] if result2.final_answer else 'N/A'}")

    name_used = result2.final_answer and "alex" in result2.final_answer.lower()
    outcome = "greeted Alex by name" if name_used else "did NOT use the name Alex"
    print(f"\n{'✓ PASS' if name_used else '✗ FAIL'} — Agent {outcome}")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Customer Support Agent demo")
    parser.add_argument(
        "--scenario",
        default=None,
        help=f"Scenario name. Options: {[s.name for s in SCENARIOS]}. Omit to run all.",
    )
    parser.add_argument(
        "--memory-demo",
        action="store_true",
        help="Run Phase 2 memory persistence demo (requires Layer 2 on localhost:8080)",
    )
    args = parser.parse_args()

    engine = build_engine()

    if args.memory_demo:
        await run_memory_demo(engine)
    elif args.scenario:
        await run_scenario(engine, args.scenario)
    else:
        await run_all(engine)


if __name__ == "__main__":
    asyncio.run(main())
