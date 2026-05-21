"""
Customer Support Agent — mocked tool implementations.

All tools return deterministic mock data keyed on their inputs so demo
scenarios are reproducible without any external dependencies.
"""
from __future__ import annotations

import asyncio
import random
from typing import Any

from pydantic import BaseModel

from engine.tools.schemas import ToolDefinition

# ── Input / Output schemas ─────────────────────────────────────────────────────

class OrderLookupInput(BaseModel):
    order_id: str

class OrderDetails(BaseModel):
    order_id: str
    status: str
    items: list[dict[str, Any]]
    total_amount: float
    purchase_date: str
    delivery_date: str | None
    customer_id: str

class RefundPolicyInput(BaseModel):
    query: str

class PolicyResult(BaseModel):
    policy_text: str
    eligible_conditions: list[str]
    exceptions: list[str]
    max_refund_window_days: int

class RefundRequestInput(BaseModel):
    order_id: str
    reason: str
    amount_usd: float

class RefundResult(BaseModel):
    refund_id: str
    status: str
    estimated_days: int

class TicketCreateInput(BaseModel):
    subject: str
    description: str
    priority: str

class TicketResult(BaseModel):
    ticket_id: str
    status: str
    assigned_team: str

class EscalateInput(BaseModel):
    reason: str
    urgency: str

class EscalationResult(BaseModel):
    escalation_id: str
    assigned_agent: str
    wait_time_minutes: int
    reason: str  # echoed back so engine can store it

# ── Mock data ──────────────────────────────────────────────────────────────────

_ORDERS: dict[str, dict] = {
    "ORD-789": {
        "order_id": "ORD-789",
        "status": "delivered",
        "items": [{"name": "Wireless Headphones", "qty": 1, "price": 89.99}],
        "total_amount": 89.99,
        "purchase_date": "2026-04-25",
        "delivery_date": "2026-04-28",
        "customer_id": "CUST-001",
    },
    "ORD-001": {
        "order_id": "ORD-001",
        "status": "delivered",
        "items": [{"name": "USB-C Cable", "qty": 2, "price": 12.00}],
        "total_amount": 24.00,
        "purchase_date": "2025-11-01",        # outside 30-day window
        "delivery_date": "2025-11-04",
        "customer_id": "CUST-002",
    },
    "ORD-FRAUD": {
        "order_id": "ORD-FRAUD",
        "status": "delivered",
        "items": [{"name": "Laptop", "qty": 1, "price": 1499.99}],
        "total_amount": 1499.99,
        "purchase_date": "2026-05-10",
        "delivery_date": "2026-05-13",
        "customer_id": "CUST-FRAUD",
    },
    "ORD-NONREFUND": {
        "order_id": "ORD-NONREFUND",
        "status": "delivered",
        "items": [{"name": "Downloaded Software License", "qty": 1, "price": 49.99}],
        "total_amount": 49.99,
        "purchase_date": "2026-05-01",
        "delivery_date": "2026-05-01",
        "customer_id": "CUST-003",
    },
}

_REFUND_POLICIES: dict[str, dict] = {
    "default": {
        "policy_text": (
            "Items may be returned within 30 days of purchase for a full refund "
            "if they are defective, damaged, or not as described."
        ),
        "eligible_conditions": ["damaged", "defective", "not as described", "wrong item"],
        "exceptions": ["digital downloads", "software licenses", "perishables"],
        "max_refund_window_days": 30,
    },
    "digital": {
        "policy_text": (
            "Digital products and software licenses are non-refundable once "
            "the license key has been delivered."
        ),
        "eligible_conditions": [],
        "exceptions": ["all digital goods"],
        "max_refund_window_days": 0,
    },
}

_PROCESSED_REFUNDS: set[str] = set()

# ── Tool functions ─────────────────────────────────────────────────────────────

# Scenario 5 uses a timeout simulation: first call to ORD-789 times out
_order_lookup_call_count: dict[str, int] = {}

async def _order_lookup(inp: OrderLookupInput) -> dict:
    _order_lookup_call_count[inp.order_id] = _order_lookup_call_count.get(inp.order_id, 0) + 1

    # Scenario 5: simulate timeout on first call for ORD-789-SLOW
    if inp.order_id == "ORD-789-SLOW" and _order_lookup_call_count[inp.order_id] == 1:
        await asyncio.sleep(999)  # will be cancelled by timeout

    order = _ORDERS.get(inp.order_id)
    if order is None:
        return {}  # triggers empty_result error
    return order


