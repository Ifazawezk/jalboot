"""What the model is told about each tool, and how arguments are checked.

Arguments are validated in code against these definitions. An argument that is not
listed is refused rather than ignored, because a call that says customer_id=C-2,
skip_limits=true or approved_by=manager is an attack, not a typo.

No tool takes a customer id. The customer always comes from the conversation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from jalboot.policy.engine import CREDIT_REASONS

REFUND_REASONS = [
    "missing_item", "wrong_item", "damaged_item", "spoiled_item", "quality", "cold_food",
    "chilled_item", "expired_product", "cold_chain", "allergen", "foreign_object",
    "broken_seal", "illness", "not_received", "modifier_missed", "substitute_rejected",
    "duplicate_charge", "late_delivery_fee", "failed_contact_refund", "whole_wrong_order",
    "driver_change_short",
]
TICKET_CATEGORIES = [
    "late_delivery", "missing_item", "wrong_item", "refund_status", "promo_issue",
    "address_change", "payment_issue", "driver_conduct", "pharmacy_prescription",
    "parcel_lost", "account", "other",
]
HANDOFF_REASONS = [
    "safety", "account_security", "customer_request", "upset_customer", "legal_threat",
    "agent_complaint", "policy_requires_person", "rule_conflict", "repeated_failure",
    "low_confidence",
]
PRIORITIES = ["P1", "P2", "P3", "P4"]
# ESC-01. The model may suggest a priority, but a safety reason is always P1.
DEFAULT_PRIORITY = {
    "safety": "P1", "account_security": "P1", "legal_threat": "P2", "agent_complaint": "P3",
    "policy_requires_person": "P3", "rule_conflict": "P3", "repeated_failure": "P3",
    "upset_customer": "P3", "customer_request": "P4", "low_confidence": "P4",
}


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    properties: dict[str, dict[str, Any]]
    required: tuple[str, ...] = ()
    needs_identity: bool = True
    writes: bool = False
    # Changes what a customer pays or gets. It runs only if the customer asked (agent/consent.py).
    moves_money: bool = False

    def openai(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.properties,
                    "required": list(self.required),
                    "additionalProperties": False,
                },
            },
        }


ORDER_ID = {"type": "string", "description": "The order number, such as JB-500007"}
ITEMS = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "quantity": {"type": "integer", "description": "Units of this item affected in total"},
        },
        "required": ["name"],
        "additionalProperties": False,
    },
    "description": "The affected items. Give quantity for any item with more than one unit. Required for an item claim.",
}
REASON_GUIDE = (
    " Reasons: missing_item, wrong_item, damaged_item, spoiled_item, quality (stale, soggy), cold_food, "
    "chilled_item, expired_product, cold_chain, allergen, foreign_object, broken_seal, illness, "
    "not_received (nothing arrived), modifier_missed (a chosen option was ignored), substitute_rejected, "
    "duplicate_charge (charged twice), late_delivery_fee (delivery fee on a very late order), "
    "failed_contact_refund (delivery failed at the door), whole_wrong_order (the bag was someone else's), "
    "driver_change_short (the driver could not give full change on a cash order)."
)

TOOLS = {
    spec.name: spec
    for spec in (
        ToolSpec(
            "get_customer_profile",
            "Read the signed-in customer's tier, wallet balance, recent orders and saved address labels.",
            {},
        ),
        ToolSpec(
            "track_order",
            "Get the live status and estimated arrival of one of the customer's orders.",
            {"order_id": ORDER_ID},
            ("order_id",),
            writes=True,
        ),
        ToolSpec(
            "get_order_details",
            "Get items, prices, fees, payment and delivery details of one of the customer's orders.",
            {"order_id": ORDER_ID},
            ("order_id",),
            writes=True,
        ),
        ToolSpec(
            "explain_delay",
            "Get why an order is late, how late it is and any late credit that is due.",
            {"order_id": ORDER_ID},
            ("order_id",),
            writes=True,
        ),
        ToolSpec(
            "quote_refund",
            "Work out exactly what a claim is worth. Always use this before issue_refund, and "
            "refund the amount it returns. Do not calculate refunds yourself." + REASON_GUIDE,
            {
                "order_id": ORDER_ID,
                "reason": {"type": "string", "enum": REFUND_REASONS},
                "items": ITEMS,
            },
            ("order_id", "reason"),
        ),
        ToolSpec(
            "issue_refund",
            "Refund money on a delivered order. Small refunds run at once; others wait for a person.",
            {
                "order_id": ORDER_ID,
                "amount_qar": {"type": "number", "description": "Amount in QAR"},
                "reason": {"type": "string", "enum": REFUND_REASONS},
                "items": ITEMS,
                "method": {
                    "type": "string", "enum": ["original", "refund_credit"],
                    "description": "Where the money goes, if the customer chose",
                },
            },
            ("order_id", "amount_qar", "reason"),
            writes=True,
            moves_money=True,
        ),
        ToolSpec(
            "issue_credit",
            "Add credit to the customer's wallet for an order, for lateness, a merchant cancellation, an expired item or goodwill.",
            {
                "order_id": ORDER_ID,
                "amount_qar": {"type": "number", "description": "Amount in QAR"},
                "reason": {"type": "string", "enum": list(CREDIT_REASONS)},
            },
            ("order_id", "amount_qar", "reason"),
            writes=True,
            moves_money=True,
        ),
        ToolSpec(
            "apply_promo",
            "Check a promo code and apply it to the customer's open basket. A code cannot be added to a placed order.",
            {
                "code": {"type": "string", "description": "The promo code"},
                "order_id": {**ORDER_ID, "description": "The order the customer means, if they name one"},
            },
            ("code",),
            writes=True,
            moves_money=True,
        ),
        ToolSpec(
            "change_address",
            "Move an active order to a new address, before it is picked up.",
            {
                "order_id": ORDER_ID,
                "new_address": {"type": "string", "description": "The address as the customer gave it"},
            },
            ("order_id", "new_address"),
            writes=True,
            moves_money=True,
        ),
        ToolSpec(
            "cancel_order",
            "Cancel an active order. If a charge applies, the first call returns the terms; "
            "call again with confirm_charge true after the customer agrees.",
            {
                "order_id": ORDER_ID,
                "reason": {"type": "string", "description": "Why the customer is cancelling"},
                "confirm_charge": {"type": "boolean", "description": "True once the customer accepted the charge"},
            },
            ("order_id",),
            writes=True,
            moves_money=True,
        ),
        ToolSpec(
            "create_ticket",
            "Open a ticket for the support team to follow up.",
            {
                "category": {"type": "string", "enum": TICKET_CATEGORIES},
                "details": {"type": "string", "description": "What the customer needs"},
                "order_id": ORDER_ID,
                "priority": {"type": "string", "enum": PRIORITIES},
            },
            ("category", "details"),
            needs_identity=False,
            writes=True,
        ),
        ToolSpec(
            "handoff_to_human",
            "Connect the customer with a person and stop automated replies.",
            {
                "reason": {"type": "string", "enum": HANDOFF_REASONS},
                "summary": {"type": "string", "description": "The order number, what was checked and what was offered"},
                "priority": {"type": "string", "enum": PRIORITIES},
            },
            ("reason", "summary"),
            needs_identity=False,
            writes=True,
        ),
        ToolSpec(
            "search_knowledge",
            "Search the help pages. Use this when the sources given do not cover the question.",
            {"query": {"type": "string"}},
            ("query",),
            needs_identity=False,
        ),
    )
}

MAX_TEXT = 2000
MAX_LINES = 50
MAX_AMOUNT_QAR = 1_000_000


def _claim_line(entry: Any) -> bool:
    if not isinstance(entry, dict) or set(entry) - {"name", "quantity"}:
        return False
    name, quantity = entry.get("name"), entry.get("quantity")
    good_name = isinstance(name, str) and bool(name.strip()) and len(name) <= 200
    good_quantity = quantity is None or (isinstance(quantity, int) and not isinstance(quantity, bool) and quantity > 0)
    return good_name and good_quantity


TYPE_CHECKS = {
    "string": lambda v: isinstance(v, str) and bool(v.strip()),
    # JSON from a model can hold NaN, Infinity or 1e308, and no amount of money is any of them.
    "number": lambda v: (
        isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and abs(v) <= MAX_AMOUNT_QAR
    ),
    "boolean": lambda v: isinstance(v, bool),
    "array": lambda v: isinstance(v, list) and len(v) <= MAX_LINES and all(_claim_line(entry) for entry in v),
}


def validate(spec: ToolSpec, arguments: dict[str, Any]) -> str | None:
    """Returns an error code, or None when the arguments are acceptable."""
    for name in arguments:
        if name not in spec.properties:
            return "unknown_argument"
    for name in spec.required:
        if name not in arguments:
            return "missing_argument"
    for name, value in arguments.items():
        schema = spec.properties[name]
        if not TYPE_CHECKS[schema["type"]](value):
            return "invalid_argument"
        if "enum" in schema and value not in schema["enum"]:
            return "invalid_argument"
        if isinstance(value, str) and len(value) > MAX_TEXT:
            return "invalid_argument"
    return None
