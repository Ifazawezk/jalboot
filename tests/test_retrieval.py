from jalboot.retrieval.base import Hit
from jalboot.retrieval.bm25 import BM25Index
from jalboot.retrieval.hybrid import HybridRetriever, reciprocal_rank_fusion
from jalboot.retrieval.ngrams import CharNgramIndex, char_ngrams

DOCS = {
    "refunds#late": "Late orders get a delivery fee refund when the delay passes the promise.",
    "refunds#missing": "If an item is missing from your order we refund the item price.",
    "promo#stack": "Promo codes cannot be combined with other offers on the same order.",
    "ar#late": "إذا تأخر الطلب نعيد رسوم التوصيل إلى المحفظة.",
    "ar#missing": "إذا نقص صنف من طلبك نعيد قيمة الصنف الناقص.",
}


def fit(cls):
    return cls().fit(list(DOCS), list(DOCS.values()))


def test_bm25_finds_the_right_english_section():
    assert fit(BM25Index).search("missing item refund")[0].doc_id == "refunds#missing"


def test_bm25_folds_arabic_spelling():
    # Written without hamza and with ه in place of ة.
    assert fit(BM25Index).search("تاخر الطلب رسوم التوصيل")[0].doc_id == "ar#late"


def test_bm25_returns_nothing_for_unknown_terms():
    assert fit(BM25Index).search("zzzz qqqq") == []


def test_coverage_is_low_when_the_question_is_about_something_else():
    index = fit(BM25Index)
    assert index.coverage("promo codes combined offers", "promo#stack") > 0.9
    assert index.coverage("promo codes for helicopter rental", "promo#stack") < 0.5


def test_ngrams_survive_a_typo_that_breaks_word_matching():
    text = "promoo kodes kombined"
    assert fit(BM25Index).search(text) == []
    assert fit(CharNgramIndex).search(text)[0].doc_id == "promo#stack"


def test_char_ngrams_fold_before_counting():
    assert char_ngrams("الطَّلَبات") == char_ngrams("الطلبات")
    assert char_ngrams("أهلا") == char_ngrams("اهلا")


def test_rrf_rewards_agreement_between_rankings():
    first = [Hit("a", 9, 1), Hit("b", 8, 2)]
    second = [Hit("b", 0.9, 1), Hit("c", 0.8, 2)]
    assert [h.doc_id for h in reciprocal_rank_fusion([first, second])][0] == "b"


def test_hybrid_merges_two_indexes():
    retriever = HybridRetriever([fit(BM25Index), fit(CharNgramIndex)])
    hits = retriever.search("refund for a late or missing order", k=2)
    assert {hit.doc_id for hit in hits} == {"refunds#late", "refunds#missing"}
