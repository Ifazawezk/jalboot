"""A server others can reach must not run on the staff password printed in the README.

The demo mode exists because a public demo needs the simulated code, as there is no
SMS provider. Before it, the only way to get that code was to turn every check off.
"""

import pytest
from fastapi.testclient import TestClient

from jalboot.api.app import create_app
from jalboot.api.runtime import DEV_STAFF_PASSWORD, MIN_STAFF_PASSWORD, STAFF_PASSWORD_VARIABLES, build_runtime
from jalboot.config import ConfigError, Settings, load_settings
from tests.conftest import database_url

SECRET = "x" * 40
AGENT, SUPERVISOR, FINANCE = "agent-password-1", "supervisor-password-2", "finance-password-3"
CHOSEN = {
    "STAFF_PASSWORD_AGENT": AGENT, "STAFF_PASSWORD_SUPERVISOR": SUPERVISOR, "STAFF_PASSWORD_FINANCE_LEAD": FINANCE,
}
DEMO = {"ENVIRONMENT": "demo", "SECRET_KEY": SECRET, "COOKIE_SECURE": "true"}


@pytest.fixture(autouse=True)
def no_passwords_from_the_machine(monkeypatch):
    for name in (*STAFF_PASSWORD_VARIABLES.values(), "DEMO_STAFF_PASSWORD"):
        monkeypatch.delenv(name, raising=False)


def public(tmp_path, environment="demo"):
    return Settings(
        database_url=database_url(tmp_path), environment=environment, secret_key=SECRET, cookie_secure=True,
        show_simulated_otp=environment == "demo", world_scale=0.05, web_dist=tmp_path / "missing",
        index_dir=tmp_path / "index",
    )


def choose(monkeypatch, passwords=CHOSEN):
    for name, value in passwords.items():
        monkeypatch.setenv(name, value)


def test_demo_mode_may_show_the_simulated_code():
    settings = load_settings(DEMO)
    assert settings.show_simulated_otp
    assert settings.is_public
    assert not settings.is_production


@pytest.mark.parametrize("change", [{"SECRET_KEY": ""}, {"SECRET_KEY": "short"}, {"COOKIE_SECURE": "false"}])
def test_demo_mode_still_needs_a_real_secret_and_secure_cookies(change):
    with pytest.raises(ConfigError):
        load_settings({**DEMO, **change})


def test_production_still_refuses_the_simulated_code():
    with pytest.raises(ConfigError, match="SHOW_SIMULATED_OTP"):
        load_settings({**DEMO, "ENVIRONMENT": "production"})


def test_demo_mode_does_not_allow_the_local_dev_server():
    assert load_settings(DEMO).allowed_origins == ()


@pytest.mark.parametrize("environment", ["demo", "production"])
def test_a_public_server_will_not_seed_without_chosen_passwords(tmp_path, environment):
    with pytest.raises(ConfigError, match="STAFF_PASSWORD_AGENT"):
        build_runtime(public(tmp_path, environment))


def test_one_password_for_all_staff_is_not_enough(tmp_path, monkeypatch):
    monkeypatch.setenv("DEMO_STAFF_PASSWORD", "a-long-shared-password")
    with pytest.raises(ConfigError, match="STAFF_PASSWORD_AGENT"):
        build_runtime(public(tmp_path))


def test_a_short_password_is_refused(tmp_path, monkeypatch):
    choose(monkeypatch, {**CHOSEN, "STAFF_PASSWORD_SUPERVISOR": "x" * (MIN_STAFF_PASSWORD - 1)})
    with pytest.raises(ConfigError, match=str(MIN_STAFF_PASSWORD)):
        build_runtime(public(tmp_path))


def test_two_accounts_cannot_share_a_password(tmp_path, monkeypatch):
    choose(monkeypatch, {**CHOSEN, "STAFF_PASSWORD_SUPERVISOR": AGENT})
    with pytest.raises(ConfigError, match="own password"):
        build_runtime(public(tmp_path))


def test_the_published_password_cannot_be_chosen(tmp_path, monkeypatch):
    choose(monkeypatch, {**CHOSEN, "STAFF_PASSWORD_AGENT": DEV_STAFF_PASSWORD})
    with pytest.raises(ConfigError):
        build_runtime(public(tmp_path))


def test_each_account_signs_in_with_its_own_password_only(tmp_path, monkeypatch):
    choose(monkeypatch)
    with TestClient(create_app(public(tmp_path)), base_url="https://testserver") as client:
        def login(email, password):
            return client.post("/api/v1/desk/session", json={"email": f"{email}@jalboot.example", "password": password})

        assert login("sara", AGENT).status_code == 200
        assert login("khalid", SUPERVISOR).status_code == 200
        assert login("amal", FINANCE).status_code == 200
        assert login("amal", AGENT).status_code == 401
        assert login("sara", DEV_STAFF_PASSWORD).status_code == 401


def test_a_database_seeded_for_development_cannot_go_public(tmp_path, monkeypatch):
    """Passwords are only read when seeding, so this would otherwise keep the public one."""
    build_runtime(Settings(
        database_url=database_url(tmp_path), world_scale=0.05, web_dist=tmp_path / "missing", index_dir=tmp_path / "index",
    )).engine.dispose()
    choose(monkeypatch)
    with pytest.raises(ConfigError, match="development password"):
        build_runtime(public(tmp_path))


def test_development_keeps_working_with_no_password_set(tmp_path):
    runtime = build_runtime(Settings(
        database_url=database_url(tmp_path), world_scale=0.05, web_dist=tmp_path / "missing", index_dir=tmp_path / "index",
    ))
    assert runtime.settings.environment == "development"
