"""Runs an evaluation and writes the numbers.

    python -m jalboot.evaluation.report --split dev --system agent --mode mock
    python -m jalboot.evaluation.report --split dev --system agent --mode llm --max-requests 40

A run stops at its request budget, at its daily token cap, or at the provider's limit,
and never works around any of them. Run the same command again later: finished cases
are kept and cached replies cost nothing, so it carries on from where it stopped.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone

from jalboot.env import ROOT, load_env_file
from jalboot.evaluation import scoring
from jalboot.evaluation.baseline import PlainBot
from jalboot.evaluation.cases import EVAL_DIR, SETS, load_cases
from jalboot.evaluation.harness import CaseRunner, RunConfig, run_cases
from jalboot.kb.store import KnowledgeBase, load_encoder, load_passages
from jalboot.llm.cache import Budget, CachedClient, ResponseCache
from jalboot.llm.client import client_from_env
from jalboot.llm.mock import MockPlanner
from jalboot.policy.rules import Rules

GOLDEN_RATIO = (5 ** 0.5 - 1) / 2
RUNS = EVAL_DIR / "runs"
RESULTS = EVAL_DIR / "results"
TEST_LOG = EVAL_DIR / "test_runs.md"
CACHE = EVAL_DIR / ".cache" / "llm.jsonl"


def test_files_hash() -> str:
    digest = hashlib.sha256()
    for path in sorted((EVAL_DIR / "test").glob("*.jsonl")):
        digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


def note_test_run(version: str, why: str) -> None:
    """SCORING section 7: every run on test/ gets a line, before it runs."""
    day = datetime.now(timezone.utc).date().isoformat()
    with TEST_LOG.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(f"| {day} | {version} | {test_files_hash()} | {why} |\n")


def spread(cases: list[dict]) -> list[dict]:
    """A fixed order in which any first N cases are spread evenly over every set and every
    topic, so a run stopped by a limit is a fair cross-section and not just the first set.
    The agent and the baseline get the same order, so their first N cases are the same."""
    seen: Counter[str] = Counter()
    keyed = []
    for case in cases:
        keyed.append(((seen[case["set"]] * GOLDEN_RATIO) % 1, case["id"], case))
        seen[case["set"]] += 1
    return [case for _position, _id, case in sorted(keyed, key=lambda row: row[:2])]


def build_llm(mode: str, budget: Budget):
    if mode == "mock":
        return MockPlanner()
    load_env_file()
    client = client_from_env()
    if client is None:
        raise SystemExit("no key found. Set LLM_API_KEY in .env, or use --mode mock.")
    return CachedClient(client, ResponseCache(CACHE), budget)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--split", choices=("dev", "test"), default="dev")
    parser.add_argument("--system", choices=("agent", "baseline"), default="agent")
    parser.add_argument("--mode", choices=("mock", "llm"), default="mock")
    parser.add_argument("--sets", default=",".join(SETS))
    parser.add_argument("--version", default="0.1.0")
    parser.add_argument("--why", default="", help="required for a run on test/")
    parser.add_argument("--max-requests", type=int, default=None)
    parser.add_argument("--max-tokens", type=int, default=None)
    parser.add_argument("--daily-tokens", type=int, default=None)
    parser.add_argument("--embeddings", default="", help="embedding preset, such as e5-small")
    parser.add_argument(
        "--publish", action="store_true",
        help="write to eval/results, which is tracked. Without it the report stays in eval/runs",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="stop after this many cases of the spread order. A run with no limit carries on from here",
    )
    args = parser.parse_args(argv)

    if args.split == "test" and not args.why:
        parser.error("a run on test/ needs --why, which goes in eval/test_runs.md")
    if args.system == "baseline" and args.mode == "mock":
        parser.error("the baseline needs a real model: both sides of a mock comparison are the same keyword rules")
    if args.publish and args.mode == "mock":
        parser.error("only a run on a real model can be published")
    if args.split == "test" and args.limit:
        parser.error("--limit is for dev: a test run covers every case, unless a provider limit stops it")

    sets = tuple(args.sets.split(","))
    cases = spread(load_cases(args.split, sets))
    in_split = len(cases)
    cases = cases[:args.limit] if args.limit else cases
    budget = Budget(requests=args.max_requests, tokens=args.max_tokens, daily_tokens=args.daily_tokens)
    llm = build_llm(args.mode, budget)
    knowledge = KnowledgeBase(
        load_passages(), encoder=load_encoder(args.embeddings), cache_dir=ROOT / "var" / "index",
    )
    rules = Rules.load()
    baseline = args.system == "baseline"
    runner = CaseRunner(
        llm, knowledge, rules, RunConfig(unguarded=baseline), agent_class=PlainBot if baseline else None,
    )

    model = "mock" if args.mode == "mock" else llm.model.replace("/", "-")
    name = f"{args.split}-{args.system}-{model}"
    # Records are only resumed for the same version. A run must never mix results
    # from code that has since changed.
    path = RUNS / f"{name}-v{args.version}.jsonl"
    if args.mode == "mock" and path.exists():
        path.unlink()
    if args.split == "test":
        note_test_run(args.version, args.why)
    done, stopped = run_cases(runner, cases, path, lambda case_id: print("done", case_id, flush=True))

    day = datetime.now(timezone.utc).date().isoformat()
    report = scoring.aggregate(
        cases, done, knowledge.section_ids, version=args.version, split=args.split, date=day,
    )
    report.update(
        system=args.system, mode=args.mode, model=model, stopped_early=stopped,
        cases_in_split=in_split, partial=report["cases_run"] < in_split,
        embeddings=args.embeddings or "none", tokens_used=budget.tokens_used, requests_used=budget.requests_used,
        note="" if args.mode == "llm" else "Mock mode: a keyword planner, not a model.",
    )
    folder = RESULTS if args.publish else RUNS
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / f"{name}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"{report['cases_run']} of {in_split} cases. Report: {out.relative_to(ROOT)}")
    print(f"requests {budget.requests_used}, tokens {budget.tokens_used}, cache hits {budget.cache_hits}")
    if stopped:
        print(f"Stopped early: {stopped}. Run the same command later to continue.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

