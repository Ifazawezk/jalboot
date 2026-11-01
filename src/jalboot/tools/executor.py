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
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from jalboot import audit
from jalboot.db.models import (
    ActionRecord, Address, Approval, Conversation, Customer, Order, PromoRedemption, Ticket,
)
from jalboot.policy import engine
from jalboot.policy.engine import APPROVAL, DENY, ESCALATE, EXECUTE, HANDOFF_CODES, ItemFact
from jalboot.policy.rules import Rules, percent_of, to_dh, to_qar
from jalboot.security.redact import redact
from jalboot.text.normalize import normalize
from jalboot.tools import specs
from jalboot.tools.approvals import LOCKED_AFTER_PICKUP
from jalboot.tools.facts import (
    COMPENSATION, claim_facts, order_count, order_facts, refunded_items, report_issues,
)
from jalboot.tools.settle import WalletFull, new_id, settle_credit, settle_refund

Publish = Callable[[dict[str, Any]], None]
# REF-03 and WRG-05: quality complaints pay half and never count toward the 70 percent rule.
PERCENT_RULES = {
    "quality": "wrong_items.quality_refund_pct",
    "cold_food": "wrong_items.quality_refund_pct",
    "modifier_missed": "wrong_items.modifier_miss_refund_pct",
}
NO_FULL_REFUND_CONVERSION = set(PERCENT_RULES) | {"substitute_rejected"}
# SAF-03 and SAF-04: these are full-order refunds, even if only one item was affected.
FULL_ORDER_REASONS = {"allergen", "broken_seal", "illness"}
# These are about the order as a whole, so a list of items changes nothing about what is
# owed, and must not make a repeat look like a new claim.
WHOLE_ORDER_REASONS = FULL_ORDER_REASONS | {
    "duplicate_charge", "driver_change_short", "failed_contact_refund", "late_delivery_fee", "not_received",
    "whole_wrong_order",
}
# ACC-03 resets promised_at to the new time shown. The simulation has no routing, so
# this stands in for the time the app would show.
NEW_ADDRESS_ETA_MINUTES = 30
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
DELAY_TEXT = {
    "merchant_backlog": {"en": "the merchant had a backlog of orders", "ar": "كان لدى المتجر طلبات كثيرة قيد التحضير"},
    "driver_traffic": {"en": "heavy traffic on the route", "ar": "ازدحام مروري على الطريق"},
    "weather_dust": {"en": "dust and low visibility", "ar": "غبار وضعف في الرؤية"},
    "high_demand": {"en": "very high demand in the area", "ar": "ضغط كبير على الطلبات في المنطقة"},
    "address_problem": {"en": "the driver had trouble finding the address", "ar": "واجه المندوب صعوبة في الوصول إلى العنوان"},
    "driver_reassigned": {"en": "the order was moved to another driver", "ar": "تم تحويل الطلب إلى مندوب آخر"},
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
        if self._identity_missing(spec):
            return self._block(name, arguments, refused("identity_required"))
        handler = getattr(self, f"_{name}")
        if spec.writes:
            with audit.serial_write(self.session):
                result = handler(**arguments)
                self._audit_result(name, arguments, result)
        else:
            # A read holds up nobody, and a search may spend a while encoding the query.
            result = handler(**arguments)
            with audit.serial_write(self.session):
                self._audit_result(name, arguments, result)
        for event in self._outbox:
            self.ctx.publish(event)
        self._outbox.clear()
        return result

    def _audit_result(self, name: str, arguments: dict[str, Any], result: dict[str, Any]) -> None:
        if result.get("ok") is False:
            self._audit("guardrail.blocked", "denied", name, arguments, result)
        else:
            self._audit(self._action_name(name, result), self._outcome(result), name, arguments, result)

    def _identity_missing(self, spec: specs.ToolSpec) -> bool:
        return spec.needs_identity and self.customer is None

    def refuse(self, name: str, arguments: dict[str, Any], code: str, **details: Any) -> dict[str, Any]:
        """For a caller that stops a tool before it runs, so the refusal is still on record."""
        return self._block(name, arguments, refused(code, **details))

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
        if customer is None or order.customer_id != customer.id:
            return None
        return order

    def _replay(self, key: str) -> dict[str, Any] | None:
        record = self.session.get(ActionRecord, key)
        if record is None:
            return None
        result = {**record.result, "replayed": True}
        # A person may have decided since. The first answer is no longer the true one.
        approval = self.session.get(Approval, result["approval_id"]) if result.get("approval_id") else None
        if approval is not None and approval.status != "pending":
            result["status"] = "done" if approval.status == "approved" else "rejected"
        return result

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
            "rider": (driver.name_ar if arabic and driver.name_ar else driver.name).split()[0] if driver else None,
        }

    # Reads

    def _get_customer_profile(self) -> dict[str, Any]:
        customer = self.customer
        if customer is None:
            return refused("identity_required")
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
        claims = claim_facts(self.session, self.customer or order.customer, order, self.now, self.rules)
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
            "balance_owed_qar": to_qar(engine.failed_cash_balance_dh(self.rules, order_facts(order))),
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
        claims = claim_facts(self.session, self.customer or order.customer, order, self.now, self.rules)
        text = DELAY_TEXT.get(order.delay_reason, {})
        # A delay can be real and still be too old to pay for (LAT-01).
        since = engine.hours_since(order.delivered_at, self._reported_at(order, ["late"]))
        window = float(self.rules.get("refunds.windows_hours.late_credit"))
        open_claim = order.category == "parcel" or since is None or since <= window
        return {
            "ok": True,
            "order_id": order.id,
            "status": order.status,
            "minutes_late": engine.minutes_late(facts, self.now),
            "delay_reason": order.delay_reason or "none_recorded",
            "delay_reason_text": text.get(self._lang(), ""),
            "late_credit_due_qar": to_qar(engine.late_credit_due_dh(self.rules, facts, claims, self.now) if open_claim else 0),
            "delivery_fee_refund_due_qar": to_qar(max(due["fee_refund_dh"] - claims.late_fee_refunded_dh, 0) if open_claim else 0),
        }

    def _note_order(self, order: Order) -> None:
        self.conversation.order_id = order.id

    def _search_knowledge(self, query: str) -> dict[str, Any]:
        if self.ctx.knowledge is None:
            return refused("knowledge_unavailable")
        return {"ok": True, "passages": self.ctx.knowledge.search(query, self._lang(), k=4)}

    # Refunds and credit

    def _claim_lines(
        self, order: Order, items: list[dict[str, Any]],
    ) -> tuple[list[tuple[ItemFact, int]], str | None]:
        """Turns the items a claim names into order lines and units. Each order line is
        counted once however often it is named, so listing a QAR 4 tea eleven times is
        one QAR 4 tea. A name that could be two lines is refused rather than guessed."""
        rows = list(zip(order.items, order_facts(order).items))
        labels = [
            [normalize(text).strip() for text in (row.name, row.name_ar) if text] for row, _ in rows
        ]
        lines: dict[int, tuple[ItemFact, int]] = {}
        for entry in items:
            wanted = normalize(entry["name"]).strip()
            matches = [index for index, names in enumerate(labels) if wanted in names]
            if not matches and len(wanted) >= 3:
                matches = [
                    index for index, names in enumerate(labels)
                    if any(wanted in name or name in wanted for name in names)
                ]
            if not matches:
                return [], "item_not_in_order"
            if len(matches) > 1:
                return [], "ambiguous_item"
            index = matches[0]
            fact = rows[index][1]
            quantity = entry.get("quantity")
            if quantity is None:
                # WRG-01: a short quantity refunds only the units not received. A
                # buy-one-get-one claim counts as one, which is the free unit.
                if fact.quantity > 1 and not fact.free_units:
                    return [], "quantity_required"
                quantity = 1 if fact.free_units else fact.quantity
            units = min(quantity, fact.quantity)
            lines[index] = (fact, max(units, lines[index][1] if index in lines else 0))
        return list(lines.values()), None

    def _entitlement_dh(
        self, order: Order, reason: str, items: list[dict[str, Any]],
    ) -> tuple[int | None, str | None]:
        """The most this claim can be worth, from the order's own prices. It stops a
        model paying the automated limit for a missing cup of tea."""
        facts = order_facts(order)
        claims = claim_facts(self.session, self.customer or order.customer, order, self.now, self.rules)
        if reason == "late_delivery_fee":
            due = engine.late_entitlement(self.rules, facts, self.now)["fee_refund_dh"] - claims.late_fee_refunded_dh
            return (due, None) if due > 0 else (None, "no_fee_refund_due")
        if reason == "duplicate_charge":
            return max(engine.duplicate_amount_dh(facts) - claims.by_reason_dh.get(reason, 0), 0), None
        if reason == "driver_change_short":
            return max(facts.change_short_dh - claims.by_reason_dh.get(reason, 0), 0), None
        if order.category == "parcel" and reason != "failed_contact_refund":
            if reason not in engine.PARCEL_REASONS:
                return None, "reason_not_for_parcels"
            room = engine.parcel_room_dh(self.rules, facts, claims)
            return (room, None) if room else (None, "parcel_cover_used")
        if reason == "failed_contact_refund":
            amount = engine.failed_contact_refund_dh(self.rules, facts, claims) - claims.by_reason_dh.get(reason, 0)
            return (amount, None) if amount > 0 else (None, "nothing_to_refund")
        if reason == "not_received":
            return engine.full_refund_dh(facts, claims, delivered=False), None
        if reason == "whole_wrong_order" or reason in FULL_ORDER_REASONS:
            return engine.full_refund_dh(facts, claims), None
        if not items:
            return None, "items_required"
        affected, problem = self._claim_lines(order, items)
        if problem:
            return None, problem
        if reason == "substitute_rejected" and not all(item.substituted for item, _ in affected):
            return None, "no_substitution_on_line"
        if reason == "substitute_rejected" and any(item.approved_substitute for item, _ in affected):
            # GRC-04: an approved substitute is only rejected if it is damaged, spoiled or expired.
            return None, "approved_substitute"
        already = refunded_items(self.session, order.id)
        billed = []
        for item, units in affected:
            done = already.get(normalize(item.name).strip(), 0)
            billed.append((item, engine.refundable_units(item, units) - engine.refundable_units(item, done)))
        if not any(units > 0 for _, units in billed):
            return None, "item_already_refunded" if already else "no_refund_value"
        billed = [(item, units) for item, units in billed if units > 0]
        offer = any(item.free_units for item, _ in affected)
        if reason not in NO_FULL_REFUND_CONVERSION and not offer and engine.full_refund_applies(self.rules, facts, billed):
            return engine.full_refund_dh(facts, claims), None
        total = sum(engine.net_item_refund_dh(facts, item, units) for item, units in billed)
        if reason in PERCENT_RULES:
            total = percent_of(total, self.rules.get(PERCENT_RULES[reason]))
        return total, None

    def _quote_refund(self, order_id: str, reason: str, items: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        """Arithmetic belongs in code. Net prices and the 70 percent rule are exactly
        what a model gets wrong, so it asks here. This holds no approval limits, which
        are internal (ESC-03)."""
        order = self._owned_order(order_id)
        if order is None:
            return refused("order_not_found")
        reason = engine.claim_reason(order_facts(order), reason)
        entitled, problem = self._entitlement_dh(order, reason, list(items or []))
        if problem:
            return refused(problem)
        return {"ok": True, "order_id": order.id, "reason": reason, "amount_qar": to_qar(entitled or 0)}

    def _issue_refund(
        self, order_id: str, amount_qar: float, reason: str, items: list[dict[str, Any]] | None = None,
        method: str | None = None,
    ) -> dict[str, Any]:
        order = self._owned_order(order_id)
        if order is None:
            return refused("order_not_found")
        amount = to_dh(amount_qar)
        reason = engine.claim_reason(order_facts(order), reason)
        # Keyed on the order's own lines, not on the words used. The same unit is one
        # claim whatever it is called and whatever reason is given. The units are in the
        # key, so "now two are missing" is a new claim that pays only for the second.
        by_line = items and reason not in WHOLE_ORDER_REASONS and order.category != "parcel"
        affected = self._claim_lines(order, items)[0] if by_line else []
        names = sorted(
            ({"name": normalize(item.name).strip(), "units": units} for item, units in affected),
            key=lambda entry: entry["name"],
        )
        key = action_key("refund", order.id, names) if names else action_key("refund", order.id, reason)
        previous = self._replay(key)
        if previous is not None:
            return previous

        chilled = reason == "substitute_rejected" and any(item.chilled for item, _ in affected)
        window_reason = "chilled_item" if chilled else None
        issues = report_issues(reason, names)
        reported = self._reported_at(order, issues)
        decision = engine.decide_refund(
            self.rules, order_facts(order), claim_facts(self.session, self.customer, order, self.now, self.rules),
            amount, reason, reported, photo_provided=bool((order.extra or {}).get("photo_evidence")),
            window_reason=window_reason,
        )
        if decision.outcome == DENY:
            return refused(decision.code, **self._limit(decision))
        self._note_report(order, issues)
        if decision.outcome == ESCALATE:
            return conflict(decision.code)
        entitled, problem = self._entitlement_dh(order, reason, list(items or []))
        if problem:
            return refused(problem)
        if entitled is not None and amount > entitled:
            return refused("above_item_value", max_qar=to_qar(entitled))
        if decision.outcome == EXECUTE:
            return self._pay_refund(key, order, amount, reason, names, "policy", method)
        result = self._ask_person(
            key, "refund", order, amount, reason, names, decision, "issue_refund", method,
            reported_at=reported.isoformat(), window_reason=window_reason,
        )
        if decision.code in HANDOFF_CODES:
            return {**result, "handoff_required": "policy_requires_person"}
        return result

    def _note_report(self, order: Order, issues: list[str]) -> None:
        """GEN-02: a request counts from when the customer first reported the issue. The
        time starts when a claim is filed, because a quote or a question is not a claim."""
        extra = dict(order.extra or {})
        reports = dict(extra.get("first_reports") or {})
        for issue in issues:
            reports.setdefault(issue, self.now.isoformat())
        order.extra = {**extra, "first_reports": reports}

    def _reported_at(self, order: Order, issues: list[str]) -> datetime:
        """The newest of these reports, so adding a new issue to a claim cannot borrow
        an older issue's time. A report from before an order was delivered cannot be
        about its delivery."""
        reports = (order.extra or {}).get("first_reports") or {}
        floor = order.delivered_at or order.placed_at
        times = [datetime.fromisoformat(reports[issue]) if issue in reports else self.now for issue in issues]
        return max(moment if moment >= floor else self.now for moment in times)

    def _limit(self, decision: engine.Decision) -> dict[str, Any]:
        # Internal limits are never handed to the model, so they cannot be quoted (ESC-03).
        return {"max_qar": to_qar(decision.limit_dh)} if decision.code in {
            "amount_exceeds_paid", "above_credit_due", "credit_cap_per_order", "above_parcel_cover",
        } else {}

    def _pay_refund(
        self, key: str, order: Order, amount: int, reason: str, names: list[dict[str, Any]], approved_by: str,
        method: str | None,
    ) -> dict[str, Any]:
        try:
            settled = settle_refund(
                self.session, self.rules, order, amount, reason=reason, key=key, approved_by=approved_by,
                now=self.now, items=names, method=method,
            )
        except WalletFull:
            return conflict("wallet_at_limit")
        result = {
            "ok": True, "status": "done", "refund_id": settled.refund.id, "order_id": order.id,
            "amount_qar": to_qar(amount), "method": settled.refund.method, "reason": reason,
            "to_original_payment_qar": to_qar(settled.original_dh), "to_credit_qar": to_qar(settled.credit_dh),
        }
        self._publish_refund(settled.refund.id, order.id, amount, "auto_approved", settled.refund.method)
        return self._remember(key, "issue_refund", result)

    def _ask_person(
        self, key: str, kind: str, order: Order, amount: int, reason: str, names: list[dict[str, Any]],
        decision: engine.Decision, tool: str, method: str | None = None, **facts: Any,
    ) -> dict[str, Any]:
        """Nothing is paid here. A person must decide, through the desk."""
        approval = Approval(
            id=new_id("AP"), kind=kind, conversation_id=self.conversation.id, customer_id=order.customer_id,
            order_id=order.id, amount_dh=amount, reason=reason,
            payload={"reason": reason, "items": names, "tool": tool, "rule": decision.code, "method": method, **facts},
            required_role=decision.required_role or "agent", created_at=self.now, idempotency_key=key,
        )
        self.session.add(approval)
        self.session.flush()
        result = {
            "ok": True, "status": "pending_approval", "approval_id": approval.id, "order_id": order.id,
            "amount_qar": to_qar(amount), "reason": reason,
        }
        if kind != "address_change":
            self._publish_refund(approval.id, order.id, amount, "pending", "original")
        self._outbox.append({"type": "approval.created", "approvalId": approval.id})
        return self._remember(key, tool, result)

    def _publish_refund(self, refund_id: str, order_id: str, amount: int, status: str, method: str) -> None:
        """destination tells the card what to say: money and credit come back differently."""
        destination = "credit" if method in {"refund_credit", COMPENSATION} else "original"
        self._outbox.append({
            "type": "refund.update",
            "refund": {
                "id": refund_id, "orderId": order_id, "amountQar": to_qar(amount), "status": status,
                "decidedBy": None, "note": None, "destination": destination,
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
        issues = report_issues(reason, [])
        reported = self._reported_at(order, issues)
        decision = engine.decide_credit(
            self.rules, order_facts(order), claim_facts(self.session, self.customer, order, self.now, self.rules),
            amount, reason, reported, photo_provided=bool((order.extra or {}).get("photo_evidence")),
        )
        if decision.outcome == DENY:
            return refused(decision.code, **self._limit(decision))
        self._note_report(order, issues)
        if decision.outcome == ESCALATE:
            return conflict(decision.code)
        if decision.outcome == APPROVAL:
            return self._ask_person(
                key, "credit", order, amount, reason, [], decision, "issue_credit", reported_at=reported.isoformat(),
            )
        return self._pay_credit(key, order, amount, reason, "policy")

    def _pay_credit(self, key: str, order: Order, amount: int, reason: str, approved_by: str) -> dict[str, Any]:
        refund = settle_credit(self.session, order, amount, reason=reason, key=key, approved_by=approved_by, now=self.now)
        result = {
            "ok": True, "status": "done", "refund_id": refund.id, "order_id": order.id,
            "amount_qar": to_qar(amount), "method": COMPENSATION, "reason": reason,
        }
        self._publish_refund(refund.id, order.id, amount, "auto_approved", COMPENSATION)
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
        month = self.now.astimezone(DOHA).strftime("%Y-%m")
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
            zone=self._fee_zone(basket.address_text) if basket else None,
            base_fee_dh=basket.delivery_fee_dh if basket else 0,
            codes_on_order=len(self.session.scalars(
                select(PromoRedemption.id).where(PromoRedemption.order_id == basket.id)
            ).all()) if basket else 0,
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
        promo = self.rules.get("promos.codes")[code]
        if promo["type"] == "free_delivery" and basket.delivery_fee_dh == 0:
            return refused("delivery_already_free")
        discount = engine.promo_discount_dh(self.rules, code, eligible, basket.delivery_fee_dh)
        period = "once" if self.rules.get("promos.codes")[code]["limit"] == "once_per_account" else month
        self.session.add(PromoRedemption(
            code=code, period=period, customer_id=customer.id, order_id=basket.id, amount_dh=discount,
            created_at=self.now,
        ))
        # A free delivery code changes the fee and creates no promo discount (GEN-03).
        if promo["type"] == "free_delivery":
            basket.delivery_fee_dh = 0
        else:
            basket.discount_dh += discount
        basket.total_dh -= discount
        return self._remember(key, "apply_promo", {
            "ok": True, "status": "done", "code": code, "order_id": basket.id,
            "discount_qar": to_qar(discount),
        })

    def _fee_zone(self, address_text: str) -> str | None:
        area = address_text.rsplit(",", 1)[-1].strip()
        return engine.fee_zone(self.rules, area)

    def _zone_fee_dh(self, category: str, zone: str | None) -> int | None:
        if zone is None:
            return 0
        fee = self.rules.get("fees.delivery_fee_qar")[zone].get(category)
        return None if fee is None else to_dh(fee)

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
        # The move count is in the key: Work, Home, Work is three moves, not a repeat.
        moves = int((order.extra or {}).get("address_changes", 0))
        key = action_key("address", order.id, normalize(clean), moves)
        previous = self._replay(key)
        if previous is not None:
            return previous
        if order.category == "parcel":
            return self._reroute_parcel(key, order, clean)
        if order.status in LOCKED_AFTER_PICKUP:
            return refused("address_locked_after_pickup")
        # ACC-03 does not say whether a change is allowed once promised_at has passed.
        if order.promised_at is not None and self.now > order.promised_at:
            return conflict("address_change_after_promised_at")
        extra = dict(order.extra or {})
        target = self._match_saved_address(clean)
        if target is not None and order.address_id == target.id:
            return self._already_there(order, target)
        if int(extra.get("address_changes", 0)) >= int(self.rules.get("account.address_change.max_per_order")):
            return refused("address_change_limit_reached")
        if any((item.extra or {}).get("prescription") or (item.extra or {}).get("cold_chain") for item in order.items):
            return refused("address_change_not_allowed_for_this_order")

        if target is None:
            return self._ask_about_new_address(key, order, clean)

        origin = self.session.get(Address, order.address_id) if order.address_id else None
        pin = (origin.lat, origin.lng) if origin else (extra.get("pin_lat"), extra.get("pin_lng"))
        if pin[0] is not None:
            limit = float(self.rules.get("account.address_change.max_distance_km"))
            # Rounded so that exactly 2 km stays allowed despite floating point.
            if round(distance_km(pin, (target.lat, target.lng)), 3) > limit:
                return refused("new_address_too_far")
        new_fee = self._zone_fee_dh(order.category, self._fee_zone(target.line))
        if new_fee is None:
            return refused("zone_not_served")
        old_fee = self._zone_fee_dh(order.category, self._fee_zone(order.address_text)) or 0
        difference = max(new_fee - old_fee, 0) if new_fee and old_fee else 0
        extra["address_changes"] = int(extra.get("address_changes", 0)) + 1
        extra["address_fee_dh"] = int(extra.get("address_fee_dh", 0)) + difference
        if order.promised_at is not None:
            extra["original_promised_at"] = order.promised_at.isoformat()
            order.promised_at = self.now + timedelta(minutes=NEW_ADDRESS_ETA_MINUTES)
        order.extra = extra
        order.address_id = target.id
        order.address_text = target.line
        return self._remember(key, "change_address", {
            "ok": True, "status": "done", "order_id": order.id, "label": target.label,
            "fee_qar": to_qar(difference),
        })

    def _ask_about_new_address(self, key: str, order: Order, clean: str) -> dict[str, Any]:
        """A new address cannot be measured against the policy here, and an unchecked
        address change is a classic way to steal an order, so a person looks at it."""
        decision = engine.Decision(APPROVAL, "new_address_needs_person", "agent")
        pending = self._ask_person(key, "address_change", order, 0, "address_change", [], decision, "change_address")
        approval = self.session.get(Approval, pending["approval_id"])
        approval.payload = {**approval.payload, "new_address": clean}
        return pending

    @staticmethod
    def _already_there(order: Order, target: Address) -> dict[str, Any]:
        """Asking for the address the order is already going to changes nothing and costs
        nothing, so a retry cannot be charged twice."""
        return {
            "ok": True, "status": "done", "order_id": order.id, "label": target.label, "fee_qar": 0.0,
            "replayed": True,
        }

    def _reroute_parcel(self, key: str, order: Order, clean: str) -> dict[str, Any]:
        """ACC-03: free before pickup, and QAR 10 after it. The 2 km limit is for meals
        and groceries, not parcels."""
        if order.status in {"delivered", "cancelled", "failed_customer"}:
            return refused("address_locked_after_pickup")
        target = self._match_saved_address(clean)
        if target is None:
            return self._ask_about_new_address(key, order, clean)
        if order.address_id == target.id:
            return self._already_there(order, target)
        moved = order.status in {"picked_up", "on_the_way"}
        fee = self.rules.dh("parcels.reroute_fee_qar") if moved else 0
        extra = dict(order.extra or {})
        extra["address_changes"] = int(extra.get("address_changes", 0)) + 1
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
        self._note_report(order, ["cancel"])
        if order.status not in self.rules.get("general.terminal_statuses"):
            extra = dict(order.extra or {})
            extra.setdefault("status_at_first_request", order.status)
            order.extra = extra
        terms = engine.cancellation_terms(self.rules, order_facts(order), self._reported_at(order, ["cancel"]))
        if terms.get("escalate"):
            return conflict(terms["code"])
        if not terms["allowed"]:
            return refused(terms["code"])
        if terms["charge_dh"] > 0 and not self._charge_confirmed(order, terms, confirm_charge):
            return {
                "ok": True, "status": "needs_confirmation", "order_id": order.id,
                "charge_qar": to_qar(terms["charge_dh"]), "refund_qar": to_qar(terms["refund_dh"]),
            }
        auto = terms["code"] == "jalboot_auto_cancel"
        credit_back = 0
        if terms["refund_dh"] > 0:
            try:
                credit_back = settle_refund(
                    self.session, self.rules, order, terms["refund_dh"], reason="customer_cancelled", key=key,
                    approved_by="policy", now=self.now,
                ).credit_dh
            except WalletFull:
                return conflict("wallet_at_limit")
        order.status = "cancelled"
        order.extra = {
            **(order.extra or {}), "cancelled_by": "jalboot" if auto else "customer",
            "cancelled_at": self.now.isoformat(),
        }
        if order.payment_method == "cash" and terms["charge_dh"] > 0:
            # CAN-05: nothing was collected, so a charge becomes a balance on the account.
            owner = order.customer
            owner.extra = {
                **(owner.extra or {}),
                "outstanding_balance_dh": int((owner.extra or {}).get("outstanding_balance_dh", 0)) + terms["charge_dh"],
            }
        bonus = 0
        if auto:
            # LAT-03: at 120 minutes Jalboot cancels and adds the cancellation credit.
            bonus = self.rules.dh("cancellations.merchant_cancel_credit_qar")
            settle_credit(
                self.session, order, bonus, reason="cancellation_credit",
                key=action_key("cancel-credit", order.id), approved_by="policy", now=self.now,
            )
        return self._remember(key, "cancel_order", {
            "ok": True, "status": "done", "order_id": order.id, "charge_qar": to_qar(terms["charge_dh"]),
            "refund_qar": to_qar(terms["refund_dh"]), "rule": terms["code"], "credit_qar": to_qar(bonus),
            "to_credit_qar": to_qar(credit_back),
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
