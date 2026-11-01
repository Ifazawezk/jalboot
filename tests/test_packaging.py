import tomllib

import yaml

from jalboot.api.runtime import STAFF_PASSWORD_VARIABLES
from jalboot.env import ROOT


def test_compose_passes_on_the_settings_production_needs():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    passed = compose["services"]["app"]["environment"]
    assert {
        "ENVIRONMENT", "COOKIE_SECURE", "SHOW_SIMULATED_OTP", "ALLOWED_ORIGINS", "LLM_PROVIDER", "LLM_BASE_URL",
        *STAFF_PASSWORD_VARIABLES.values(),
    } <= set(passed)


def test_the_image_fails_closed_when_it_is_run_without_settings():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "ENV ENVIRONMENT=production" in dockerfile


def test_unused_dependencies_stay_out_and_fastapi_stays_pinned():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    declared = " ".join([*project["dependencies"], *project["optional-dependencies"]["dev"]])
    assert "websockets" not in declared
    assert "playwright" not in declared
    assert "fastapi>=0.162,<0.163" in declared
    assert "pyyaml>=6.0.1" in declared
    assert "uvicorn>=0.54" in declared  # serve passes it a loop factory by name
