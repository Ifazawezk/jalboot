"""An installed package has no repo around it, so nothing may look for one.

The first test fakes that layout and runs with every test. The second builds a real
wheel, installs it in a new virtual environment and starts the server. It downloads
the dependencies, so it only runs when JALBOOT_INSTALL_TEST is set.
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from jalboot import config, env
from jalboot.api import runtime as runtime_module
from jalboot.api.runtime import build_runtime
from jalboot.config import ConfigError, Settings, load_settings
from jalboot.kb import store
from jalboot.policy import rules as rules_module

REPO = Path(__file__).resolve().parents[1]
INSTALL_PORT = 8431


@pytest.fixture
def no_repo(tmp_path, monkeypatch):
    """Points every ROOT at an empty folder, as lib/python3.12 is once installed."""
    empty = tmp_path / "lib"
    empty.mkdir()
    for module in (env, config, rules_module, store):
        monkeypatch.setattr(module, "ROOT", empty)
    return empty


def test_a_new_install_seeds_its_world_from_the_configured_rules(tmp_path, no_repo):
    settings = Settings(
        database_url=f"sqlite:///{(tmp_path / 'fresh.sqlite3').as_posix()}", world_scale=0.05,
        knowledge_dir=REPO / "knowledge", index_dir=tmp_path / "index", web_dist=tmp_path / "missing",
    )
    runtime = build_runtime(settings)
    assert runtime.rules.get("meta.currency") == "QAR"


def test_seeding_uses_the_configured_rules_and_not_the_repo_copy(tmp_path, monkeypatch):
    loaded = []
    real_load = runtime_module.Rules.load

    def spy(path=None):
        loaded.append(path)
        return real_load(path)

    monkeypatch.setattr(runtime_module.Rules, "load", staticmethod(spy))
    settings = Settings(
        database_url=f"sqlite:///{(tmp_path / 'fresh.sqlite3').as_posix()}", world_scale=0.05,
        knowledge_dir=REPO / "knowledge", index_dir=tmp_path / "index", web_dist=tmp_path / "missing",
    )
    build_runtime(settings)
    assert loaded and all(path == REPO / "knowledge" / "rules.json" for path in loaded)


def test_a_missing_knowledge_folder_is_named_at_startup(tmp_path):
    with pytest.raises(ConfigError, match="KNOWLEDGE_DIR"):
        load_settings({"KNOWLEDGE_DIR": str(tmp_path / "nowhere")})


def wait_for_health(url, server, seconds=60):
    deadline = time.time() + seconds
    while time.time() < deadline:
        if server.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                return response.status == 200
        except OSError:
            time.sleep(0.5)
    return False


@pytest.mark.skipif(not os.environ.get("JALBOOT_INSTALL_TEST"), reason="set JALBOOT_INSTALL_TEST to run")
def test_a_real_install_starts_and_answers(tmp_path):
    """A plain pip install in a clean environment, run from outside the repo."""
    with socket.socket() as probe:
        assert probe.connect_ex(("127.0.0.1", INSTALL_PORT)) != 0, "the port is in use"

    source = tmp_path / "source"
    shutil.copytree(
        REPO, source,
        ignore=shutil.ignore_patterns(".git", "web", "eval", "var", "docs", "tests", "__pycache__", "*.egg-info", "build"),
    )
    venv = tmp_path / "venv"
    subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
    scripts = venv / ("Scripts" if os.name == "nt" else "bin")
    python = scripts / ("python.exe" if os.name == "nt" else "python")
    # The same command as the Dockerfile, so this also proves the lock file can be met.
    subprocess.run(
        [str(python), "-m", "pip", "install", "--quiet", "--no-input", "--constraint", str(REPO / "requirements.lock"),
         f"{source}[postgres]"],
        check=True, timeout=600,
    )

    where = subprocess.run(
        [str(python), "-c", "import jalboot; print(jalboot.__file__)"], cwd=tmp_path,
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    assert str(venv) in where and str(REPO) not in where

    server_env = {
        key: value for key, value in os.environ.items() if key not in {"PYTHONPATH", "DATABASE_URL", "KNOWLEDGE_DIR"}
    }
    server_env.update({
        "KNOWLEDGE_DIR": str(REPO / "knowledge"), "WEB_DIST": str(tmp_path / "no-web"),
        "INDEX_DIR": str(tmp_path / "index"), "DATABASE_URL": f"sqlite:///{(tmp_path / 'app.sqlite3').as_posix()}",
        "LLM_MODE": "mock", "WORLD_SCALE": "0.05",
    })
    log = (tmp_path / "server.log").open("w", encoding="utf-8")
    server = subprocess.Popen(
        [str(scripts / "jalboot"), "serve", "--port", str(INSTALL_PORT)], cwd=tmp_path, env=server_env, stdout=log, stderr=log,
    )
    base = f"http://127.0.0.1:{INSTALL_PORT}/api/v1"
    try:
        assert wait_for_health(f"{base}/health", server), (tmp_path / "server.log").read_text(encoding="utf-8")
        with urllib.request.urlopen(f"{base}/policy", timeout=5) as response:
            assert json.load(response)["currency"] == "QAR"
        request = urllib.request.Request(
            f"{base}/conversations", data=b'{"locale": "en"}', headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            assert response.status == 201
    finally:
        server.terminate()
        server.wait(timeout=15)
        log.close()
