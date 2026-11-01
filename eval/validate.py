"""Check the evaluation sets for structural problems.

Usage:
    python validate.py                 check everything
    python validate.py --freeze        rewrite MANIFEST.json from the current files
    python validate.py --knowledge DIR check section ids against another folder

Standard library only. Nothing here calls a model or a network service.
Exit code is 0 when clean and 1 when any problem is found.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
SETS = ("support", "knowledge", "handoff", "redteam")
SPLITS = ("dev", "test")
ID_PREFIX = {"support": "SUP", "knowledge": "KNW", "handoff": "HND", "redteam": "RED"}

TOOLS = {
    "get_customer_profile",
    "quote_refund",
    "track_order",
    "get_order_details",
    "explain_delay",
    "issue_refund",
    "issue_credit",
    "apply_promo",
    "change_address",
    "cancel_order",
    "create_ticket",
    "handoff_to_human",
    "search_knowledge",
}

SUPPORT_OUTCOMES = {
    "resolved",
    "resolved_no_action",
    "refused_by_policy",
    "pending_approval",
    "ticket_created",
    "handed_off",
    "needs_more_info",
}
DIFFICULTY = {"normal", "edge", "policy_boundary"}
ATTACK_CLASSES = {
    "injection_customer_message",
    "injection_merchant_note",
    "injection_retrieved_document",
    "cross_customer_access",
    "refund_social_engineering",
    "tool_argument_manipulation",
    "system_prompt_leak",
    "internal_policy_leak",
    "identity_bypass",
}
SEVERITY = {"critical", "high", "medium"}
KNOWLEDGE_TYPES = {"direct", "paraphrase", "numeric", "multi_section", "unanswerable"}

FORBIDDEN_CHARS = {
    chr(0x2014): "em dash",
    chr(0x2013): "en dash",
}
EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF️]"
)
ARABIC = re.compile(r"[؀-ۿ]")


def load(path: Path, problems: list[str]) -> list[dict]:
    rows = []
    if not path.exists():
        problems.append(f"missing file: {path.name}")
        return rows
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            problems.append(f"{path.name}:{number}: blank line")
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            problems.append(f"{path.name}:{number}: bad JSON: {exc}")
    return rows


def walk_strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from walk_strings(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk_strings(value)


def known_sections(folder: Path) -> tuple[set[str], set[str]]:
    """Section ids from each document's front matter: (all, internal)."""
    everything: set[str] = set()
    internal: set[str] = set()
    if not folder.exists():
        return everything, internal
    pattern = re.compile(r"- id: ([A-Z]+-\d+)\n(?:\s+\w+: .*\n)*?\s+visibility: (\w+)")
    for path in sorted(folder.glob("*.md")):
        for section, visibility in pattern.findall(path.read_text(encoding="utf-8").replace("\r\n", "\n")):
            everything.add(section)
            if visibility == "internal":
                internal.add(section)
    return everything, internal


def check_calls(case_id: str, calls, problems: list[str], label: str) -> None:
    if not isinstance(calls, list):
        problems.append(f"{case_id}: {label} must be a list")
        return
    for call in calls:
        if not isinstance(call, dict) or call.get("tool") not in TOOLS:
            problems.append(f"{case_id}: {label} has unknown tool: {call}")


def check_common(row: dict, problems: list[str]) -> None:
    cid = row.get("id", "<no id>")
    for field in ("id", "set", "group", "lang", "split", "category"):
        if field not in row:
            problems.append(f"{cid}: missing {field}")
    if row.get("lang") not in ("en", "ar"):
        problems.append(f"{cid}: bad lang {row.get('lang')}")
    for text in walk_strings(row):
        for char, name in FORBIDDEN_CHARS.items():
            if char in text:
                problems.append(f"{cid}: contains {name}: {text[:60]}")
        if EMOJI.search(text):
            problems.append(f"{cid}: contains emoji: {text[:60]}")


def first_customer_text(row: dict) -> str:
    for turn in row.get("conversation", []):
        if turn.get("role") == "customer":
            return turn.get("text", "")
    return row.get("question", "")


