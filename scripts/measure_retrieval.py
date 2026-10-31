"""Measures retrieval, with no language model involved.

Compares keyword search, character n-grams, the two fused, and optionally dense
embeddings and a reranker. It writes retrieval-<split>.json to eval/runs/, which git
ignores, and --publish writes to eval/results/ instead. Dense and reranker runs need the
embeddings extra and a local model.

    python scripts/measure_retrieval.py --split dev --dense --rerank-model PATH_OR_NAME
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jalboot.evaluation.cases import load_cases  # noqa: E402
from jalboot.evaluation.retrieval import paired_change, questions_from, recall_table  # noqa: E402
from jalboot.kb.store import load_passages  # noqa: E402
from jalboot.retrieval.bm25 import BM25Index  # noqa: E402
from jalboot.retrieval.hybrid import HybridRetriever  # noqa: E402
from jalboot.retrieval.ngrams import CharNgramIndex  # noqa: E402

LANGUAGES = ("en", "ar")


def build(passages, make):
    table = {}
    for language in LANGUAGES:
        visible = [p for p in passages if p.language == language and p.visibility != "internal"]
        table[language] = make([p.id for p in visible], [p.search_text for p in visible], language)
    return table


def searcher(table):
    return lambda text, language, k: table[language].search(text, k)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--split", choices=("dev", "test"), default="dev")
    parser.add_argument("--dense", action="store_true")
    parser.add_argument("--dense-model", default="e5-small")
    parser.add_argument("--rerank-model", default="")
    parser.add_argument("--publish", action="store_true", help="write to eval/results, which is tracked")
    args = parser.parse_args()

    passages = load_passages()
    questions = questions_from(load_cases(args.split, ("knowledge",)))
    bm25 = build(passages, lambda ids, texts, _language: BM25Index().fit(ids, texts))
    ngrams = build(passages, lambda ids, texts, _language: CharNgramIndex().fit(ids, texts))
    hybrid = {language: HybridRetriever([bm25[language], ngrams[language]]) for language in LANGUAGES}
    systems = {"bm25": bm25, "ngrams": ngrams, "bm25+ngrams": hybrid}

    if args.dense:
        from jalboot.retrieval.dense import MODEL_PRESETS, DenseIndex, SentenceTransformerEncoder

        encoder = SentenceTransformerEncoder(MODEL_PRESETS[args.dense_model])
        dense = build(
            passages, lambda ids, texts, _language: DenseIndex(encoder, ids, texts, ROOT / "var" / "index"),
        )
        systems["dense"] = dense
        systems["bm25+dense"] = {l: HybridRetriever([bm25[l], dense[l]]) for l in LANGUAGES}
        systems["bm25+ngrams+dense"] = {l: HybridRetriever([bm25[l], ngrams[l], dense[l]]) for l in LANGUAGES}

    if args.rerank_model:
        from jalboot.retrieval.rerank import CrossEncoderScorer, RerankingRetriever

        scorer = CrossEncoderScorer(args.rerank_model)
        best = systems.get("bm25+ngrams+dense", hybrid)
        texts = {
            language: {p.id: p.text[:1200] for p in passages if p.language == language}
            for language in LANGUAGES
        }
        systems["best+reranker"] = {
            l: RerankingRetriever(best[l], scorer, texts[l], depth=10) for l in LANGUAGES
        }

    base = searcher(hybrid)
    report: dict = {"split": args.split, "questions": len(questions), "systems": {}, "paired_vs_bm25_ngrams_at_3": {}}
    for name, table in systems.items():
        search = searcher(table)
        report["systems"][name] = recall_table(questions, search)
        if table is not hybrid:
            report["paired_vs_bm25_ngrams_at_3"][name] = paired_change(questions, base, search, 3)
        row = report["systems"][name]
        print(f"{name:22} R@3 {row['recall_at_3']['value']:.3f}  R@5 {row['recall_at_5']['value']:.3f}  "
              f"MRR {row['mrr']:.3f}  en R@3 {row['recall_at_3_en']['value']:.3f}  ar R@3 {row['recall_at_3_ar']['value']:.3f}",
              flush=True)
    out = ROOT / "eval" / ("results" if args.publish else "runs") / f"retrieval-{args.split}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(report["paired_vs_bm25_ngrams_at_3"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
