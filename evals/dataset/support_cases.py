"""
Support Agent eval dataset — 20 benchmark cases.

All cases use the mock tool data from demos/support_agent/tools.py:
  ORD-789      delivered 2026-04-28, $89.99 headphones, eligible for refund
  ORD-001      delivered 2025-11-04, $24.00 USB cables,  OUTSIDE 30-day window
  ORD-FRAUD    delivered 2026-05-13, $1499.99 laptop,    fraud-flagged account
  ORD-NONREFUND delivered 2026-05-01, $49.99 software,  digital — non-refundable
"""
from __future__ import annotations

from engine.evals.base import EvalCase

SUPPORT_CASES: list[EvalCase] = [

    # ── Simple lookups ─────────────────────────────────────────────────────────

    EvalCase(
        case_id="support_001",
        description="Basic order status check — no refund requested",
        agent_id="support_agent",
        input="What's the status of my order ORD-789?",
        expected_status="completed",
        expected_tools_called=["order_lookup"],
        unexpected_tools_called=["refund_request"],
        answer_must_contain=["delivered", "ORD-789"],
        max_cost_usd=0.05,
        tags=["order_lookup", "simple"],
    ),

    EvalCase(
        case_id="support_002",
        description="Order status for out-of-window order",
        agent_id="support_agent",
        input="Can you check my order ORD-001?",
        expected_status="completed",
        expected_tools_called=["order_lookup"],
        answer_must_contain=["ORD-001"],
        max_cost_usd=0.05,
        tags=["order_lookup", "simple"],
    ),

    EvalCase(
        case_id="support_003",
        description="Customer asks vague question — no order ID provided",
        agent_id="support_agent",
        input="I need help with my order.",
        expected_status="completed",
        unexpected_tools_called=["refund_request"],
        max_cost_usd=0.05,
        tags=["clarification", "no_tools"],
    ),

    EvalCase(
        case_id="support_004",
        description="Customer asks what the agent can help with",
        agent_id="support_agent",
        input="What can you help me with?",
        expected_status="completed",
        unexpected_tools_called=["refund_request", "escalate_to_human"],
        max_cost_usd=0.04,
        tags=["no_tools", "greeting"],
    ),

    # ── Refund — eligible ──────────────────────────────────────────────────────

    EvalCase(
        case_id="support_005",
        description="Eligible refund — delivered order, damage claim",
        agent_id="support_agent",
        input="My order ORD-789 arrived damaged. I'd like a refund.",
        expected_status="completed",
        expected_tools_called=["order_lookup", "refund_request"],
        answer_must_contain=["refund"],
        answer_must_not_contain=["cannot process", "not eligible"],
        max_cost_usd=0.08,
        tags=["refund", "eligible"],
    ),

    EvalCase(
        case_id="support_006",
        description="Eligible refund — wrong item received",
        agent_id="support_agent",
        input="I received the wrong item for ORD-789. I ordered headphones but got something else.",
        expected_status="completed",
        expected_tools_called=["order_lookup", "refund_request"],
        answer_must_contain=["refund"],
        max_cost_usd=0.08,
        tags=["refund", "eligible", "wrong_item"],
    ),

    EvalCase(
        case_id="support_007",
        description="Eligible refund — item not as described",
        agent_id="support_agent",
        input="The headphones I got with ORD-789 are completely different from what was shown online. Can I get my money back?",
        expected_status="completed",
        expected_tools_called=["order_lookup", "refund_request"],
        answer_must_contain=["refund"],
        max_cost_usd=0.08,
        tags=["refund", "eligible"],
    ),

    # ── Refund — ineligible ────────────────────────────────────────────────────

    EvalCase(
        case_id="support_008",
        description="Ineligible refund — outside 30-day window",
        agent_id="support_agent",
        input="I want to return my USB cables from order ORD-001.",
        expected_status="completed",
        expected_tools_called=["order_lookup", "refund_policy_search"],
        unexpected_tools_called=["refund_request"],
        answer_must_contain=["30"],
        max_cost_usd=0.08,
        tags=["refund", "ineligible", "expired"],
        notes="ORD-001 was purchased 2025-11-01 — well outside the 30-day window",
    ),

    EvalCase(
        case_id="support_009",
        description="Ineligible refund — digital product non-refundable",
        agent_id="support_agent",
        input="I want a refund for my software license ORD-NONREFUND. I don't like it.",
        expected_status="completed",
        expected_tools_called=["order_lookup", "refund_policy_search"],
        unexpected_tools_called=["refund_request"],
        answer_must_not_contain=["refund approved", "refund processed"],
        max_cost_usd=0.08,
        tags=["refund", "ineligible", "digital"],
        notes="Digital products are explicitly non-refundable in policy",
    ),

    EvalCase(
        case_id="support_010",
        description="Refund policy question — no specific order",
        agent_id="support_agent",
        input="What is your return policy?",
        expected_status="completed",
        expected_tools_called=["refund_policy_search"],
        unexpected_tools_called=["refund_request"],
        answer_must_contain=["30"],
        max_cost_usd=0.06,
        tags=["policy", "no_order"],
    ),

    EvalCase(
        case_id="support_011",
        description="Refund policy for digital products specifically",
        agent_id="support_agent",
        input="Can I return a digital download I just bought?",
        expected_status="completed",
        expected_tools_called=["refund_policy_search"],
        answer_must_not_contain=["refund approved"],
        max_cost_usd=0.06,
        tags=["policy", "digital"],
    ),

    # ── Escalation ─────────────────────────────────────────────────────────────

    EvalCase(
        case_id="support_012",
        description="Fraud-flagged account — must escalate",
        agent_id="support_agent",
        input="I need a refund for my order ORD-FRAUD.",
        expected_status="escalated",
        expected_tools_called=["order_lookup", "escalate_to_human"],
        max_cost_usd=0.08,
        tags=["escalation", "fraud"],
        notes="ORD-FRAUD triggers escalation path",
    ),

    EvalCase(
        case_id="support_013",
        description="Customer explicitly demands human agent",
        agent_id="support_agent",
        input="I don't want to talk to a bot. I need a real person right now.",
        expected_status="escalated",
        expected_tools_called=["escalate_to_human"],
        max_cost_usd=0.06,
        tags=["escalation", "human_request"],
    ),

    EvalCase(
        case_id="support_014",
        description="Angry customer with fraud order demands immediate resolution",
        agent_id="support_agent",
        input="This is absolutely unacceptable! My order ORD-FRAUD is fraudulent and I want this resolved immediately or I'm calling my bank!",
        expected_status="escalated",
        expected_tools_called=["escalate_to_human"],
        max_cost_usd=0.08,
        tags=["escalation", "fraud", "angry_customer"],
    ),

    # ── Edge cases ─────────────────────────────────────────────────────────────

    EvalCase(
        case_id="support_015",
        description="Order ID not found in system",
        agent_id="support_agent",
        input="What's the status of order ORD-9999?",
        expected_status="completed",
        expected_tools_called=["order_lookup"],
        unexpected_tools_called=["refund_request"],
        max_cost_usd=0.06,
        tags=["order_lookup", "not_found"],
        notes="ORD-9999 does not exist in mock data — agent should handle gracefully",
    ),

    EvalCase(
        case_id="support_016",
        description="Customer asks for refund without providing order ID",
        agent_id="support_agent",
        input="I want a refund please.",
        expected_status="completed",
        unexpected_tools_called=["refund_request"],
        max_cost_usd=0.06,
        tags=["refund", "missing_info"],
        notes="Agent must ask for order ID before calling any tools",
    ),

    EvalCase(
        case_id="support_017",
        description="Multi-step: check order then request refund",
        agent_id="support_agent",
        input="First tell me the status of ORD-789, then process a refund for it — it was damaged.",
        expected_status="completed",
        expected_tools_called=["order_lookup", "refund_request"],
        answer_must_contain=["refund"],
        max_cost_usd=0.10,
        tags=["refund", "multi_step", "eligible"],
    ),

    EvalCase(
        case_id="support_018",
        description="Customer provides all info upfront — should be efficient",
        agent_id="support_agent",
        input="Order ORD-789 arrived damaged, I want a refund for $89.99.",
        expected_status="completed",
        expected_tools_called=["order_lookup", "refund_request"],
        answer_must_contain=["refund"],
        max_cost_usd=0.08,
        tags=["refund", "eligible", "efficient"],
        notes="Agent should not ask for info already provided",
    ),

    EvalCase(
        case_id="support_019",
        description="Tracking / delivery date question",
        agent_id="support_agent",
        input="When was my order ORD-789 delivered?",
        expected_status="completed",
        expected_tools_called=["order_lookup"],
        answer_must_contain=["ORD-789"],
        unexpected_tools_called=["refund_request", "escalate_to_human"],
        max_cost_usd=0.05,
        tags=["order_lookup", "delivery"],
    ),

    EvalCase(
        case_id="support_020",
        description="Customer mentions their name — user memory extraction",
        agent_id="support_agent",
        input="Hi, my name is Alex. I need help with order ORD-789.",
        expected_status="completed",
        expected_tools_called=["order_lookup"],
        answer_must_contain=["ORD-789"],
        max_cost_usd=0.06,
        tags=["order_lookup", "user_memory"],
        notes="Agent should acknowledge Alex and look up the order",
    ),
]

# Engineering agent cases — populated in Phase 5
ENGINEERING_CASES: list[EvalCase] = []
