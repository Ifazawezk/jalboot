"""Reciprocal rank fusion.

RRF only looks at ranks, so the retrievers do not need comparable scores:

    score(d) = sum over retrievers of  1 / (k + rank(d))

k = 60 is the value from the original paper (Cormack et al., 2009). It is not
tuned on any evaluation set.
"""

from __future__ import annotations

from typing import Sequence

from jalboot.retrieval.base import Hit, Retriever


def reciprocal_rank_fusion(rankings: Sequence[Sequence[Hit]], k: int = 60) -> list[Hit]:
    fused: dict[str, float] = {}
    for ranking in rankings:
        for hit in ranking:
            fused[hit.doc_id] = fused.get(hit.doc_id, 0.0) + 1.0 / (k + hit.rank)
    order = sorted(fused.items(), key=lambda item: -item[1])
    return [Hit(doc, score, rank) for rank, (doc, score) in enumerate(order, start=1)]


class HybridRetriever:
    name = "hybrid"

    def __init__(self, retrievers: Sequence[Retriever], k: int = 60, depth: int = 30):
        self.retrievers = list(retrievers)
        self.k = k
        self.depth = depth

    def search(self, query: str, k: int = 10) -> list[Hit]:
        rankings = [r.search(query, k=self.depth) for r in self.retrievers]
        return reciprocal_rank_fusion(rankings, self.k)[:k]
