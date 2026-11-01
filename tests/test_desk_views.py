"""What the desk and the order card show. Staff and customers read these, so they carry
labels in the reader's language and never an internal code."""

import re
from types import SimpleNamespace

import pytest

from jalboot.api import views
from jalboot.db.models import Approval, Driver, Message, Order
from jalboot.tools.specs import CREDIT_REASONS, REFUND_REASONS
from tests.conftest import ANCHOR, RULES

VIEWER = SimpleNamespace(role="supervisor")
ORDER = "JB-700102"
LATIN = re.compile(r"[A-Za-z]")


def approval(db, reason="wrong_item", kind="refund", order_id=ORDER, **payload):
    order = db.get(Order, order_id)
    row = Approval(
        id=f"AP-{reason}", kind=kind, status="pending", customer_id=order.customer_id, order_id=order.id,
        amount_dh=1000, payload={"reason": reason, **payload}, reason=reason, required_role="agent",
        idempotency_key=f"key-{reason}", created_at=ANCHOR,
    )
    db.add(row)
    db.commit()
    return row


def view(db, row, language="en"):
    return views.refund_view(db, RULES, row, VIEWER, ANCHOR, language)


def evidence(result, label):
    return next((item for item in result["evidence"] if item["label"] == label), None)


def test_every_reason_has_a_label_in_both_languages():
    for reason in [*REFUND_REASONS, *CREDIT_REASONS, "address_change"]:
        english, arabic = views.REASON_LABELS[reason]
        assert english and "_" not in english
        assert arabic and not LATIN.search(arabic)


def test_every_order_status_has_a_label_in_both_languages():
    statuses = {status for path in RULES.get("general.order_status_paths").values() for status in path}
    statuses |= set(RULES.get("general.terminal_statuses"))
    for status in statuses:
        english, arabic = views.STATUS_LABELS[status]
        assert english and "_" not in english
        assert arabic and not LATIN.search(arabic)


@pytest.mark.parametrize("language, expected", [
    ("en", f"Wrong item on {ORDER}"),
    ("ar", f"صنف خاطئ في الطلب {ORDER}"),
])
def test_a_refund_summary_shows_a_label_and_not_a_code(db, language, expected):
    assert view(db, approval(db), language)["summary"] == expected


def test_a_reason_nobody_has_labelled_yet_is_still_not_shown_raw(db):
    summary = view(db, approval(db, reason="brand_new_reason"))["summary"]
    assert "brand_new_reason" not in summary


def test_arabic_evidence_shows_no_internal_status_or_latin_money(db):
    result = view(db, approval(db), "ar")
    assert not LATIN.search(evidence(result, "حالة الطلب")["value"])
    assert "ر.ق" in evidence(result, "إجمالي الطلب")["value"]


def test_arabic_evidence_names_items_in_arabic(db):
    row = approval(db, items=[{"name": "Karak tea", "quantity": 1}])
    assert "Karak" not in evidence(view(db, row, "ar"), "الأصناف")["value"]


@pytest.mark.parametrize("typed", ["karak tea", "KARAK TEA", "karak"])
def test_arabic_evidence_finds_the_item_however_it_was_typed(db, typed):
    """A claim keeps the name as the customer or the model wrote it."""
    row = approval(db, items=[{"name": typed, "quantity": 1}])
    assert evidence(view(db, row, "ar"), "الأصناف")["value"] == "شاي كرك"


def test_arabic_evidence_keeps_a_name_it_cannot_match_rather_than_dropping_it(db):
    row = approval(db, items=[{"name": "mystery box", "quantity": 1}])
    assert evidence(view(db, row, "ar"), "الأصناف")["value"] == "mystery box"


def test_the_policy_title_is_readable_and_not_just_the_section_code(db):
    policy = view(db, approval(db), "en")["policy"]
    assert policy["section"] == "WRG-01"
    assert policy["title"] != policy["section"]


@pytest.mark.parametrize("language", ["en", "ar"])
def test_photo_evidence_says_it_is_simulated(db, language):
    """Customers cannot upload a photo, so the flag on a demo order is not a real file."""
    order = db.get(Order, ORDER)
    order.extra = {**(order.extra or {}), "photo_evidence": True}
    db.commit()
    rows = [item for item in view(db, approval(db), language)["evidence"] if item.get("simulated")]
    assert len(rows) == 1
    assert ("simulated" in rows[0]["value"].lower()) if language == "en" else ("محاكاة" in rows[0]["value"])
    assert "On file" not in rows[0]["value"] and "محفوظة" not in rows[0]["value"]


def test_no_photo_row_appears_when_the_order_has_no_photo_flag(db):
    order = db.get(Order, ORDER)
    order.extra = {key: value for key, value in (order.extra or {}).items() if key != "photo_evidence"}
    db.commit()
    assert not any(item.get("simulated") for item in view(db, approval(db))["evidence"])


def test_a_photo_risk_does_not_suggest_one_is_on_its_way(db):
    row = approval(db, rule="photo_needed")
    assert not any("yet" in risk for risk in view(db, row)["risks"])
    assert any("cannot" in risk for risk in view(db, row)["risks"])


def test_the_approver_sees_the_new_address_being_approved(db):
    address = "Zone 60, Street 812, Building 14, West Bay"
    row = approval(db, reason="address_change", kind="address_change", new_address=address)
    result = view(db, row)
    assert evidence(result, "New address")["value"] == address
    assert evidence(view(db, row, "ar"), "العنوان الجديد")["value"] == address
    assert result["reason"] == "address"
    assert "Address change" in result["summary"]


def test_an_order_card_in_arabic_has_no_latin_area_or_rider(db):
    card = views.order_card(db.get(Order, ORDER), "ar")
    assert card["area"] and not LATIN.search(card["area"])
    assert card["rider"] and not LATIN.search(card["rider"])


def test_an_order_card_in_english_keeps_english_names(db):
    order = db.get(Order, ORDER)
    card = views.order_card(order, "en")
    assert card["area"] == order.address_text.rsplit(",", 1)[-1].strip()
    assert card["rider"] == order.driver.name.split()[0]


def test_an_arabic_card_leaves_out_a_name_it_cannot_write_in_arabic(db):
    order = db.get(Order, ORDER)
    order.driver = db.get(Driver, order.driver_id)
    order.driver.name_ar = ""
    order.address_text = "Zone 1, Street 2, Building 3, Nowhere Town"
    card = views.order_card(order, "ar")
    assert card["rider"] is None
    assert card["area"] == ""


def test_two_passages_from_one_page_are_listed_once():
    citations = [{"doc_title": "Refunds"}, {"doc_title": "Refunds"}, {"doc_title": "Cancellations"}]
    assert views.source_titles(citations) == ["Refunds", "Cancellations"]


def test_a_citation_without_a_page_title_uses_its_section_title():
    assert views.source_titles([{"id": "REF-01", "title": "Refund basics"}]) == ["Refund basics"]
    assert views.citation_view({"n": 1, "id": "REF-01", "title": "Refund basics"})["title"] == "Refund basics"


def test_a_saved_transcript_entry_shows_each_source_once_and_no_blanks():
    message = Message(id=1, role="bot", text="Hi", created_at=ANCHOR, meta={"sources": ["Refunds", "", "Refunds"]})
    assert views.transcript_entry(message)["sources"] == ["Refunds"]
