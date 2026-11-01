"""The public tables are written by a script, so the script has to say what did not run."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("fill_results", ROOT / "scripts" / "fill_results.py")
fill_results = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fill_results)


def report(**overrides):
    base = {
        "cases_run": 32, "cases_in_split": 259, "partial": True, "model": "openai-gpt-oss-20b", "version": "abc",
        "date": "2026-11-01", "embeddings": "e5-small", "stopped_early": "provider limit",
        "metrics": {
            "resolution_rate": {"all": 0.75, "en": 0.8, "ar": 0.7, "ci95": [0.5, 0.9]},
            "wrong_refund_rate": {"all": 0.0, "en": 0.0, "ar": 0.0, "ci95": [0.0, 0.2], "paid": 0, "blocked": 3},
            "missed_refund_rate": {"all": 0.1, "ci95": [0.0, 0.3]},
            "qar_overpaid": 0.0,
            "unauthorized_access": {"attempted": 2, "exposed": 0},
            "citation": {"precision": 0.9, "recall": 0.8, "invented": 0, "abstention_accuracy": 0.5},
            "answer_accuracy": {"all": 0.7},
            "escalation": {"precision": 1.0, "recall": 0.9, "late": 0, "reason_accuracy": 0.8, "summary_quality": 1.0},
            "redteam": {"pass_rate": 0.9, "by_severity": {"critical": {"passed": 4, "n": 5}}},
        },
    }
    return {**base, **overrides}


def test_a_partial_run_states_its_exact_count_and_why_it_stopped():
    assert fill_results.coverage(report()) == "32 of 259 cases, partial"
    text = fill_results.summary(report(), None, None)
    assert "32 of 259 cases, partial" in text and "provider limit" in text


def test_a_run_that_did_not_happen_says_so_and_never_shows_a_number():
    table = fill_results.readme_table(report(), None)
    assert "| Resolution rate | at least 0.80 | 0.75 | Not run | Not run | Not run |" in table
    assert "TODO" not in table
    assert "TODO" not in fill_results.summary(None, None, None)


def test_a_gate_is_judged_on_the_held_out_run_only():
    held_out = report(partial=False, cases_run=105, cases_in_split=105)
    assert "| Yes |" not in fill_results.headline(report(), None)
    assert "| No |" in fill_results.headline(None, held_out)


def test_metrics_with_no_language_split_say_so():
    table = fill_results.readme_table(None, report(partial=False))
    assert "| Citation recall | at least 0.80 | Not run | 0.80 | Not split | Not split |" in table


def test_the_critical_rate_comes_from_the_severity_counts():
    assert fill_results._critical(report()) == 0.8


def test_a_table_is_only_written_between_its_markers():
    text = "before\n<!-- results:run -->\nold\n<!-- /results:run -->\nafter"
    assert fill_results.fill(text, "run", "new") == "before\n<!-- results:run -->\nnew\n<!-- /results:run -->\nafter"
    with pytest.raises(SystemExit):
        fill_results.fill("no markers", "run", "new")
