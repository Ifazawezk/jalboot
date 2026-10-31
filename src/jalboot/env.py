"""Reads local settings from a gitignored .env file.

The process environment always wins over the file. This module handles names
only: it never logs, prints or returns a value it read, so a key cannot leak
through it.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import MutableMapping

ROOT = Path(__file__).resolve().parents[2]
LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$")


def parse_env(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        match = LINE.match(line)
        if not match:
            continue
        name, value = match.groups()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        else:
            value = value.split(" #", 1)[0].rstrip()
        values[name] = value
    return values


def load_env_file(
    path: Path | None = None, environ: MutableMapping[str, str] | None = None
) -> list[str]:
    """Add variables from the file that are not already set, and return their names."""
    environ = os.environ if environ is None else environ
    path = path or Path(environ.get("JALBOOT_ENV_FILE") or ROOT / ".env")
    try:
        # utf-8-sig: Notepad can save a byte order mark, which would corrupt the first name.
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return []
    added = []
    for name, value in parse_env(text).items():
        if value and not environ.get(name):
            environ[name] = value
            added.append(name)
    return added
