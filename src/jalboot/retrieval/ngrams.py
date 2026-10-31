"""TF-IDF over character n-grams.

This needs no model and survives what breaks word matching: Gulf spellings,
typos, attached particles and word forms the light stemmer misses. It is the
second retriever when no embedding model is installed.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Sequence

import numpy as np

from jalboot.retrieval.base import Hit, top_hits
from jalboot.text.normalize import normalize

SPACES = re.compile(r"[^\w]+")


def char_ngrams(text: str, sizes: tuple[int, ...] = (3, 4, 5)) -> Counter[str]:
    folded = f" {SPACES.sub(' ', normalize(text)).strip()} "
    grams: Counter[str] = Counter()
    for size in sizes:
        for start in range(len(folded) - size + 1):
            gram = folded[start:start + size]
            if gram.strip():
                grams[gram] += 1
    return grams


class CharNgramIndex:
    name = "ngrams"

    def __init__(self, sizes: tuple[int, ...] = (3, 4, 5)):
        self.sizes = sizes
        self.doc_ids: list[str] = []
        self.postings: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        self.idf: dict[str, float] = {}

    @staticmethod
    def _weight(tf: int) -> float:
        return 1.0 + math.log(tf)

    def fit(self, doc_ids: Sequence[str], texts: Sequence[str]) -> "CharNgramIndex":
        self.doc_ids = list(doc_ids)
        counts = [char_ngrams(text, self.sizes) for text in texts]
        df: Counter[str] = Counter()
        for grams in counts:
            df.update(grams.keys())
        total = len(self.doc_ids)
        self.idf = {g: math.log((1 + total) / (1 + n)) + 1.0 for g, n in df.items()}
        norms = [
            math.sqrt(sum((self._weight(tf) * self.idf[g]) ** 2 for g, tf in grams.items())) or 1.0
            for grams in counts
        ]
        lists: dict[str, list[tuple[int, float]]] = {}
        for index, grams in enumerate(counts):
            for gram, tf in grams.items():
                lists.setdefault(gram, []).append(
                    (index, self._weight(tf) * self.idf[gram] / norms[index])
                )
        for gram, entries in lists.items():
            self.postings[gram] = (
                np.array([d for d, _ in entries], dtype=np.int64),
                np.array([w for _, w in entries], dtype=np.float64),
            )
        return self

    def scores(self, query: str) -> np.ndarray:
        scores = np.zeros(len(self.doc_ids))
        grams = char_ngrams(query, self.sizes)
        weighted = {g: self._weight(tf) * self.idf[g] for g, tf in grams.items() if g in self.idf}
        norm = math.sqrt(sum(w * w for w in weighted.values())) or 1.0
        for gram, weight in weighted.items():
            docs, values = self.postings[gram]
            scores[docs] += values * (weight / norm)
        return scores

    def search(self, query: str, k: int = 10) -> list[Hit]:
        return top_hits(self.doc_ids, self.scores(query), k)
