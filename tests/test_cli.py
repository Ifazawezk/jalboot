import io
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import uvicorn

from jalboot import cli
from jalboot.env import ROOT

POSTGRES = "postgresql+psycopg://jalboot:s3cret@db:5432/jalboot"


def seed_output(monkeypatch, url, encoding):
    """Runs the seed command against stdout in a chosen encoding, as a console would."""
    fake = SimpleNamespace(settings=SimpleNamespace(database_url=url))
    monkeypatch.setattr("jalboot.api.runtime.build_runtime", lambda _settings: fake)
    monkeypatch.setattr("jalboot.config.load_settings", lambda: None)
    stream = io.TextIOWrapper(io.BytesIO(), encoding=encoding)
    monkeypatch.setattr(sys, "stdout", stream)
    assert cli.seed(SimpleNamespace()) == 0
    stream.flush()
    return stream.buffer.getvalue().decode(encoding)


def test_seed_never_prints_a_database_password(monkeypatch):
    output = seed_output(monkeypatch, POSTGRES, "utf-8")
    assert "s3cret" not in output
    assert "jalboot:***@db" in output


def test_seed_survives_an_arabic_path_on_a_console_that_cannot_print_it(monkeypatch):
    output = seed_output(monkeypatch, "sqlite:///C:/Users/n/الصور/app.sqlite3", "cp1252")
    assert "app.sqlite3" in output


def test_ctrl_c_does_not_wait_for_open_streams(monkeypatch):
    started = {}
    monkeypatch.setattr(uvicorn, "run", lambda _app, **options: started.update(options))
    monkeypatch.setattr("jalboot.api.app.create_app", lambda: object())
    cli.serve(SimpleNamespace(host="127.0.0.1", port=9))
    assert started["timeout_graceful_shutdown"] == 2


def test_the_package_runs_with_python_dash_m():
    done = subprocess.run(
        [sys.executable, "-m", "jalboot", "--help"], capture_output=True, text=True,
        env={"PYTHONPATH": str(ROOT / "src"), "SYSTEMROOT": str(Path(sys.executable).anchor)}, timeout=60,
    )
    assert done.returncode == 0, done.stderr
    assert "serve" in done.stdout
