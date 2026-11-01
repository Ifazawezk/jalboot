import re
from pathlib import Path

import pytest

from jalboot.kb.store import KnowledgeBase, load_encoder, load_passages
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
    assert {"id", "title", "text", "doc_title", "updated", "confidence", "ngram_similarity"} <= set(row)


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


class FakeEncoder:
    """Stands in for an embedding model: a letter-count vector, so no model is needed."""

    name = "fake"
    max_chars = 400

    def __init__(self):
        self.calls = 0

    def _vector(self, text):
        import numpy as np

        vector = np.zeros(64, dtype=np.float32)
        for char in text.lower():
            vector[ord(char) % 64] += 1
        return vector / (np.linalg.norm(vector) or 1.0)

    def encode_queries(self, texts):
        import numpy as np

        return np.stack([self._vector(t) for t in texts])

    def encode_passages(self, texts):
        import numpy as np

        self.calls += 1
        return np.stack([self._vector(t) for t in texts])


def test_an_encoder_joins_the_hybrid_search():
    base = KnowledgeBase(PASSAGES)
    dense = KnowledgeBase(PASSAGES, encoder=FakeEncoder())
    assert len(dense.retrievers["en"].retrievers) == len(base.retrievers["en"].retrievers) + 1
    assert dense.search("late credit tiers", "en")


def test_dense_search_never_returns_an_internal_section():
    internal = {p.id for p in PASSAGES if p.visibility == "internal"}
    kb = KnowledgeBase(PASSAGES, encoder=FakeEncoder())
    assert not {row["id"] for row in kb.search("who approves refunds and what are the limits", "en", k=10)} & internal


def test_embeddings_are_cached_so_a_restart_does_not_recompute(tmp_path):
    from jalboot.retrieval.dense import DenseIndex

    encoder = FakeEncoder()
    DenseIndex(encoder, ["a", "b"], ["one", "two"], tmp_path)
    DenseIndex(encoder, ["a", "b"], ["one", "two"], tmp_path)
    assert encoder.calls == 1


def test_changed_text_rebuilds_the_cache(tmp_path):
    from jalboot.retrieval.dense import DenseIndex

    encoder = FakeEncoder()
    DenseIndex(encoder, ["a"], ["one"], tmp_path)
    DenseIndex(encoder, ["a"], ["changed"], tmp_path)
    assert encoder.calls == 2


def test_no_embedding_preset_means_no_model():
    assert load_encoder("") is None
