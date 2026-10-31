"""Turns database rows into the JSON objects in API.md.

Each function takes the language of the person reading. Nothing here adds a phone
number, a code or a customer's contact details to a staff or customer view.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from jalboot.db.models import (
    Approval, AuditEvent, Conversation, Customer, Message, Order, Refund, StaffUser,
)
from jalboot.policy.rules import Rules, to_qar
from jalboot.tools.approvals import can_decide
from jalboot.tools.facts import claim_facts, order_facts

TOOL_LABELS = {
    "get_customer_profile": (("Opening your account", "جارٍ فتح حسابك"), ("Opened your account", "تم فتح حسابك")),
    "track_order": (("Checking your order", "جارٍ التحقق من طلبك"), ("Checked your order", "تم التحقق من طلبك")),
    "get_order_details": (("Reading your order details", "جارٍ قراءة تفاصيل طلبك"), ("Read your order details", "تمت قراءة تفاصيل طلبك")),
    "quote_refund": (("Working out your refund", "جارٍ حساب الاسترداد"), ("Worked out your refund", "تم حساب الاسترداد")),
    "issue_refund": (("Working on your refund", "جارٍ تجهيز الاسترداد"), ("Worked on your refund", "تم تجهيز الاسترداد")),
    "issue_credit": (("Adding credit to your account", "جارٍ إضافة رصيد إلى حسابك"), ("Added credit to your account", "تمت إضافة الرصيد إلى حسابك")),
    "apply_promo": (("Checking your promo code", "جارٍ التحقق من الرمز الترويجي"), ("Checked your promo code", "تم التحقق من الرمز الترويجي")),
    "change_address": (("Updating your address", "جارٍ تحديث عنوانك"), ("Updated your address", "تم تحديث عنوانك")),
    "cancel_order": (("Cancelling your order", "جارٍ إلغاء طلبك"), ("Cancelled your order", "تم إلغاء طلبك")),
    "create_ticket": (("Opening a ticket with the team", "جارٍ فتح تذكرة مع الفريق"), ("Opened a ticket with the team", "تم فتح تذكرة مع الفريق")),
    "handoff_to_human": (("Finding a person to help", "جارٍ البحث عن موظف لمساعدتك"), ("Asked a person to help", "تم طلب موظف لمساعدتك")),
    "search_knowledge": (("Reading the help pages", "جارٍ قراءة صفحات المساعدة"), ("Read the help pages", "تمت قراءة صفحات المساعدة")),
    "explain_delay": (("Finding out what caused the delay", "جارٍ معرفة سبب التأخير"), ("Found out what caused the delay", "تمت معرفة سبب التأخير")),
}
TOOL_FAILED = ("That step did not work", "لم تنجح هذه الخطوة")
# Stated in the API as a single reason the desk has a label for.
REASON_GROUPS = {
    "missing_item": "missing_item", "wrong_item": "wrong_item", "whole_wrong_order": "wrong_item",
    "damaged_item": "wrong_item", "spoiled_item": "quality", "quality": "quality", "cold_food": "quality",
    "chilled_item": "quality", "expired_product": "quality", "cold_chain": "quality",
    "modifier_missed": "wrong_item", "substitute_rejected": "wrong_item", "late_delivery": "late",
    "late_delivery_fee": "late", "goodwill": "late", "not_received": "missing_item",
    "duplicate_charge": "wrong_item", "failed_contact_refund": "missing_item", "allergen": "quality",
    "foreign_object": "quality", "broken_seal": "quality", "illness": "quality",
}
POLICY_SECTIONS = {
    "missing_item": "WRG-01", "wrong_item": "WRG-01", "whole_wrong_order": "WRG-01", "quality": "WRG-05",
    "cold_food": "WRG-05", "late_delivery": "LAT-01", "late_delivery_fee": "LAT-01", "not_received": "LAT-04",
    "duplicate_charge": "PAY-03", "modifier_missed": "WRG-02", "substitute_rejected": "GRC-04",
}
STAGE_STATE = {"bot": "bot", "waiting": "waiting", "agent": "agent", "closed": "closed"}


def iso(moment: datetime | None) -> str | None:
    if moment is None:
        return None
    return moment.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def pick(pair: tuple[str, str], language: str) -> str:
    return pair[1] if language == "ar" else pair[0]


def tool_label(tool: str, stage: int, language: str) -> str:
    labels = TOOL_LABELS.get(tool)
    return pick(labels[stage], language) if labels else tool


def order_card(order: Order, language: str) -> dict[str, Any]:
    arabic = language == "ar"
    merchant = order.merchant
    store = ""
    if merchant:
        store = merchant.name_ar if arabic and merchant.name_ar else merchant.name
    finished = order.status in {"delivered", "cancelled", "failed_customer"}
    return {
        "id": order.id,
        "vertical": order.category,
        "status": order.status,
        "store": store,
        "area": order.address_text.rsplit(",", 1)[-1].strip() if order.address_text else "",
        "placedAt": iso(order.placed_at),
        "etaAt": None if finished else iso(order.promised_at),
        "deliveredAt": iso(order.delivered_at),
        "rider": order.driver.name.split()[0] if order.driver else None,
        "items": [
            {
                "name": item.name_ar if arabic and item.name_ar else item.name,
                "qty": item.quantity,
                "priceQar": to_qar(item.unit_price_dh),
            }
            for item in order.items
        ],
        "feesQar": to_qar(order.delivery_fee_dh + order.other_fees_dh),
        "totalQar": to_qar(order.total_dh),
    }


def citation_view(citation: dict[str, Any]) -> dict[str, Any]:
    updated = str(citation.get("updated") or "2026-11-01")
    return {
        "n": citation["n"],
        "sourceId": citation.get("doc", citation["id"]),
        "title": citation.get("doc_title", ""),
        "section": f"{citation['id']}: {citation.get('title', '')}",
        "excerpt": str(citation.get("text", ""))[:280],
        "updatedAt": f"{updated}T00:00:00Z",
    }


def handoff_view(session: Session, conversation: Conversation) -> dict[str, Any]:
    status_map = {"waiting": "queued", "agent": "joined", "closed": "closed"}
    agent = session.get(StaffUser, conversation.assigned_staff_id) if conversation.assigned_staff_id else None
    position = None
    if conversation.status == "waiting":
        ahead = session.scalars(
            select(Conversation.id).where(
                Conversation.status == "waiting", Conversation.handoff_at < conversation.handoff_at
            )
        ).all()
        position = len(ahead) + 1
    return {
        "status": status_map.get(conversation.status, "requested"),
        "agentName": agent.name.split()[0] if agent else None,
        "etaMinutes": None,
        "position": position,
    }


def customer_name(session: Session, conversation: Conversation) -> str:
    if conversation.customer_id and conversation.verified_at:
        customer = session.get(Customer, conversation.customer_id)
        if customer is not None:
            return customer.name_ar if conversation.language == "ar" and customer.name_ar else customer.name
    return "زائر" if conversation.language == "ar" else "Guest"


def live_conversation(session: Session, conversation: Conversation) -> dict[str, Any]:
    agent = session.get(StaffUser, conversation.assigned_staff_id) if conversation.assigned_staff_id else None
    first = session.scalar(
        select(Message.text).where(Message.conversation_id == conversation.id, Message.role == "customer")
        .order_by(Message.id).limit(1)
    )
    return {
        "id": conversation.id,
        "customer": customer_name(session, conversation),
        "locale": conversation.language,
        "state": STAGE_STATE.get(conversation.status, "bot"),
        "priority": "high" if conversation.priority in {"P1", "P2"} else "normal",
        "verified": bool(conversation.verified_at),
        "summary": (conversation.handoff_summary or first or "")[:300],
        "orderId": conversation.order_id or None,
        "agentName": agent.name if agent else None,
        "startedAt": iso(conversation.created_at),
        "updatedAt": iso(conversation.updated_at),
        "waitingSince": iso(conversation.handoff_at) if conversation.status == "waiting" else None,
    }


def transcript_entry(message: Message, staff_name: str | None = None) -> dict[str, Any]:
    author = {"customer": "customer", "bot": "bot", "agent": "agent"}.get(message.role, "system")
    meta = message.meta or {}
    return {
        "id": str(message.id),
        "at": iso(message.created_at),
        "author": author,
        "name": staff_name or meta.get("agent_name"),
        "text": message.text,
        "tools": list(meta.get("tools", [])),
        "sources": list(meta.get("sources", [])),
    }


def conversation_detail(session: Session, conversation: Conversation) -> dict[str, Any]:
    rows = session.scalars(
        select(Message).where(Message.conversation_id == conversation.id).order_by(Message.id)
    ).all()
    return {**live_conversation(session, conversation), "transcript": [transcript_entry(row) for row in rows]}


def refund_status(approval: Approval) -> str:
    return {"pending": "pending", "approved": "approved", "rejected": "rejected"}[approval.status]


def refund_summary(approval: Approval, staff_name: str | None) -> dict[str, Any]:
    # An approval note is for the audit log. A rejection note is the reason the customer sees.
    return {
        "id": approval.id,
        "orderId": approval.order_id,
        "amountQar": to_qar(approval.amount_dh),
        "status": refund_status(approval),
        "decidedBy": staff_name,
        "note": approval.decision_note or None if approval.status == "rejected" else None,
    }


def _risks(session: Session, rules: Rules, approval: Approval, order: Order, now: datetime, language: str) -> list[str]:
    customer = session.get(Customer, approval.customer_id)
    facts = claim_facts(session, customer, order, now)
    risks: list[str] = []
    rule = str((approval.payload or {}).get("rule", ""))
    if rule == "photo_needed":
        risks.append(pick(("Photo not received yet", "لم تصل الصورة بعد"), language))
    if rule == "repeat_claims" or facts.claims_30d >= 2:
        risks.append(pick((f"{facts.claims_30d} claims in 30 days", f"{facts.claims_30d} مطالبات خلال 30 يوما"), language))
    if facts.account_age_days < int(rules.get("refunds.new_account.age_days")):
        risks.append(pick(("New account", "حساب جديد"), language))
    if rule == "proof_of_delivery_exists":
        risks.append(pick(("Proof of delivery on file", "يوجد إثبات تسليم"), language))
    return risks


def refund_view(
    session: Session, rules: Rules, approval: Approval, viewer: StaffUser, now: datetime, language: str,
) -> dict[str, Any]:
    order = session.get(Order, approval.order_id)
    decider = session.get(StaffUser, approval.decided_by) if approval.decided_by else None
    conversation = session.get(Conversation, approval.conversation_id) if approval.conversation_id else None
    customer = session.get(Customer, approval.customer_id)
    arabic = language == "ar"
    name = (customer.name_ar if arabic and customer.name_ar else customer.name) if customer else ""
    store = ""
    if order.merchant:
        store = order.merchant.name_ar if arabic and order.merchant.name_ar else order.merchant.name
    reason = str((approval.payload or {}).get("reason") or approval.reason)
    risks = _risks(session, rules, approval, order, now, language)
    section = POLICY_SECTIONS.get(reason, "REF-03")
    items = ", ".join((approval.payload or {}).get("items") or [])
    evidence = [
        {"label": pick(("Order total", "إجمالي الطلب"), language), "value": f"QAR {to_qar(order.total_dh):g}"},
        {"label": pick(("Order status", "حالة الطلب"), language), "value": order.status},
    ]
    if items:
        evidence.append({"label": pick(("Items", "الأصناف"), language), "value": items})
    if (order.extra or {}).get("photo_evidence"):
        evidence.append({"label": pick(("Photo", "صورة"), language), "value": pick(("On file", "محفوظة"), language)})
    return {
        **refund_summary(approval, decider.name if decider else None),
        "conversationId": approval.conversation_id or "",
        "customer": name,
        "store": store,
        "reason": REASON_GROUPS.get(reason, "wrong_item"),
        "summary": pick((f"{reason} on {order.id}", f"{reason} في الطلب {order.id}"), language),
        "requestedAt": iso(approval.created_at),
        "decidedAt": iso(approval.decided_at),
        "recommendation": "review" if risks else "approve",
        "evidence": evidence,
        "policy": {"title": section, "section": section},
        "risks": risks,
        "version": approval.version,
        "canDecide": can_decide(viewer.role, approval) and approval.status == "pending",
        "requiredRole": approval.required_role,
        "conversationVerified": bool(conversation and conversation.verified_at),
    }


def audit_entry(session: Session, row: AuditEvent) -> dict[str, Any]:
    kind = {"bot": "bot", "staff": "agent"}.get(row.actor_type, "system")
    name = "Support bot" if kind == "bot" else row.actor_id
    if kind == "agent":
        staff = session.get(StaffUser, row.actor_id)
        name = staff.name if staff else row.actor_id
    detail = row.detail or {}
    summary = " ".join(str(v) for v in (detail.get("tool"), detail.get("status"), detail.get("error"), detail.get("reason")) if v)
    return {
        "id": str(row.seq),
        "at": iso(row.at),
        "actorKind": kind,
        "actorName": name,
        "action": row.action,
        "target": row.order_id or row.conversation_id or "",
        "detail": summary,
    }


def desk_summary(session: Session, now: datetime) -> dict[str, int]:
    conversations = session.scalars(select(Conversation.status)).all()
    pending = session.scalars(select(Approval.id).where(Approval.status == "pending")).all()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    resolved = session.scalars(
        select(Conversation.id).where(Conversation.resolved_by != "", Conversation.updated_at >= today)
    ).all()
    return {
        "live": sum(1 for status in conversations if status in {"bot", "waiting", "agent"}),
        "waiting": sum(1 for status in conversations if status == "waiting"),
        "refundsPending": len(pending),
        "resolvedToday": len(resolved),
    }


def order_facts_paid(order: Order) -> float:
    return to_qar(order_facts(order).paid_dh)


__all__ = [
    "Refund", "audit_entry", "citation_view", "conversation_detail", "desk_summary", "handoff_view", "iso",
    "live_conversation", "order_card", "pick", "refund_summary", "refund_view", "tool_label", "transcript_entry",
]
