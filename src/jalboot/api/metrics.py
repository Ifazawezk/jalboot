"""Numbers for the desk. They come from simulated tickets plus any live conversations,
and the page says so. They are not the evaluation results."""

from __future__ import annotations

from datetime import datetime, timedelta
from statistics import mean, median
from typing import Any, Callable, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from jalboot.api.views import pick
from jalboot.db.models import Message, Ticket

ISSUE_LABELS = {
    "late_delivery": ("Late delivery", "تأخر التوصيل"),
    "missing_item": ("Missing item", "صنف ناقص"),
    "wrong_item": ("Wrong item", "صنف خاطئ"),
    "refund_status": ("Refund status", "حالة الاسترداد"),
    "promo_issue": ("Promo code", "الرمز الترويجي"),
    "address_change": ("Address change", "تغيير العنوان"),
    "payment_issue": ("Payment", "الدفع"),
    "driver_conduct": ("Driver conduct", "سلوك السائق"),
    "pharmacy_prescription": ("Prescription", "الوصفة الطبية"),
    "parcel_lost": ("Lost parcel", "طرد مفقود"),
    "account": ("Account", "الحساب"),
    "other": ("Other", "أخرى"),
}
BUCKETS = 7


def _between(session: Session, start: datetime, end: datetime) -> Sequence[Ticket]:
    return session.scalars(
        select(Ticket).where(Ticket.created_at >= start, Ticket.created_at < end)
    ).all()


def top_issues(session: Session, now: datetime, window: int, language: str) -> list[dict[str, Any]]:
    span = timedelta(days=window)
    current, previous = _between(session, now - span, now), _between(session, now - 2 * span, now - span)
    counts: dict[str, int] = {}
    earlier: dict[str, int] = {}
    for ticket in current:
        counts[ticket.category] = counts.get(ticket.category, 0) + 1
    for ticket in previous:
        earlier[ticket.category] = earlier.get(ticket.category, 0) + 1
    issues = []
    for category, count in counts.items():
        before = earlier.get(category, 0)
        change = round((count - before) * 100 / before) if before else 0
        issues.append({
            "id": category,
            "label": pick(ISSUE_LABELS.get(category, (category, category)), language),
            "count": count,
            "changePct": change,
        })
    return sorted(issues, key=lambda issue: (-issue["count"], issue["id"]))


def _bot_share(tickets: Sequence[Ticket]) -> float:
    done = [t for t in tickets if t.resolved_by]
    return round(100 * sum(t.resolved_by == "bot" for t in done) / len(done), 1) if done else 0.0


def _agent_share(tickets: Sequence[Ticket]) -> float:
    return round(100 - _bot_share(tickets), 1) if any(t.resolved_by for t in tickets) else 0.0


def _csat(tickets: Sequence[Ticket]) -> float:
    scores = [t.csat for t in tickets if t.csat]
    return round(mean(scores), 2) if scores else 0.0


def _first_reply(tickets: Sequence[Ticket]) -> float:
    times = [t.first_reply_seconds for t in tickets if t.first_reply_seconds is not None]
    return float(median(times)) if times else 0.0


def _tile(
    session: Session, now: datetime, window: int, tile_id: str, label: str, unit: str,
    higher_better: bool, measure: Callable[[Sequence[Ticket]], float],
) -> dict[str, Any]:
    span = timedelta(days=window)
    value = measure(_between(session, now - span, now))
    before = measure(_between(session, now - 2 * span, now - span))
    step = span / BUCKETS
    trend = [
        measure(_between(session, now - span + step * index, now - span + step * (index + 1)))
        for index in range(BUCKETS)
    ]
    return {
        "id": tile_id, "label": label, "value": value, "unit": unit,
        "delta": round(value - before, 2), "higherIsBetter": higher_better, "trend": trend,
    }


def reply_check_tile(session: Session, language: str) -> dict[str, Any] | None:
    """Live data only, from replies this server really sent."""
    rows = session.scalars(select(Message.meta).where(Message.role == "bot")).all()
    checked = [meta for meta in rows if meta and "flags" in meta]
    if not checked:
        return None
    clean = sum(not any(str(flag).startswith("check_failed") for flag in meta["flags"]) for meta in checked)
    return {
        "id": "checks", "label": pick(("Replies passing checks first time", "ردود اجتازت الفحص من أول مرة"), language),
        "value": round(100 * clean / len(checked), 1), "unit": "percent", "delta": 0.0,
        "higherIsBetter": True, "trend": [],
    }


def quality_report(session: Session, now: datetime, window: int, language: str) -> dict[str, Any]:
    hero = _tile(
        session, now, window, "bot_resolution",
        pick(("Resolved without a person", "حُلّت دون تدخل موظف"), language), "percent", True, _bot_share,
    )
    tiles = [
        _tile(session, now, window, "csat", pick(("Customer rating", "تقييم العملاء"), language), "score", True, _csat),
        _tile(session, now, window, "first_reply", pick(("First reply", "أول رد"), language), "seconds", False, _first_reply),
        _tile(session, now, window, "agent_share", pick(("Needed a person", "احتاجت إلى موظف"), language), "percent", False, _agent_share),
    ]
    live = reply_check_tile(session, language)
    if live:
        tiles.append(live)
    series = []
    for days_back in range(window - 1, -1, -1):
        day_end = now - timedelta(days=days_back)
        day_start = day_end - timedelta(days=1)
        series.append({
            "date": day_start.date().isoformat(),
            "value": _bot_share(_between(session, day_start, day_end)),
        })
    return {"windowDays": window, "hero": hero, "tiles": tiles, "series": series}
