import re
from pathlib import Path

import pytest

from jalboot.kb.store import KnowledgeBase, load_passages
from jalboot.policy.rules import Rules

ROOT = Path(__file__).resolve().parents[1]
PASSAGES = load_passages()
KB = KnowledgeBase(PASSAGES)
RULES = Rules.load()


def test_every_section_exists_in_both_languages():
    english = {p.id for p in PASSAGES if p.language == "en"}
    arabic = {p.id for p in PASSAGES if p.language == "ar"}
    assert english == arabic
    assert len(english) >= 80


def test_no_passage_is_empty():
    assert all(len(p.text) > 40 for p in PASSAGES)


def test_arabic_passages_are_arabic():
    for passage in PASSAGES:
        if passage.language == "ar":
            letters = re.findall(r"[؀-ۿ]", passage.text)
            assert len(letters) > 30, passage.id


def test_customer_search_never_returns_an_internal_section():
    internal = {p.id for p in PASSAGES if p.visibility == "internal"}
    assert internal
    for question in ("what is your refund approval limit", "who approves refunds", "repeat claims trust review"):
        assert not {row["id"] for row in KB.search(question, "en", k=10)} & internal


def test_english_search_finds_the_late_section():
    assert "LAT-01" in [row["id"] for row in KB.search("how much late credit do I get", "en")]


def test_arabic_search_finds_the_cancel_section():
    assert KB.search("كم رسوم إلغاء طلب الطعام", "ar")[0]["id"].startswith("CAN-")


def test_results_carry_what_a_citation_needs():
    row = KB.search("promo code", "en", k=1)[0]
    assert {"id", "title", "text", "doc_title", "updated", "confidence"} <= set(row)


def figures(text):
    return {float(n.replace(",", "")) for n in re.findall(r"\d[\d,]*(?:\.\d+)?", text)}


@pytest.mark.parametrize("section,path", [
    ("REF-05", "refunds.approval_limits_qar.automated"),
    ("REF-05", "refunds.approval_limits_qar.agent"),
    ("REF-05", "refunds.approval_limits_qar.supervisor"),
    ("REF-05", "refunds.new_account.automated_limit_qar"),
    ("REF-06", "refunds.photo.required_above_qar"),
    ("REF-07", "goodwill.automated_max_qar"),
    ("REF-07", "goodwill.max_per_customer_30d_qar"),
    ("REF-07", "compensation_credit_cap_per_order_qar"),
    ("LAT-03", "late_delivery.free_cancel_after_minutes_late"),
    ("LAT-03", "late_delivery.auto_cancel_after_minutes_late"),
    ("LAT-04", "not_received.gps_radius_m"),
    ("CAN-03", "cancellations.grace_minutes"),
    ("ACC-03", "account.address_change.max_distance_km"),
    ("ACC-01", "account.otp.max_failures"),
])
def test_written_policy_and_rules_file_agree(section, path):
    for language in ("en", "ar"):
        passage = next(p for p in PASSAGES if p.id == section and p.language == language)
        assert float(RULES.get(path)) in figures(passage.text.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")))
