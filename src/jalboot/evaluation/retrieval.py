"""Measures search on its own. No model is called, so these numbers are always real.

Each answerable knowledge question lists the sections that answer it. Recall at k is
the share of questions where the top k results hold a right section. A question that
accepts alternatives counts as found if any one of them is in the top k.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Sequence

from jalboot.evaluation.scoring import wilson_interval
from jalboot.retrieval.base import Hit

Search = Callable[[str, str, int], Sequence[Hit]]


@dataclass(frozen=True)
class Question:
    id: str
    text: str
    language: str
    groups: tuple[tuple[str, ...], ...]
    kind: str


def questions_from(cases: Sequence[dict[str, Any]]) -> list[Question]:
    out = []
    for case in cases:
        if case.get("set") != "knowledge" or case.get("answerable") is False:
            continue
        groups = [(section,) for section in case.get("gold_sections") or []]
        groups.extend(tuple(group) for group in case.get("gold_any_of") or [])
        out.append(Question(case["id"], case["question"], case["lang"], tuple(groups), case.get("type", "")))
    return out


def found_all(ranked: Sequence[str], groups: Sequence[Sequence[str]]) -> bool:
    return all(set(group) & set(ranked) for group in groups)


def reciprocal_rank(ranked: Sequence[str], groups: Sequence[Sequence[str]]) -> float:
    wanted = {section for group in groups for section in group}
    for position, doc in enumerate(ranked, start=1):
        if doc in wanted:
            return 1.0 / position
    return 0.0


def recall_table(questions: Sequence[Question], search: Search) -> dict[str, Any]:
    deep = {q.id: [hit.doc_id for hit in search(q.text, q.language, 10)] for q in questions}

    def recall(pool: Sequence[Question], k: int) -> dict[str, Any]:
        hits = sum(found_all(deep[q.id][:k], q.groups) for q in pool)
        return {
            "value": round(hits / len(pool), 4) if pool else None,
            "hits": hits,
            "n": len(pool),
            "ci95": list(wilson_interval(hits, len(pool))),
        }

    english = [q for q in questions if q.language == "en"]
    arabic = [q for q in questions if q.language == "ar"]
    return {
        "recall_at_3": recall(questions, 3),
        "recall_at_5": recall(questions, 5),
        "recall_at_3_en": recall(english, 3),
        "recall_at_3_ar": recall(arabic, 3),
        "recall_at_5_en": recall(english, 5),
        "recall_at_5_ar": recall(arabic, 5),
        "mrr": round(sum(reciprocal_rank(deep[q.id], q.groups) for q in questions) / len(questions), 4)
        if questions else None,
    }


def paired_change(
    questions: Sequence[Question], base: Search, other: Search, k: int = 3,
) -> dict[str, int]:
    """On the same questions: how many went from a miss to a hit, and the other way.
    Two overlapping intervals cannot tell two systems apart, but this can."""
    gained = lost = 0
    for question in questions:
        before = found_all([h.doc_id for h in base(question.text, question.language, k)], question.groups)
        after = found_all([h.doc_id for h in other(question.text, question.language, k)], question.groups)
        gained += after and not before
        lost += before and not after
    return {"gained": gained, "lost": lost}
