"""Recordings go out on a public page, so they must be real and hold nothing private."""

import json

import pytest

from jalboot.env import ROOT

RECORDINGS = sorted((ROOT / "demo" / "recordings").glob("*.json"))


@pytest.mark.parametrize("path", RECORDINGS, ids=lambda path: path.stem)
def test_a_published_recording_is_a_real_run_with_nothing_private(path):
    text = path.read_text(encoding="utf-8")
    recording = json.loads(text)
    assert recording["source"].count("/") >= 1 and "mock" not in recording["source"]
    assert recording["recordedAt"] and recording["steps"]
    assert "simulatedCode" not in text and "97401001" not in text and "+974 0100" not in text
