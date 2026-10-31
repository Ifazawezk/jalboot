"""Runs every tool call, and is the only code that changes customer data for the bot.

The model proposes; this module decides. For each call, in this order:

    1. the tool exists and its arguments match the definition exactly
    2. the conversation has passed the identity check, if the tool needs one
    3. the order belongs to the verified customer
    4. a repeat of the same action returns the first result and changes nothing
    5. the policy engine allows the action, sends it for approval, or refuses it
    6. the action and an audit row commit together, or neither does

An order that does not exist and an order that belongs to someone else give the same
answer, so order numbers cannot be probed. The customer always comes from the
conversation row, which only the identity check can set.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from jalboot import audit
from jalboot.db.models import (
    ActionRecord, Address, Approval, Conversation, Customer, Order, PromoRedemption, Refund, Ticket,
)
from jalboot.policy import engine
from jalboot.policy.engine import APPROVAL, DENY, ESCALATE, EXECUTE, HANDOFF_CODES, ItemFact
from jalboot.policy.rules import Rules, percent_of, to_dh, to_qar
from jalboot.security.redact import redact
from jalboot.text.normalize import normalize
from jalboot.tools import specs
from jalboot.tools.facts import COMPENSATION, claim_facts, order_count, order_facts, refunded_items

Publish = Callable[[dict[str, Any]], None]
# REF-03 and WRG-05: quality complaints pay half and never count toward the 70 percent rule.
PERCENT_RULES = {
    "quality": "wrong_items.quality_refund_pct",
    "cold_food": "wrong_items.quality_refund_pct",
    "modifier_missed": "wrong_items.modifier_miss_refund_pct",
}
NO_FULL_REFUND_CONVERSION = set(PERCENT_RULES) | {"substitute_rejected"}
NUMBER = re.compile(r"\d+")
ORDER_NUMBER = re.compile(r"\b[A-Z]{1,3}-\d{3,}\b", re.I)
LABEL_WORDS = {
    "home": ("home", "my house", "بيتي", "البيت", "منزلي", "المنزل"),
    "work": ("work", "office", "دوامي", "الدوام", "عملي", "العمل", "مكتبي", "المكتب"),
}
EARTH_KM = 6371.0
DOHA = timezone(timedelta(hours=3))
# Facts on file that a model needs to answer well. Listed here so that a new field
# reaches the model because someone chose it, not by accident.
ORDER_FACTS = (
    "promo_code", "proof_of_delivery", "gps_distance_m", "leave_at_door", "failed_contact", "driver_wait_minutes",
    "driver_calls", "left_for_safety", "severe_weather", "cancelled_by", "credit_paid_dh", "open_bank_dispute",
    "pending_bank_amount_dh", "charges", "last_tracking_update_at", "declared_value_dh", "recipient_refused",
    "refused_reason", "scheduled_slot_at", "driver_change_short_dh",
)
ITEM_FACTS = (
    "offer", "charged_units", "substitute_for", "customer_approved", "contains", "prescription", "cold_chain",
    "chilled", "modifier", "missed_modifier", "shelf_life_days_at_delivery",
)
PREPICKUP_LOCKED = {"picked_up", "on_the_way", "delivered", "cancelled", "failed_customer"}
DELAY_TEXT = {
    "merchant_backlog": {"en": "the merchant had a backlog of orders", "ar": "كان لدى المتجر طلبات كثيرة قيد التحضير"},
    "driver_traffic": {"en": "heavy traffic on the route", "ar": "ازدحام مروري على الطريق"},
    "weather_dust": {"en": "dust and low visibility", "ar": "غبار وضعف في الرؤية"},
    "high_demand": {"en": "very high demand in the area", "ar": "طلب مرتفع جدا في المنطقة"},
    "address_problem": {"en": "the driver had trouble finding the address", "ar": "واجه السائق صعوبة في الوصول إلى العنوان"},
    "driver_reassigned": {"en": "the order was moved to another driver", "ar": "تم تحويل الطلب إلى سائق آخر"},
}


class Knowledge(Protocol):
    def search(self, query: str, language: str, k: int = 4) -> list[dict[str, Any]]: ...


@dataclass
class ToolContext:
    session: Session
    conversation: Conversation
    rules: Rules
    now: datetime
    knowledge: Knowledge | None = None
    publish: Publish = lambda _event: None
    actor: str = "support-bot"
    # Identifies this turn, so a charge can only be confirmed in a later one.
    turn_id: str = ""
    # True in the baseline comparison only. See evaluation/baseline.py.
    unguarded: bool = False
    extras: dict[str, Any] = field(default_factory=dict)


def doha_time(moment: datetime | None) -> str | None:
    """GEN-02: every time is Doha time. A model handed UTC will repeat UTC to the customer."""
    return None if moment is None else moment.astimezone(DOHA).strftime("%Y-%m-%d %H:%M Doha time")


def refused(code: str, **details: Any) -> dict[str, Any]:
    return {"ok": False, "error": code, **details}


def conflict(code: str) -> dict[str, Any]:
    """GEN-04 step 6. Nothing was changed, and the agent loop connects a person."""
    return refused("needs_person", rule=code, handoff_required="rule_conflict")


def action_key(*parts: Any) -> str:
    text = json.dumps(parts, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def new_id(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(4).upper()}"


def distance_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lng1, lat2, lng2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 2 * EARTH_KM * math.asin(math.sqrt(h))


class ToolExecutor:
    def __init__(self, context: ToolContext):
        self.ctx = context
        self.session = context.session
        self.conversation = context.conversation
        self.rules = context.rules
        self.now = context.now
        self._outbox: list[dict[str, Any]] = []

    def specs(self) -> list[dict[str, Any]]:
        return [spec.openai() for spec in specs.TOOLS.values()]

    @property
    def customer(self) -> Customer | None:
        """The verified customer. Both columns are set only by the identity check."""
        if self.conversation.customer_id and self.conversation.verified_at:
            return self.session.get(Customer, self.conversation.customer_id)
        return None

    def allowed_contacts(self) -> list[str]:
        customer = self.customer
        return [customer.phone, customer.email] if customer else []

    def execute(self, name: str, arguments: dict[str, Any], *, malformed: bool = False) -> dict[str, Any]:
        spec = specs.TOOLS.get(name)
        if spec is None:
            return self._block(name, arguments, refused("unknown_tool"))
        if malformed:
            return self._block(name, arguments, refused("arguments_not_valid_json"))
        problem = specs.validate(spec, arguments)
        if problem:
            return self._block(name, arguments, refused(problem))
        if spec.needs_identity and self.customer is None and not self.ctx.unguarded:
            return self._block(name, arguments, refused("identity_required"))
        handler = getattr(self, f"_{name}")
        with audit.serial_write(self.session):
            result = handler(**arguments)
            if result.get("ok") is False:
                self._audit("guardrail.blocked", "denied", name, arguments, result)
            else:
                self._audit(self._action_name(name, result), self._outcome(result), name, arguments, result)
        for event in self._outbox:
            self.ctx.publish(event)
        self._outbox.clear()
        return result

    def _block(self, name: str, arguments: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
        with audit.serial_write(self.session):
            self._audit("guardrail.blocked", "denied", name, arguments, result)
        return result

    @staticmethod
    def _action_name(name: str, result: dict[str, Any]) -> str:
        if name in {"issue_refund", "issue_credit"}:
            if result.get("status") == "pending_approval":
                return "refund.proposed"
            return "refund.auto_approved"
        return "handoff.requested" if name == "handoff_to_human" else "tool.called"

    @staticmethod
    def _outcome(result: dict[str, Any]) -> str:
        return "pending" if result.get("status") == "pending_approval" else "allowed"

    def _audit(self, action: str, outcome: str, tool: str, arguments: dict[str, Any], result: dict[str, Any]) -> None:
        safe_args = {
            key: redact(value)[0] if isinstance(value, str) else value for key, value in arguments.items()
        }
        audit.record(
            self.session,
            actor_type="bot",
            actor_id=self.ctx.actor,
            action=action,
            outcome=outcome,
            conversation_id=self.conversation.id,
            customer_id=self.conversation.customer_id,
            order_id=str(arguments.get("order_id")) if arguments.get("order_id") else None,
            detail={
                "tool": tool,
                "args": safe_args,
                "status": result.get("status", ""),
                "error": result.get("error", ""),
                "replayed": bool(result.get("replayed")),
            },
        )

    def _owned_order(self, order_id: str) -> Order | None:
        customer = self.customer
        order = self.session.get(Order, order_id.strip().upper())
        if order is None:
            return None
        if self.ctx.unguarded:
            return order
        if customer is None or order.customer_id != customer.id:
            return None
        return order

    def _replay(self, key: str) -> dict[str, Any] | None:
        record = self.session.get(ActionRecord, key)
        return None if record is None else {**record.result, "replayed": True}

    def _remember(self, key: str, tool: str, result: dict[str, Any]) -> dict[str, Any]:
        self.session.add(ActionRecord(
            key=key, tool=tool, conversation_id=self.conversation.id, result=result, created_at=self.now,
        ))
        return result

    def _lang(self) -> str:
        return self.conversation.language if self.conversation.language in ("en", "ar") else "en"

    def _order_view(self, order: Order) -> dict[str, Any]:
        merchant = order.merchant
        driver = order.driver
        arabic = self._lang() == "ar"
        return {
            "order_id": order.id,
            "vertical": order.category,
            "status": order.status,
            "store": (merchant.name_ar if arabic and merchant.name_ar else merchant.name) if merchant else "",
            "placed_at": doha_time(order.placed_at),
            "promised_at": doha_time(order.promised_at),
            "delivered_at": doha_time(order.delivered_at),
            # A driver's first name only: their record is not the customer's to read.
            "rider": driver.name.split()[0] if driver else None,
        }

    # Reads

    def _get_customer_profile(self) -> dict[str, Any]:
        customer = self.customer
        if customer is None:
            return self._all_orders_refused()
        orders = self.session.scalars(
            select(Order).where(Order.customer_id == customer.id).order_by(Order.placed_at.desc()).limit(5)
        ).all()
        return {
            "ok": True,
            "name": customer.name_ar if self._lang() == "ar" and customer.name_ar else customer.name,
            "tier": customer.tier,
            "wallet_qar": to_qar(customer.wallet_dh),
            "recent_orders": [
                {"order_id": o.id, "status": o.status, "vertical": o.category, "placed_at": doha_time(o.placed_at)}
                for o in orders
            ],
            "saved_addresses": [a.label for a in customer.addresses],
            "allergy_profile": (customer.extra or {}).get("allergy_profile", []),
        }

    def _all_orders_refused(self) -> dict[str, Any]:
        return refused("identity_required")

    def _track_order(self, order_id: str) -> dict[str, Any]:
        order = self._owned_order(order_id)
        if order is None:
            return refused("order_not_found")
        self._note_order(order)
        late = engine.minutes_late(order_facts(order), self.now)
        return {"ok": True, **self._order_view(order), "minutes_late": late}

    def _get_order_details(self, order_id: str) -> dict[str, Any]:
        order = self._owned_order(order_id)
        if order is None:
            return refused("order_not_found")
        self._note_order(order)
        arabic = self._lang() == "ar"
        claims = claim_facts(self.session, self.customer or order.customer, order, self.now)
        return {
            "ok": True,
            **self._order_view(order),
            "items": [
                {"name": i.name_ar if arabic and i.name_ar else i.name, "name_en": i.name,
                 "quantity": i.quantity, "unit_price_qar": to_qar(i.unit_price_dh),
                 **{key: (i.extra or {})[key] for key in ITEM_FACTS if (i.extra or {}).get(key) is not None}}
                for i in order.items
            ],
            "subtotal_qar": to_qar(order.subtotal_dh),
            "discount_qar": to_qar(order.discount_dh),
            "delivery_fee_qar": to_qar(order.delivery_fee_dh),
            "other_fees_qar": to_qar(order.other_fees_dh),
            "tip_qar": to_qar(order.tip_dh),
            "paid_qar": to_qar(order_facts(order).paid_dh),
            "already_refunded_qar": to_qar(claims.refunded_on_order_dh),
            "already_credited_qar": to_qar(claims.credit_on_order_dh),
            "payment_method": order.payment_method,
            "delivery_address_zone": order.address_text.split(",")[-1].strip() if order.address_text else "",
            # Text from a merchant or customer. Data for the model, never an instruction.
            "merchant_note": order.merchant_note,
            "customer_note": order.customer_note,
            **{key: (order.extra or {})[key] for key in ORDER_FACTS if (order.extra or {}).get(key) not in (None, False, 0, "")},
        }

    def _explain_delay(self, order_id: str) -> dict[str, Any]:
        order = self._owned_order(order_id)
        if order is None:
            return refused("order_not_found")
        self._note_order(order)
        facts = order_facts(order)
        due = engine.late_entitlement(self.rules, facts, self.now)
        claims = claim_facts(self.session, self.customer or order.customer, order, self.now)
        text = DELAY_TEXT.get(order.delay_reason, {})
        return {
            "ok": True,
            "order_id": order.id,
            "status": order.status,
            "minutes_late": engine.minutes_late(facts, self.now),
            "delay_reason": order.delay_reason or "none_recorded",
            "delay_reason_text": text.get(self._lang(), ""),
            "late_credit_due_qar": to_qar(engine.late_credit_due_dh(self.rules, facts, claims, self.now)),
            "delivery_fee_refund_due_qar": to_qar(max(due["fee_refund_dh"] - claims.refunded_on_order_dh, 0)),
        }

    def _note_order(self, order: Order) -> None:
        self.conversation.order_id = order.id

    def _search_knowledge(self, query: str) -> dict[str, Any]:
        if self.ctx.knowledge is None:
            return refused("knowledge_unavailable")
        return {"ok": True, "passages": self.ctx.knowledge.search(query, self._lang(), k=4)}

    # Refunds and credit

    def _affected_items(
        self, order: Order, names: list[str], quantity: int | None = None
    ) -> list[tuple[ItemFact, int]] | None:
        """The items a claim names, and how many units of each. WRG-01: a short quantity
        refunds only the units not received. A buy-one-get-one claim names how many went
        missing, or it counts as one, which is the free unit."""
        facts = order_facts(order)
        rows = list(zip(order.items, facts.items))
        affected = []
        for name in names:
            wanted = normalize(name).strip()
            match = None
            for row, fact in rows:
                labels = [normalize(label).strip() for label in (row.name, row.name_ar) if label]
                if any(wanted == label or (len(wanted) >= 3 and (wanted in label or label in wanted)) for label in labels):
                    match = fact
                    break
            if match is None:
                return None
            default = 1 if match.free_units else match.quantity
            affected.append((match, min(quantity or default, match.quantity)))
        return affected

    def _entitlement_dh(
        self, order: Order, reason: str, names: list[str], quantity: int | None = None
    ) -> tuple[int | None, str | None]:
        """The most this claim can be worth, from the order's own prices. It stops a
        model paying the automated limit for a missing cup of tea."""
        facts = order_facts(order)
        claims = claim_facts(self.session, self.customer, order, self.now)
        if reason == "failed_contact_refund" or (reason == "not_received" and order.status == "failed_customer"):
            return engine.failed_contact_refund_dh(self.rules, facts, claims), None
        if reason == "not_received":
            return engine.full_refund_dh(facts, claims, delivered=False), None
        if reason == "driver_change_short":
            return facts.change_short_dh, None
        if reason == "whole_wrong_order":
            return engine.full_refund_dh(facts, claims), None
        if reason == "duplicate_charge":
            return engine.duplicate_amount_dh(facts), None
        if reason == "late_delivery_fee":
            due = engine.late_entitlement(self.rules, facts, self.now)["fee_refund_dh"]
            return (due, None) if due else (None, "no_fee_refund_due")
        if not names:
            return None, "items_required"
        affected = self._affected_items(order, names, quantity)
        if affected is None:
            return None, "item_not_in_order"
        if reason == "substitute_rejected" and any(item.approved_substitute for item, _ in affected):
            # GRC-04: an approved substitute is only rejected if it is damaged, spoiled or expired.
            return None, "approved_substitute"
        billed = [(item, engine.refundable_units(item, units)) for item, units in affected]
        if not any(units for _, units in billed):
            return None, "no_refund_value"
        already = refunded_items(self.session, order.id)
        if any(normalize(item.name).strip() in already for item, _ in affected):
            return None, "item_already_refunded"
        # An older refund can have no item names. One of exactly this value is taken to
        # be this same item, so it is not paid twice on a guess.
        unnamed = int((order.extra or {}).get("prior_refunded_dh", 0))
        if unnamed and sum(engine.net_item_refund_dh(facts, item, q) for item, q in billed) == unnamed:
            return None, "already_refunded"
        offer = any(item.free_units for item, _ in affected)
        if reason not in NO_FULL_REFUND_CONVERSION and not offer and engine.full_refund_applies(self.rules, facts, billed):
            return engine.full_refund_dh(facts, claims), None
        total = sum(engine.net_item_refund_dh(facts, item, units) for item, units in billed)
        if reason in PERCENT_RULES:
            total = percent_of(total, self.rules.get(PERCENT_RULES[reason]))
        return total, None

    def _quote_refund(
        self, order_id: str, reason: str, items: list[str] | None = None, quantity: int | None = None
    ) -> dict[str, Any]:
        """Arithmetic belongs in code. Net prices and the 70 percent rule are exactly
        what a model gets wrong, so it asks here. This holds no approval limits, which
        are internal (ESC-03)."""
        order = self._owned_order(order_id)
        if order is None:
            return refused("order_not_found")
        entitled, problem = self._entitlement_dh(order, reason, list(items or []), quantity)
        if problem:
            return refused(problem)
        return {"ok": True, "order_id": order.id, "reason": reason, "amount_qar": to_qar(entitled or 0)}

    def _issue_refund(
        self, order_id: str, amount_qar: float, reason: str, items: list[str] | None = None,
        method: str | None = None, quantity: int | None = None,
    ) -> dict[str, Any]:
        order = self._owned_order(order_id)
        if order is None:
            return refused("order_not_found")
        amount = to_dh(amount_qar)
        # Keyed on the order's own item names, so "fries" and "Fries, large" are one
        # item and a different spelling cannot refund it twice.
        affected = self._affected_items(order, items) if items else None
        names = sorted({normalize(item.name).strip() for item, _ in affected or ()})
        key = action_key("refund", order.id, reason, names)
        previous = self._replay(key)
        if previous is not None:
            return previous
        if self.ctx.unguarded:
            return self._pay_refund(key, order, amount, reason, names, "unguarded", method=method)

        decision = engine.decide_refund(
            self.rules, order_facts(order), claim_facts(self.session, self.customer, order, self.now),
            amount, reason, self._reported_at(), photo_provided=bool((order.extra or {}).get("photo_evidence")),
        )
        if decision.outcome == DENY:
            return refused(decision.code, **self._limit(decision))
        if decision.outcome == ESCALATE:
            return conflict(decision.code)
        entitled, problem = self._entitlement_dh(order, reason, list(items or []), quantity)
        if problem:
            return refused(problem)
        if entitled is not None and amount > entitled:
            return refused("above_item_value", max_qar=to_qar(entitled))
        if decision.outcome == EXECUTE:
            return self._pay_refund(key, order, amount, reason, names, "policy", method=method)
        result = self._ask_person(key, "refund", order, amount, reason, names, decision, "issue_refund")
        if decision.code in HANDOFF_CODES:
            return {**result, "handoff_required": "policy_requires_person"}
        return result

    def _reported_at(self) -> datetime:
        """GEN-02: a request counts from when the customer first reported the issue."""
        return self.conversation.first_report_at or self.now

    def _limit(self, decision: engine.Decision) -> dict[str, Any]:
        # Internal limits are never handed to the model, so they cannot be quoted (ESC-03).
        return {"max_qar": to_qar(decision.limit_dh)} if decision.code in {
            "amount_exceeds_paid", "above_late_credit_due", "credit_cap_per_order",
        } else {}

    def _pay_refund(
        self, key: str, order: Order, amount: int, reason: str, names: list[str], approved_by: str,
        approval_id: str | None = None, method: str | None = None,
    ) -> dict[str, Any]:
        # REF-04: a cash order is only ever refunded as credit.
        method = "refund_credit" if order.payment_method == "cash" else (method or "original")
        # REF-04: on a mixed payment the card part goes back first, then the credit part.
        credit_part = amount if method == "refund_credit" else 0
        paid_by_credit = int((order.extra or {}).get("credit_paid_dh") or 0)
        if method == "original" and paid_by_credit:
            credit_part = max(amount - (order_facts(order).paid_dh - paid_by_credit), 0)
        refund = Refund(
            id=new_id("R"), order_id=order.id, customer_id=order.customer_id, amount_dh=amount,
            method=method, reason=reason, items=names, approved_by=approved_by, approval_id=approval_id,
            created_at=self.now, idempotency_key=key,
        )
        self.session.add(refund)
        order.customer.wallet_dh += credit_part
        result = {
            "ok": True, "status": "done", "refund_id": refund.id, "order_id": order.id,
            "amount_qar": to_qar(amount), "method": method, "reason": reason,
            "to_original_payment_qar": to_qar(amount - credit_part), "to_credit_qar": to_qar(credit_part),
        }
        self._publish_refund(refund.id, order.id, amount, "auto_approved")
        return self._remember(key, "issue_refund", result)

    def _ask_person(
        self, key: str, kind: str, order: Order, amount: int, reason: str, names: list[str],
        decision: engine.Decision, tool: str,
    ) -> dict[str, Any]:
        """Nothing is paid here. A person must decide, through the desk."""
        approval = Approval(
            id=new_id("AP"), kind=kind, conversation_id=self.conversation.id, customer_id=order.customer_id,
            order_id=order.id, amount_dh=amount, reason=reason,
            payload={"reason": reason, "items": names, "tool": tool, "rule": decision.code},
            required_role=decision.required_role or "agent", created_at=self.now, idempotency_key=key,
        )
        self.session.add(approval)
        self.session.flush()
        result = {
            "ok": True, "status": "pending_approval", "approval_id": approval.id, "order_id": order.id,
            "amount_qar": to_qar(amount), "reason": reason,
        }
        self._publish_refund(approval.id, order.id, amount, "pending")
        self._outbox.append({"type": "approval.created", "approvalId": approval.id})
        return self._remember(key, tool, result)

    def _publish_refund(self, refund_id: str, order_id: str, amount: int, status: str) -> None:
        self._outbox.append({
            "type": "refund.update",
            "refund": {
                "id": refund_id, "orderId": order_id, "amountQar": to_qar(amount), "status": status,
                "decidedBy": None, "note": None,
            },
        })

    def _issue_credit(self, order_id: str, amount_qar: float, reason: str) -> dict[str, Any]:
        order = self._owned_order(order_id)
        if order is None:
            return refused("order_not_found")
        amount = to_dh(amount_qar)
        key = action_key("credit", order.id, reason)
        previous = self._replay(key)
        if previous is not None:
            return previous
        if self.ctx.unguarded:
            return self._pay_credit(key, order, amount, reason, "unguarded")
        decision = engine.decide_credit(
            self.rules, order_facts(order), claim_facts(self.session, self.customer, order, self.now),
            amount, reason, self._reported_at(),
        )
        if decision.outcome == DENY:
            return refused(decision.code, **self._limit(decision))
        if decision.outcome == ESCALATE:
            return conflict(decision.code)
        if decision.outcome == APPROVAL:
            return self._ask_person(key, "credit", order, amount, reason, [], decision, "issue_credit")
        return self._pay_credit(key, order, amount, reason, "policy")

    def _pay_credit(self, key: str, order: Order, amount: int, reason: str, approved_by: str) -> dict[str, Any]:
        refund = Refund(
            id=new_id("R"), order_id=order.id, customer_id=order.customer_id, amount_dh=amount,
            method=COMPENSATION, reason=reason, approved_by=approved_by, created_at=self.now,
            idempotency_key=key,
        )
        self.session.add(refund)
        order.customer.wallet_dh += amount
        result = {
            "ok": True, "status": "done", "refund_id": refund.id, "order_id": order.id,
            "amount_qar": to_qar(amount), "method": COMPENSATION, "reason": reason,
        }
        self._publish_refund(refund.id, order.id, amount, "auto_approved")
        return self._remember(key, "issue_credit", result)

    # Orders

    def _apply_promo(self, code: str, order_id: str | None = None) -> dict[str, Any]:
        customer = self.customer
        code = code.strip().upper()
        target = None
        if order_id:
            target = self._owned_order(order_id)
            if target is None:
                return refused("order_not_found")
        basket = target or self.session.scalar(
            select(Order).where(Order.customer_id == customer.id, Order.status == "basket").limit(1)
        )
        category = basket.category if basket else "food"
        eligible = 0
        if basket is not None:
            # A basket can hold only a total, so that stands in when it has no item rows.
            eligible = sum(
                item.unit_dh * item.quantity for item in order_facts(basket).items if item.promo_eligible
            ) if basket.items else basket.subtotal_dh
        month = self.now.strftime("%Y-%m")
        used = self.session.scalars(
            select(PromoRedemption).where(PromoRedemption.customer_id == customer.id, PromoRedemption.code == code)
        ).all()
        if code not in self.rules.get("promos.codes"):
            return refused("unknown_code")
        decision = engine.promo_decision(
            self.rules, code,
            order_placed=target is not None and target.status != "basket",
            category=category,
            eligible_subtotal_dh=eligible,
            now=self.now,
            used_this_month=any(row.period == month for row in used),
            used_ever=bool(used),
            has_delivered_order=order_count(self.session, customer.id, "delivered") > 0,
        )
        if decision.outcome == DENY:
            promo = self.rules.get("promos.codes").get(code) or {}
            detail = {"valid_until": promo["valid_until"]} if decision.code == "code_expired" else {}
            return refused(decision.code, **detail)
        if basket is None:
            return refused("no_open_basket")
        key = action_key("promo", customer.id, code, month)
        previous = self._replay(key)
        if previous is not None:
            return previous
        discount = engine.promo_discount_dh(self.rules, code, eligible, basket.delivery_fee_dh)
        period = "once" if self.rules.get("promos.codes")[code]["limit"] == "once_per_account" else month
        self.session.add(PromoRedemption(
            code=code, period=period, customer_id=customer.id, order_id=basket.id, amount_dh=discount,
            created_at=self.now,
        ))
        basket.discount_dh += discount
        basket.total_dh -= discount
        return self._remember(key, "apply_promo", {
            "ok": True, "status": "done", "code": code, "order_id": basket.id,
            "discount_qar": to_qar(discount),
        })

    def _match_saved_address(self, text: str) -> Address | None:
        """Finds the saved address a customer means, by its street and building numbers
        or by a word for its label. Free text that matches nothing returns None."""
        folded = normalize(ORDER_NUMBER.sub(" ", text))
        numbers = set(NUMBER.findall(folded))
        for address in self.customer.addresses:
            if numbers and numbers <= set(NUMBER.findall(normalize(address.line))):
                return address
        # A street and building number that match nothing mean a new address, whatever
        # else the text says. "Street 777, near my aunt's house" is not Home.
        if numbers:
            return None
        words = set(folded.split())
        for address in self.customer.addresses:
            label = address.label.strip().lower()
            if {normalize(term) for term in LABEL_WORDS.get(label, (label,))} & words:
                return address
        return None

    def _change_address(self, order_id: str, new_address: str) -> dict[str, Any]:
        order = self._owned_order(order_id)
        if order is None:
            return refused("order_not_found")
        clean = redact(new_address)[0]
        key = action_key("address", order.id, normalize(clean))
        previous = self._replay(key)
        if previous is not None:
            return previous
        if self.ctx.unguarded:
            order.address_text = clean
            return {"ok": True, "status": "done", "order_id": order.id, "new_address": clean}
        if order.category == "parcel":
            return self._reroute_parcel(key, order, clean)
        if order.status in PREPICKUP_LOCKED:
            return refused("address_locked_after_pickup")
        # ACC-03 does not say whether a change is allowed once promised_at has passed.
        if order.promised_at is not None and self.now > order.promised_at:
            return conflict("address_change_after_promised_at")
        extra = dict(order.extra or {})
        if int(extra.get("address_changes", 0)) >= int(self.rules.get("account.address_change.max_per_order")):
            return refused("address_change_limit_reached")
        if any((item.extra or {}).get("prescription") or (item.extra or {}).get("cold_chain") for item in order.items):
            return refused("address_change_not_allowed_for_this_order")

        target = self._match_saved_address(clean)
        if target is None:
            return self._ask_about_new_address(key, order, clean)

        origin = self.session.get(Address, order.address_id) if order.address_id else None
        pin = (origin.lat, origin.lng) if origin else (extra.get("pin_lat"), extra.get("pin_lng"))
        if pin[0] is not None:
            limit = float(self.rules.get("account.address_change.max_distance_km"))
            # Rounded so that exactly 2 km stays allowed despite floating point.
            if round(distance_km(pin, (target.lat, target.lng)), 3) > limit:
                return refused("new_address_too_far")
        extra["address_changes"] = int(extra.get("address_changes", 0)) + 1
        order.extra = extra
        order.address_id = target.id
        order.address_text = target.line
        return self._remember(key, "change_address", {
            "ok": True, "status": "done", "order_id": order.id, "label": target.label,
        })

    def _ask_about_new_address(self, key: str, order: Order, clean: str) -> dict[str, Any]:
        """A new address cannot be measured against the policy here, and an unchecked
        address change is a classic way to steal an order, so a person looks at it."""
        decision = engine.Decision(APPROVAL, "new_address_needs_person", "agent")
        pending = self._ask_person(key, "address_change", order, 0, "address_change", [], decision, "change_address")
        approval = self.session.get(Approval, pending["approval_id"])
        approval.payload = {**approval.payload, "new_address": clean}
        return pending

    def _reroute_parcel(self, key: str, order: Order, clean: str) -> dict[str, Any]:
        """ACC-03: free before pickup, and QAR 10 after it. The 2 km limit is for meals
        and groceries, not parcels."""
        if order.status in {"delivered", "cancelled", "failed_customer"}:
            return refused("address_locked_after_pickup")
        target = self._match_saved_address(clean)
        if target is None:
            return self._ask_about_new_address(key, order, clean)
        moved = order.status in {"picked_up", "on_the_way"}
        fee = self.rules.dh("parcels.reroute_fee_qar") if moved else 0
        extra = dict(order.extra or {})
        extra["reroute_fee_dh"] = int(extra.get("reroute_fee_dh", 0)) + fee
        order.extra = extra
        order.address_id = target.id
        order.address_text = target.line
        return self._remember(key, "change_address", {
            "ok": True, "status": "done", "order_id": order.id, "label": target.label, "fee_qar": to_qar(fee),
        })

    def _cancel_order(
        self, order_id: str, reason: str | None = None, confirm_charge: bool = False
    ) -> dict[str, Any]:
        order = self._owned_order(order_id)
        if order is None:
            return refused("order_not_found")
        key = action_key("cancel", order.id)
        previous = self._replay(key)
        if previous is not None:
            return previous
        # CAN-01: the charge is set by the status when the customer first asked, so
        # confirming a moment later cannot cost more.
        if order.status not in self.rules.get("general.terminal_statuses"):
            extra = dict(order.extra or {})
            extra.setdefault("status_at_first_request", order.status)
            order.extra = extra
        terms = engine.cancellation_terms(self.rules, order_facts(order), self.now)
        if self.ctx.unguarded:
            terms = {"allowed": True, "code": "unguarded", "charge_dh": 0, "refund_dh": order_facts(order).paid_dh}
        if terms.get("escalate"):
            return conflict(terms["code"])
        if not terms["allowed"]:
            return refused(terms["code"])
        if terms["charge_dh"] > 0 and not self._charge_confirmed(order, terms, confirm_charge):
            return {
                "ok": True, "status": "needs_confirmation", "order_id": order.id,
                "charge_qar": to_qar(terms["charge_dh"]), "refund_qar": to_qar(terms["refund_dh"]),
            }
        order.status = "cancelled"
        order.extra = {**(order.extra or {}), "cancelled_by": "customer"}
        if order.payment_method == "cash" and terms["charge_dh"] > 0:
            # CAN-05: nothing was collected, so a charge becomes a balance on the account.
            owner = order.customer
            owner.extra = {
                **(owner.extra or {}),
                "outstanding_balance_dh": int((owner.extra or {}).get("outstanding_balance_dh", 0)) + terms["charge_dh"],
            }
        if terms["refund_dh"] > 0:
            method = "refund_credit" if order.payment_method == "cash" else "original"
            self.session.add(Refund(
                id=new_id("R"), order_id=order.id, customer_id=order.customer_id, amount_dh=terms["refund_dh"],
                method=method, reason="customer_cancelled", approved_by="policy", created_at=self.now,
                idempotency_key=key,
            ))
        return self._remember(key, "cancel_order", {
            "ok": True, "status": "done", "order_id": order.id, "charge_qar": to_qar(terms["charge_dh"]),
            "refund_qar": to_qar(terms["refund_dh"]), "rule": terms["code"],
        })

    def _charge_confirmed(self, order: Order, terms: dict[str, Any], confirm_charge: bool) -> bool:
        """A customer has to see the charge before agreeing to it, so a confirmation
        only counts in a later turn than the quote. The model cannot confirm for them."""
        quote_key = action_key("cancel-quote", order.id, terms["charge_dh"])
        quote = self.session.get(ActionRecord, quote_key)
        if quote is None:
            self._remember(quote_key, "cancel_quote", {"turn": self.ctx.turn_id})
            return False
        return confirm_charge and quote.result.get("turn") != self.ctx.turn_id

    # People

    def _create_ticket(
        self, category: str, details: str, order_id: str | None = None, priority: str = "P4"
    ) -> dict[str, Any]:
        order = None
        if order_id:
            order = self._owned_order(order_id)
            if order is None:
                return refused("order_not_found")
        key = action_key("ticket", self.conversation.id, category, order.id if order else "")
        previous = self._replay(key)
        if previous is not None:
            return previous
        clean = redact(details)[0]
        ticket = Ticket(
            id=new_id("T"), customer_id=self.conversation.customer_id, order_id=order.id if order else None,
            conversation_id=self.conversation.id, category=category, priority=priority, status="open",
            subject=clean[:200], body=clean, language=self._lang(), source="bot", created_at=self.now,
            idempotency_key=key,
        )
        self.session.add(ticket)
        return self._remember(key, "create_ticket", {
            "ok": True, "status": "done", "ticket_id": ticket.id, "category": category,
        })

    def _handoff_to_human(self, reason: str, summary: str, priority: str | None = None) -> dict[str, Any]:
        conversation = self.conversation
        if conversation.status in {"waiting", "agent"}:
            return {"ok": True, "status": "done", "replayed": True}
        floor = specs.DEFAULT_PRIORITY[reason]
        # A model can raise the priority, but it cannot lower a safety case.
        chosen = min(priority or floor, floor) if floor in {"P1", "P2"} else (priority or floor)
        conversation.status = "waiting"
        conversation.handoff_reason = reason
        conversation.handoff_summary = redact(summary)[0]
        conversation.handoff_at = self.now
        conversation.priority = chosen
        conversation.failures = 0
        self._outbox.append({
            "type": "handoff.update",
            "handoff": {"status": "queued", "agentName": None, "etaMinutes": None, "position": None},
        })
        return {"ok": True, "status": "done", "reason": reason, "priority": chosen}
