"""
7 named demo scenarios for the Customer Support Agent.
These are LIVE DEMO scripts — not eval cases (eval cases are in evals/datasets/).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Scenario:
    name: str
    description: str
    user_id: str
    session_id: str
    input: str
    expected_status: str       # completed | escalated | failed
    notes: str = ""


SCENARIOS: list[Scenario] = [
    Scenario(
        name="eligible_refund",
        description="Order within 30-day window, damaged item — straightforward approval",
        user_id="user_demo_001",
        session_id="sess_demo_001",
        input=(
            "Hi, I received my order ORD-789 last week and the item arrived damaged. "
            "The headphones have a cracked case. I'd like a full refund please."
        ),
        expected_status="completed",
        notes="Agent should call order_lookup → refund_policy_search → refund_request",
    ),
    Scenario(
        name="ineligible_refund",
        description="Order outside 30-day refund window — policy says no",
        user_id="user_demo_002",
        session_id="sess_demo_002",
        input=(
            "I want to return order ORD-001 and get my money back. "
            "The cables stopped working."
        ),
        expected_status="completed",
        notes="Agent should look up order, check policy, explain ineligibility (Nov 2025 purchase).",
    ),
    Scenario(
        name="missing_order_id",
        description="User never provides order ID — agent must ask",
        user_id="user_demo_003",
        session_id="sess_demo_003",
        input="I want a refund for the thing I bought from you guys.",
        expected_status="completed",
        notes="Agent must ask for order ID before calling any tools.",
    ),
    Scenario(
        name="frustrated_customer",
        description="Angry customer with valid refund claim — agent stays professional",
        user_id="user_demo_004",
        session_id="sess_demo_004",
        input=(
            "This is absolutely ridiculous! Order ORD-789 arrived broken and nobody "
            "is helping me! I want my $89.99 back RIGHT NOW or I'm disputing the charge!"
        ),
        expected_status="completed",
        notes="Agent de-escalates, validates claim, processes refund without escalating to human.",
    ),
    Scenario(
        name="tool_timeout_retry",
        description="order_lookup times out once, succeeds on retry",
        user_id="user_demo_005",
        session_id="sess_demo_005",
        input=(
            "I need a refund for order ORD-789-SLOW. The product was defective."
        ),
        expected_status="completed",
        notes=(
            "First order_lookup call times out (simulated). "
            "Tool executor retries and succeeds. Final status should still be completed."
        ),
    ),
    Scenario(
        name="policy_conflict_nonrefundable",
        description="Order within window but item is non-refundable digital product",
        user_id="user_demo_006",
        session_id="sess_demo_006",
        input=(
            "I bought a software license (order ORD-NONREFUND) two weeks ago and "
            "I want to return it. I haven't used it yet."
        ),
        expected_status="completed",
        notes="Agent should find digital policy exception, explain no refund is possible.",
    ),
    Scenario(
        name="fraud_risk_escalation",
        description="Large order + suspicious pattern → agent escalates to human",
        user_id="user_demo_007",
        session_id="sess_demo_007",
        input=(
            "I need an immediate refund on order ORD-FRAUD for $1499.99. "
            "The laptop never arrived even though tracking says delivered. "
            "This is the third time this has happened to me."
        ),
        expected_status="escalated",
        notes=(
            "High-value order + repeated claim pattern → agent should detect fraud risk "
            "and call escalate_to_human."
        ),
    ),
]

SCENARIOS_BY_NAME: dict[str, Scenario] = {s.name: s for s in SCENARIOS}
