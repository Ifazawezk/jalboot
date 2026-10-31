"""Optional cross-encoder reranking.

A reranker reads each question and passage together, which is slower than search
and needs a model of several hundred megabytes. It is only switched on when a
measured run on the development questions shows it helps; see eval/retrieval.
"""

from __future__ import annotations

from typing import Mapping, Protocol, Sequence

from jalboot.retrieval.base import Hit, Retriever


class PairScorer(Protocol):
    name: str

    def score(self, pairs: Sequence[tuple[str, str]]) -> list[float]: ...


class CrossEncoderScorer:
    def __init__(self, model_name: str, batch_size: int = 8):
        from sentence_transformers import CrossEncoder

        self.name = model_name
        self.batch_size = batch_size
        self.model = CrossEncoder(model_name, device="cpu")

    def score(self, pairs: Sequence[tuple[str, str]]) -> list[float]:
        scores = self.model.predict(list(pairs), batch_size=self.batch_size, show_progress_bar=False)
        return [float(value) for value in scores]


class RerankingRetriever:
    name = "rerank"

    def __init__(
        self,
        retriever: Retriever,
        scorer: PairScorer,
        texts: Mapping[str, str],
        depth: int = 20,
    ):
        self.retriever = retriever
        self.scorer = scorer
        self.texts = texts
        self.depth = depth

    def search(self, query: str, k: int = 10) -> list[Hit]:
        candidates = self.retriever.search(query, k=self.depth)
        if not candidates:
            return []
        scores = self.scorer.score([(query, self.texts[hit.doc_id]) for hit in candidates])
        ranked = sorted(zip(candidates, scores), key=lambda pair: -pair[1])
        return [Hit(hit.doc_id, score, rank) for rank, (hit, score) in enumerate(ranked[:k], start=1)]