def check_support(row: dict, problems: list[str]) -> None:
    cid = row["id"]
    if row.get("difficulty") not in DIFFICULTY:
        problems.append(f"{cid}: bad difficulty {row.get('difficulty')}")
    for field in ("title", "now", "conversation", "state", "expected"):
        if field not in row:
            problems.append(f"{cid}: missing {field}")
            return
    expected = row["expected"]
    check_calls(cid, expected.get("tool_calls", []), problems, "tool_calls")
    check_calls(cid, expected.get("forbidden_calls", []), problems, "forbidden_calls")
    outcome = expected.get("outcome", {})
    if outcome.get("type") not in SUPPORT_OUTCOMES:
        problems.append(f"{cid}: bad outcome type {outcome.get('type')}")
    for other in outcome.get("also_accept", []):
        if other not in SUPPORT_OUTCOMES:
            problems.append(f"{cid}: bad also_accept type {other}")
    if "refund_qar" not in outcome:
        problems.append(f"{cid}: outcome needs refund_qar (0 when none is due)")
    if "handoff" not in expected:
        problems.append(f"{cid}: expected.handoff is required")
    if "citations" not in expected:
        problems.append(f"{cid}: expected.citations is required")
    required = {call["tool"] for call in expected.get("tool_calls", []) if call.get("required", True)}
    forbidden_tools = {call["tool"] for call in expected.get("forbidden_calls", []) if not call.get("args")}
    overlap = required & forbidden_tools
    if overlap:
        problems.append(f"{cid}: tool both required and forbidden: {overlap}")
    if outcome.get("refund_qar", 0) > 0:
        tools = {call["tool"] for call in expected.get("tool_calls", [])}
        if not tools & {"issue_refund", "issue_credit"}:
            problems.append(f"{cid}: refund_qar > 0 without a refund or credit call")
    total = sum(
        call.get("args", {}).get("amount_qar", 0)
        for call in expected.get("tool_calls", [])
        if call["tool"] in ("issue_refund", "issue_credit")
    )
    gold = outcome.get("refund_qar", 0) or outcome.get("pending_refund_qar", 0)
    if total and abs(total - gold) > 0.001:
        problems.append(f"{cid}: call amounts {total} differ from the outcome {gold}")


def check_citations(row: dict, sections: set[str], internal: set[str], problems: list[str]) -> None:
    cid = row.get("id")
    expected = row.get("expected") or {}
    cited = [c["section"] if isinstance(c, dict) else c for c in expected.get("citations", [])]
    cited += list(row.get("gold_sections") or [])
    for group in row.get("gold_any_of") or []:
        cited += list(group)
    for section in cited:
        if sections and section not in sections:
            problems.append(f"{cid}: unknown section {section}")
        if section in internal:
            problems.append(f"{cid}: internal section {section} used as a customer citation")


def check_knowledge(row: dict, problems: list[str]) -> None:
    cid = row["id"]
    if row.get("type") not in KNOWLEDGE_TYPES:
        problems.append(f"{cid}: bad type {row.get('type')}")
    if not row.get("question"):
        problems.append(f"{cid}: empty question")
    gold = row.get("gold_sections")
    if not isinstance(gold, list):
        problems.append(f"{cid}: gold_sections must be a list")
        return
    answerable = row.get("answerable")
    groups = row.get("gold_any_of") or []
    if answerable is True and not gold and not groups:
        problems.append(f"{cid}: answerable with no gold sections")
    if answerable is False and (gold or groups):
        problems.append(f"{cid}: unanswerable but has gold sections")
    if answerable and not row.get("answer_must_include"):
        problems.append(f"{cid}: answerable with nothing to check in the answer")


def check_handoff(row: dict, problems: list[str]) -> None:
    cid = row["id"]
    for field in ("conversation", "state", "expected", "now"):
        if field not in row:
            problems.append(f"{cid}: missing {field}")
            return
    expected = row["expected"]
    if not isinstance(expected.get("handoff"), bool):
        problems.append(f"{cid}: expected.handoff must be true or false")
    check_calls(cid, expected.get("tool_calls", []), problems, "tool_calls")
    check_calls(cid, expected.get("forbidden_calls", []), problems, "forbidden_calls")
    tools = {call["tool"] for call in expected.get("tool_calls", [])}
    forbidden = {call["tool"] for call in expected.get("forbidden_calls", [])}
    if expected.get("handoff") is True:
        if "handoff_to_human" not in tools:
            problems.append(f"{cid}: handoff true without a handoff call")
        if not expected.get("reason"):
            problems.append(f"{cid}: handoff true needs reason")
    else:
        if "handoff_to_human" not in forbidden:
            problems.append(f"{cid}: handoff false must forbid the handoff call")


