"""Loads the machine-readable policy and handles money.

knowledge/rules.json is the one place a limit is written down. The policy documents
quote the same figures in prose, and a test checks that they still agree.
"""

from __future__ import annotations

import json
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

from jalboot.env import ROOT


def to_dh(qar: Any) -> int:
    """QAR to whole dirhams, half up. Goes through str so 0.1 stays exactly 0.1."""
    return int((Decimal(str(qar)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def to_qar(dh: int) -> float:
    return float(Decimal(dh) / 100)


def percent_of(dh: int, percent: float) -> int:
    value = Decimal(dh) * Decimal(str(percent)) / 100
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


class Rules:
    def __init__(self, data: dict[str, Any]):
        self.data = data

    @classmethod
    def load(cls, path: Path | None = None) -> "Rules":
        path = path or ROOT / "knowledge" / "rules.json"
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def get(self, dotted: str) -> Any:
        node: Any = self.data
        for part in dotted.split("."):
            node = node[part]
        return node

    def dh(self, dotted: str) -> int:
        return to_dh(self.get(dotted))

    @property
    def version(self) -> str:
        return str(self.data["meta"]["policy_version"])
