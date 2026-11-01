"""Optional dense retrieval with multilingual sentence embeddings.

The index is a plain normalized matrix: the knowledge base has a few hundred
passages, so an exact dot product is fast and needs no approximate search. The
model is not in the default install, and it never goes in git.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence

import numpy as np

from jalboot.retrieval.base import Hit, top_hits

log = logging.getLogger("jalboot.dense")


@dataclass(frozen=True)
class ModelSpec:
    model_name: str
    query_prefix: str = ""
    passage_prefix: str = ""
    max_chars: int = 900


MODEL_PRESETS = {
    "e5-small": ModelSpec("intfloat/multilingual-e5-small", "query: ", "passage: ", 900),
    "minilm": ModelSpec("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", max_chars=400),
}


class Encoder(Protocol):
    name: str
    max_chars: int

    def encode_queries(self, texts: Sequence[str]) -> np.ndarray: ...

    def encode_passages(self, texts: Sequence[str]) -> np.ndarray: ...


class SentenceTransformerEncoder:
    """Wraps a sentence-transformers model and returns L2-normalized vectors."""

    def __init__(self, spec: ModelSpec, batch_size: int = 16):
        from sentence_transformers import SentenceTransformer

        self.spec = spec
        self.name = spec.model_name
        self.max_chars = spec.max_chars
        self.batch_size = batch_size
        self.model = SentenceTransformer(spec.model_name, device="cpu")

    def _encode(self, texts: Sequence[str]) -> np.ndarray:
        vectors = self.model.encode(
            list(texts), batch_size=self.batch_size, normalize_embeddings=True,
            convert_to_numpy=True, show_progress_bar=False,
        )
        return vectors.astype(np.float32)

    def encode_queries(self, texts: Sequence[str]) -> np.ndarray:
        return self._encode([self.spec.query_prefix + t for t in texts])

    def encode_passages(self, texts: Sequence[str]) -> np.ndarray:
        return self._encode([self.spec.passage_prefix + t for t in texts])


def fingerprint(model: str, doc_ids: Sequence[str], texts: Sequence[str]) -> str:
    digest = hashlib.sha256(model.encode("utf-8"))
    for doc, text in zip(doc_ids, texts):
        digest.update(f"{doc}\t{text}\n".encode("utf-8"))
    return digest.hexdigest()[:16]


class DenseIndex:
    name = "dense"

    def __init__(
        self,
        encoder: Encoder,
        doc_ids: Sequence[str],
        texts: Sequence[str],
        cache_dir: Path | None = None,
    ):
        self.encoder = encoder
        self.doc_ids = list(doc_ids)
        clipped = [text[: encoder.max_chars] for text in texts]
        path = None
        if cache_dir is not None:
            path = cache_dir / f"dense-{fingerprint(encoder.name, self.doc_ids, clipped)}.npy"
        if path is not None and path.exists():
            self.embeddings = np.load(path)
        else:
            self.embeddings = encoder.encode_passages(clipped)
            if path is not None:
                path.parent.mkdir(parents=True, exist_ok=True)
                np.save(path, self.embeddings)

    def search(self, query: str, k: int = 10) -> list[Hit]:
        vector = self.encoder.encode_queries([query])[0]
        return top_hits(self.doc_ids, self.embeddings @ vector, k)
