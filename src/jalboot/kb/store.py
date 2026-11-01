"""Loads the policy documents and searches them.

Each document holds numbered sections in English, with the Arabic version in a block
right after each one. A section in one language is one passage, and passages keep the
section id, so an Arabic and an English answer cite the same section.

Sections marked internal hold approval limits and review triggers that support must
not quote (ESC-03). They are left out of customer search entirely, which is simpler
and safer than trusting a model not to repeat them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import yaml

from jalboot.env import ROOT
from jalboot.retrieval.base import Hit, Retriever
from jalboot.retrieval.bm25 import BM25Index
from jalboot.retrieval.hybrid import HybridRetriever
from jalboot.retrieval.ngrams import CharNgramIndex

SECTION = re.compile(r"^##\s+([A-Z]+-\d+):\s*(.+?)\s*$", re.M)
ARABIC_BLOCK = re.compile(r'<div lang="ar" dir="rtl">(.*?)</div>', re.S)
HEADING = re.compile(r"^#+\s*(.+?)\s*$", re.M)
LANGUAGES = ("en", "ar")
# Enough to hold a whole section's table, short enough to keep a turn cheap.
PROMPT_CHARS = 1400


@dataclass(frozen=True)
class Passage:
    id: str
    doc: str
    doc_title: str
    language: str
    title: str
    text: str
    visibility: str
    tags: tuple[str, ...]
    updated: str

    @property
    def search_text(self) -> str:
        return f"{self.title}\n{self.title}\n{' '.join(self.tags)}\n{self.text}"


def parse_document(path: Path) -> list[Passage]:
    raw = path.read_text(encoding="utf-8")
    _, front, body = raw.split("---", 2)
    meta = yaml.safe_load(front)
    declared = {section["id"]: section for section in meta["sections"]}
    matches = list(SECTION.finditer(body))
    passages: list[Passage] = []
    for index, match in enumerate(matches):
        section_id, title_en = match.group(1), match.group(2)
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        block = body[match.end():end]
        arabic_match = ARABIC_BLOCK.search(block)
        arabic = arabic_match.group(1).strip() if arabic_match else ""
        english = ARABIC_BLOCK.sub("", block).strip()
        info = declared[section_id]
        title_ar = info.get("title_ar") or title_en
        arabic = HEADING.sub("", arabic, count=1).strip()
        shared = dict(
            id=section_id,
            doc=meta["id"],
            visibility=info.get("visibility", "public"),
            tags=tuple(info.get("tags") or ()),
            updated=str(meta.get("effective_from", "")),
        )
        passages.append(Passage(language="en", doc_title=meta["title"], title=title_en, text=english, **shared))
        passages.append(Passage(
            language="ar", doc_title=meta.get("title_ar") or meta["title"], title=title_ar, text=arabic, **shared,
        ))
    return passages


def load_passages(folder: Path | None = None) -> list[Passage]:
    folder = folder or ROOT / "knowledge"
    passages: list[Passage] = []
    for path in sorted(folder.glob("*.md")):
        passages.extend(parse_document(path))
    return passages


def load_encoder(name: str) -> Any:
    """Loads an embedding model by preset name. Empty means none. It needs the embeddings
    extra, so the default install runs with no model at all."""
    if not name:
        return None
    from jalboot.retrieval.dense import MODEL_PRESETS, SentenceTransformerEncoder

    return SentenceTransformerEncoder(MODEL_PRESETS[name])


def prompt_text(text: str) -> str:
    if len(text) <= PROMPT_CHARS:
        return text
    return text[:PROMPT_CHARS].rsplit("\n", 1)[0]


class KnowledgeBase:
    """Hybrid search per language: BM25 and character n-grams, plus dense embeddings
    when they are installed and switched on. A reranker is left out, because it lowered
    recall on the development questions (eval/results/retrieval-dev.json)."""

    def __init__(
        self,
        passages: Sequence[Passage],
        *,
        include_internal: bool = False,
        encoder: Any = None,
        cache_dir: Path | None = None,
    ):
        self.all_passages = list(passages)
        self.by_key = {(p.language, p.id): p for p in self.all_passages}
        self.section_ids = {p.id for p in self.all_passages}
        self.bm25: dict[str, BM25Index] = {}
        self.ngrams: dict[str, CharNgramIndex] = {}
        self.retrievers: dict[str, Retriever] = {}
        for language in LANGUAGES:
            visible = [
                p for p in self.all_passages
                if p.language == language and (include_internal or p.visibility != "internal")
            ]
            ids = [p.id for p in visible]
            texts = [p.search_text for p in visible]
            self.bm25[language] = BM25Index().fit(ids, texts)
            self.ngrams[language] = CharNgramIndex().fit(ids, texts)
            members: list[Retriever] = [self.bm25[language], self.ngrams[language]]
            if encoder is not None:
                from jalboot.retrieval.dense import DenseIndex

                members.append(DenseIndex(encoder, ids, texts, cache_dir))
            self.retrievers[language] = HybridRetriever(members)

    def hits(self, query: str, language: str, k: int = 5) -> list[Hit]:
        return self.retrievers.get(language, self.retrievers["en"]).search(query, k=k)

    def search(self, query: str, language: str, k: int = 4) -> list[dict[str, Any]]:
        """Each row holds BM25 term coverage as confidence, and n-gram similarity beside
        it, because typos and Gulf spellings can leave a good passage with no shared term."""
        language = language if language in LANGUAGES else "en"
        ngrams = self.ngrams[language]
        similarity = dict(zip(ngrams.doc_ids, ngrams.scores(query)))
        out = []
        for hit in self.hits(query, language, k):
            passage = self.by_key[(language, hit.doc_id)]
            out.append({
                "id": passage.id,
                "doc": passage.doc,
                "doc_title": passage.doc_title,
                "title": passage.title,
                "text": prompt_text(passage.text),
                "updated": passage.updated,
                "confidence": round(self.bm25[language].coverage(query, passage.id), 3),
                "ngram_similarity": round(float(similarity[passage.id]), 3),
            })
        return out
