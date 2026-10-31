"""Okapi BM25 over folded, lightly stemmed Arabic and English terms."""

from __future__ import annotations

import math
from collections import Counter
from typing import Sequence

import numpy as np

from jalboot.retrieval.base import Hit, top_hits
from jalboot.text.tokenize import analyze


class BM25Index:
    name = "bm25"

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.doc_ids: list[str] = []
        self.positions: dict[str, int] = {}
        self.doc_len = np.zeros(0)
        self.avgdl = 0.0
        self.postings: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        self.idf: dict[str, float] = {}

    def fit(self, doc_ids: Sequence[str], texts: Sequence[str]) -> "BM25Index":
        self.doc_ids = list(doc_ids)
        self.positions = {doc: index for index, doc in enumerate(self.doc_ids)}
        lists: dict[str, list[tuple[int, int]]] = {}
        lengths = []
        for index, text in enumerate(texts):
            terms = analyze(text)
            lengths.append(len(terms))
            for term, tf in Counter(terms).items():
                lists.setdefault(term, []).append((index, tf))
        self.doc_len = np.array(lengths, dtype=np.float64)
        self.avgdl = float(self.doc_len.mean()) if lengths else 0.0
        total = len(self.doc_ids)
        for term, entries in lists.items():
            docs = np.array([d for d, _ in entries], dtype=np.int64)
            tfs = np.array([t for _, t in entries], dtype=np.float64)
            self.postings[term] = (docs, tfs)
            df = len(entries)
            self.idf[term] = math.log(1 + (total - df + 0.5) / (df + 0.5))
        return self

    def scores(self, query: str) -> np.ndarray:
        scores = np.zeros(len(self.doc_ids))
        if not self.doc_ids:
            return scores
        norm = self.k1 * (1 - self.b + self.b * self.doc_len / max(self.avgdl, 1e-9))
        for term in dict.fromkeys(analyze(query)):
            posting = self.postings.get(term)
            if posting is None:
                continue
            docs, tfs = posting
            scores[docs] += self.idf[term] * tfs * (self.k1 + 1) / (tfs + norm[docs])
        return scores

    def search(self, query: str, k: int = 10) -> list[Hit]:
        return top_hits(self.doc_ids, self.scores(query), k)

    def coverage(self, query: str, doc_id: str) -> float:
        """The share of the query's information, weighted by IDF, that a document holds.

        A question about something the documents never mention scores low here even
        when BM25 finds a weak match, so this feeds the confidence check.
        """
        terms = list(dict.fromkeys(analyze(query)))
        index = self.positions.get(doc_id)
        if not terms or index is None:
            return 0.0
        # A term the index has never seen is the most surprising kind, so it counts in full.
        unseen = math.log(1 + (len(self.doc_ids) + 0.5) / 0.5)
        total = found = 0.0
        for term in terms:
            weight = self.idf.get(term, unseen)
            total += weight
            posting = self.postings.get(term)
            if posting is not None and index in posting[0]:
                found += weight
        return found / total if total else 0.0
