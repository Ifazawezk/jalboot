"""Types shared by the retrievers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

import numpy as np


@dataclass(frozen=True)
class Hit:
    doc_id: str
    score: float
    rank: int


class Retriever(Protocol):
    name: str

    def search(self, query: str, k: int = 10) -> list[Hit]: ...


def top_hits(doc_ids: Sequence[str], scores: np.ndarray, k: int) -> list[Hit]:
    """The k best documents with a score above zero, ties broken by document order."""
    if not len(doc_ids):
        return []
    order = np.lexsort((np.arange(len(scores)), -scores))
    hits: list[Hit] = []
    for index in order[:k]:
        score = float(scores[index])
        if score <= 0.0:
            break
        hits.append(Hit(doc_ids[int(index)], score, len(hits) + 1))
    return hits