async def _refund_policy_search(inp: RefundPolicyInput) -> dict:
    query_lower = inp.query.lower()
    if any(word in query_lower for word in ["digital", "software", "download", "license"]):
        return _REFUND_POLICIES["digital"]
    return _REFUND_POLICIES["default"]


async def _refund_request(inp: RefundRequestInput) -> dict:
    order = _ORDERS.get(inp.order_id)
    if order is None:
        return {}  # order not found

    if inp.order_id in _PROCESSED_REFUNDS:
        return {}  # duplicate request → empty result

    if inp.amount_usd > order["total_amount"]:
        return {}  # amount exceeds original

    _PROCESSED_REFUNDS.add(inp.order_id)
    refund_id = f"REF-{random.randint(10000, 99999)}"
    return {
        "refund_id": refund_id,
        "status": "approved",
        "estimated_days": 5,
    }


async def _ticket_create(inp: TicketCreateInput) -> dict:
    ticket_id = f"TKT-{random.randint(10000, 99999)}"
    return {
        "ticket_id": ticket_id,
        "status": "open",
        "assigned_team": "customer-support",
    }


async def _escalate_to_human(inp: EscalateInput) -> dict:
    return {
        "escalation_id": f"ESC-{random.randint(1000, 9999)}",
        "assigned_agent": "Senior Support Agent",
        "wait_time_minutes": 5,
        "reason": inp.reason,
    }

# ── ToolDefinition objects ─────────────────────────────────────────────────────

ORDER_LOOKUP = ToolDefinition(
    name="order_lookup",
    description=(
        "Look up an order by order ID. Returns order status, items, total amount, "
        "purchase date, delivery date, and customer ID. "
        "Call this before processing any refund."
    ),
    input_schema=OrderLookupInput,
    output_schema=OrderDetails,
    fn=_order_lookup,
    timeout_seconds=5,
    max_retries=2,
    permission_level="read",
    on_timeout="fail",
    on_error="return_structured_error",
)

REFUND_POLICY_SEARCH = ToolDefinition(
    name="refund_policy_search",
    description=(
        "Search the refund policy knowledge base. Provide a plain-English query "
        "describing the situation (e.g. 'damaged item return', 'software license refund'). "
        "Returns applicable policy text and eligibility conditions."
    ),
    input_schema=RefundPolicyInput,
    output_schema=PolicyResult,
    fn=_refund_policy_search,
    timeout_seconds=5,
    max_retries=1,
    permission_level="read",
    on_error="return_structured_error",
)

REFUND_REQUEST = ToolDefinition(
    name="refund_request",
    description=(
        "Submit a refund request for an order. Requires a verified order ID, the "
        "reason for the refund, and the refund amount in USD. "
        "Always call order_lookup and refund_policy_search before calling this."
    ),
    input_schema=RefundRequestInput,
    output_schema=RefundResult,
    fn=_refund_request,
    timeout_seconds=10,
    max_retries=1,
    permission_level="write",
    on_error="return_structured_error",
)

TICKET_CREATE = ToolDefinition(
    name="ticket_create",
    description=(
        "Create a support ticket for issues that cannot be resolved immediately. "
        "Provide a subject, detailed description, and priority (low/medium/high/urgent)."
    ),
    input_schema=TicketCreateInput,
    output_schema=TicketResult,
    fn=_ticket_create,
    timeout_seconds=10,
    max_retries=1,
    permission_level="write",
    on_error="return_structured_error",
)

ESCALATE_TO_HUMAN = ToolDefinition(
    name="escalate_to_human",
    description=(
        "Escalate this conversation to a human support agent. Use when: "
        "(1) fraud risk is detected, "
        "(2) the customer is abusive or threatening, "
        "(3) the issue exceeds your authority to resolve. "
        "Provide the reason and urgency (low/medium/high/critical)."
    ),
    input_schema=EscalateInput,
    output_schema=EscalationResult,
    fn=_escalate_to_human,
    timeout_seconds=5,
    max_retries=0,
    permission_level="escalate",
    on_error="fail",
)

ALL_TOOLS = [
    ORDER_LOOKUP,
    REFUND_POLICY_SEARCH,
    REFUND_REQUEST,
    TICKET_CREATE,
    ESCALATE_TO_HUMAN,
]
