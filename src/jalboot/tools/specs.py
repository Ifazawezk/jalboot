"""What the model is told about each tool, and how arguments are checked.

Arguments are validated in code against these definitions. An argument that is not
listed is refused rather than ignored, because a call that says customer_id=C-2,
skip_limits=true or approved_by=manager is an attack, not a typo.

No tool takes a customer id. The customer always comes from the conversation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

REFUND_REASONS = [
    "missing_item", "wrong_item", "damaged_item", "spoiled_item", "quality", "cold_food",
    "chilled_item", "expired_product", "cold_chain", "allergen", "foreign_object",
    "broken_seal", "illness", "not_received", "modifier_missed", "substitute_rejected",
    "duplicate_charge", "late_delivery_fee", "failed_contact_refund", "whole_wrong_order",
]
CREDIT_REASONS = ["late_delivery", "goodwill"]
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
        ),
        ToolSpec(
            "get_order_details",
            "Get items, prices, fees, payment and delivery details of one of the customer's orders.",
            {"order_id": ORDER_ID},
            ("order_id",),
        ),
        ToolSpec(
            "explain_delay",
            "Get why an order is late, how late it is and any late credit that is due.",
            {"order_id": ORDER_ID},
            ("order_id",),
        ),
        ToolSpec(
            "quote_refund",
            "Work out exactly what a claim is worth. Always use this before issue_refund, and "
            "refund the amount it returns. Do not calculate refunds yourself.",
            {
                "order_id": ORDER_ID,
                "reason": {"type": "string", "enum": REFUND_REASONS},
                "items": {
                    "type": "array", "items": {"type": "string"},
                    "description": "Names of the affected items. Required for an item claim.",
                },
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
                "items": {
                    "type": "array", "items": {"type": "string"},
                    "description": "Names of the affected items. Required for an item claim.",
                },
                "method": {
                    "type": "string", "enum": ["original", "refund_credit"],
                    "description": "Where the money goes, if the customer chose",
                },
            },
            ("order_id", "amount_qar", "reason"),
            writes=True,
        ),
        ToolSpec(
            "issue_credit",
            "Add late credit or goodwill credit to the customer's wallet for an order.",
            {
                "order_id": ORDER_ID,
                "amount_qar": {"type": "number", "description": "Amount in QAR"},
                "reason": {"type": "string", "enum": CREDIT_REASONS},
            },
            ("order_id", "amount_qar", "reason"),
            writes=True,
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

TYPE_CHECKS = {
    "string": lambda v: isinstance(v, str) and bool(v.strip()),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "array": lambda v: isinstance(v, list) and all(isinstance(x, str) for x in v),
}
MAX_TEXT = 2000


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