def check_redteam(row: dict, problems: list[str]) -> None:
    cid = row["id"]
    if row.get("attack_class") not in ATTACK_CLASSES:
        problems.append(f"{cid}: bad attack_class {row.get('attack_class')}")
    if row.get("severity") not in SEVERITY:
        problems.append(f"{cid}: bad severity {row.get('severity')}")
    for field in ("conversation", "state", "expected", "now", "expected_safe_behaviour", "attack_goal"):
        if field not in row:
            problems.append(f"{cid}: missing {field}")
            return
    expected = row["expected"]
    check_calls(cid, expected.get("tool_calls", []), problems, "tool_calls")
    check_calls(cid, expected.get("forbidden_calls", []), problems, "forbidden_calls")
    if not expected.get("forbidden_calls") and not expected.get("must_not_leak"):
        problems.append(f"{cid}: needs forbidden_calls or must_not_leak so a pass can be measured")
    vector = row.get("vector")
    if vector == "merchant_note":
        notes = [
            order.get("merchant_note")
            for order in row["state"].get("orders", [])
            if order.get("merchant_note")
        ]
        if not notes:
            problems.append(f"{cid}: merchant note attack without a note in state")
    if vector == "retrieved_document" and not row.get("injected_document"):
        problems.append(f"{cid}: retrieved document attack without injected_document")


def check_language(row: dict, problems: list[str]) -> None:
    text = first_customer_text(row)
    if not text:
        problems.append(f"{row.get('id')}: no first customer message")
        return
    has_arabic = bool(ARABIC.search(text))
    if row.get("lang") == "ar" and not has_arabic:
        problems.append(f"{row.get('id')}: lang is ar but first message has no Arabic")
    if row.get("lang") == "en" and has_arabic and not row.get("mixed_language"):
        problems.append(f"{row.get('id')}: lang is en but first message has Arabic")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--knowledge", default=str(HERE.parent / "knowledge"))
    args = parser.parse_args()

    problems: list[str] = []
    sections, internal = known_sections(Path(args.knowledge))
    all_ids: dict[str, str] = {}
    groups: dict[str, set[str]] = {}
    table: dict[str, Counter] = {}
    texts: dict[str, str] = {}

    # The held-out files stay out of the repo until the final scored run, so they are
    # reported as unpublished, not as missing.
    published = (HERE / "test").exists()
    if not published:
        print("test/: not published yet. It ships after the final scored run, with its frozen manifest.")
    for set_name in SETS:
        for split in SPLITS:
            if split == "test" and not published:
                continue
            path = HERE / split / f"{set_name}.jsonl"
            rows = load(path, problems)
            table[f"{set_name}/{split}"] = Counter(row.get("lang") for row in rows)
            for row in rows:
                cid = row.get("id", "<no id>")
                if cid in all_ids:
                    problems.append(f"{cid}: duplicate id")
                all_ids[cid] = split
                if not str(cid).startswith(ID_PREFIX[set_name] + "-"):
                    problems.append(f"{cid}: wrong prefix for {set_name}")
                if row.get("set") != set_name:
                    problems.append(f"{cid}: set field is {row.get('set')}")
                if row.get("split") != split:
                    problems.append(f"{cid}: split field is {row.get('split')}, file is {split}")
                check_common(row, problems)
                check_language(row, problems)
                check_citations(row, sections, internal, problems)
                if split == "test" and (row.get("debatable") or "ambiguous_combination" in row.get("tags", [])):
                    problems.append(f"{cid}: a debatable case is in the test split")
                groups.setdefault(row.get("group", cid), set()).add(split)
                if set_name == "support":
                    check_support(row, problems)
                elif set_name == "knowledge":
                    check_knowledge(row, problems)
                elif set_name == "handoff":
                    check_handoff(row, problems)
                else:
                    check_redteam(row, problems)
                first = first_customer_text(row).strip()
                if first:
                    other = texts.get(first)
                    if other and other != cid:
                        problems.append(f"{cid}: same first message as {other}")
                    texts[first] = cid

    for group, splits in groups.items():
        if len(splits) > 1:
            problems.append(f"group {group} appears in both dev and test")

    manifest_path = HERE / "MANIFEST.json"
    current = {}
    for split in SPLITS:
        for set_name in SETS:
            path = HERE / split / f"{set_name}.jsonl"
            if path.exists():
                current[f"{split}/{set_name}.jsonl"] = {
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "cases": len(path.read_text(encoding="utf-8").splitlines()),
                }
    if args.freeze:
        manifest_path.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
    elif manifest_path.exists():
        frozen = json.loads(manifest_path.read_text(encoding="utf-8"))
        for name, info in frozen.items():
            if name.startswith("test/") and current.get(name, {}).get("sha256") != info["sha256"]:
                problems.append(f"{name}: changed since it was frozen")

    print(f"{'set/split':<20}{'en':>5}{'ar':>5}{'all':>6}")
    total = 0
    for key, counts in table.items():
        count = sum(counts.values())
        total += count
        print(f"{key:<20}{counts.get('en', 0):>5}{counts.get('ar', 0):>5}{count:>6}")
    print(f"{'total':<20}{'':>10}{total:>6}")
    print(f"knowledge sections: {len(sections)}, internal: {len(internal)}")

    for problem in problems:
        print("PROBLEM:", problem)
    print(f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
