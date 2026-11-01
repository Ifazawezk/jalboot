"""A limit has to hold when requests arrive together. These fire them at once through
the real app, whose routes run on a thread pool, because one request at a time cannot
show a race. The audit log counts what was really checked, since a response can say
429 after the guess behind it has already been compared."""

import asyncio
import time

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from jalboot.api import identity
from jalboot.api.app import create_app
from jalboot.config import Settings
from jalboot.db.models import AuditEvent
from jalboot.security import throttle
from tests.conftest import database_url
from tests.test_api import LAYLA, NOURA, PASSWORD, V1, signed_in, start

BURST = 12
OTP_LIMIT = 5
GOOD_EMAIL = "sara@jalboot.example"
OTHER_EMAIL = "khalid@jalboot.example"


@pytest.fixture
def app(tmp_path):
    return create_app(Settings(database_url=database_url(tmp_path), web_dist=tmp_path / "missing", world_scale=0.05))


@pytest.fixture
def gap_after_check(monkeypatch):
    """Widens the moment between reading a limit and counting against it. Requests alone
    rarely land in that gap on one machine, so the race would pass by luck. Code that
    holds a lock across the gap is not affected, however long it is."""
    real = throttle.is_blocked

    def slow(*args):
        blocked = real(*args)
        time.sleep(0.03)
        return blocked

    monkeypatch.setattr(throttle, "is_blocked", slow)


def audit_count(app, action):
    with app.state.runtime.sessions() as session:
        return session.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.action == action))


def burst(app, path, bodies, headers=None, client="127.0.0.1"):
    """Sends every request together and returns their status codes."""
    transport = httpx.ASGITransport(app=app, client=(client, 50000))

    async def run():
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http:
            responses = await asyncio.gather(*(http.post(path, json=body, headers=headers) for body in bodies))
            return [response.status_code for response in responses]

    return asyncio.run(run())


def stranger(number):
    """A valid number with no account, so a test can open more checks than one number allows."""
    return f"+974555{number:05d}"


def open_check(app, phone=LAYLA):
    with TestClient(app, base_url="http://testserver") as client:
        cid, auth = start(client)
        sent = client.post(f"{V1}/conversations/{cid}/verify/start", headers=auth, json={"phone": phone}).json()
    return cid, auth, sent["simulatedCode"]


def wrong(code, offset=1):
    return f"{(int(code) + offset) % 1_000_000:06d}"


def test_a_burst_of_guesses_only_checks_the_allowed_number(app, gap_after_check):
    cid, auth, code = open_check(app)
    path = f"{V1}/conversations/{cid}/verify/confirm"
    statuses = burst(app, path, [{"code": wrong(code)}] * BURST, auth)
    assert audit_count(app, "identity.failed") == OTP_LIMIT
    assert statuses.count(400) == OTP_LIMIT - 1
    assert statuses.count(429) == BURST - OTP_LIMIT + 1


def test_the_right_code_in_a_burst_past_the_limit_is_refused_unread(app, gap_after_check):
    cid, auth, code = open_check(app)
    path = f"{V1}/conversations/{cid}/verify/confirm"
    burst(app, path, [{"code": wrong(code)}] * BURST, auth)
    assert burst(app, path, [{"code": code}], auth) == [429]
    assert audit_count(app, "identity.verified") == 0


def test_a_refused_guess_is_refused_before_it_is_compared(app, monkeypatch):
    cid, auth, code = open_check(app)
    path = f"{V1}/conversations/{cid}/verify/confirm"
    burst(app, path, [{"code": wrong(code)}] * OTP_LIMIT, auth)
    compared = []
    real = identity.hmac.compare_digest
    monkeypatch.setattr(identity.hmac, "compare_digest", lambda a, b: compared.append(1) or real(a, b))
    assert burst(app, path, [{"code": wrong(code)}], auth) == [429]
    assert compared == []


def test_guessing_across_many_numbers_from_one_client_is_limited(app):
    """Each number has its own lock, so one client could otherwise spread its guesses."""
    limit = identity.CONFIRM_CLIENT_LIMIT
    checks = [open_check(app, stranger(number)) for number in range(limit // (OTP_LIMIT - 1) + 1)]
    statuses = []
    for cid, auth, code in checks:
        path = f"{V1}/conversations/{cid}/verify/confirm"
        for offset in range(1, OTP_LIMIT):
            statuses.append(burst(app, path, [{"code": wrong(code, offset)}], auth)[0])
    assert 429 in statuses
    assert audit_count(app, "identity.failed") == limit


def test_the_client_limit_does_not_touch_other_clients(app):
    limit = identity.CONFIRM_CLIENT_LIMIT
    checks = [open_check(app, stranger(number)) for number in range(limit // (OTP_LIMIT - 1) + 2)]
    for cid, auth, code in checks[:-1]:
        path = f"{V1}/conversations/{cid}/verify/confirm"
        for offset in range(1, OTP_LIMIT):
            burst(app, path, [{"code": wrong(code, offset)}], auth)
    cid, auth, code = checks[-1]
    path = f"{V1}/conversations/{cid}/verify/confirm"
    assert burst(app, path, [{"code": wrong(code)}], auth, client="198.51.100.7") == [400]


def test_verifying_your_own_number_does_not_reset_the_client_limit(app):
    """Otherwise a client with one real account could clear its count between guesses."""
    cid, auth, code = open_check(app)
    path = f"{V1}/conversations/{cid}/verify/confirm"
    burst(app, path, [{"code": wrong(code)}] * 3, auth)
    client_key = identity._key(app.state.runtime.settings.secret_key, "otp-confirm-client", "127.0.0.1")
    with app.state.runtime.sessions() as session:
        before = session.get(throttle.LoginThrottle, client_key).failures
    assert burst(app, path, [{"code": code}], auth) == [200]
    with app.state.runtime.sessions() as session:
        assert session.get(throttle.LoginThrottle, client_key).failures == before


def test_a_burst_of_code_requests_cannot_pass_the_send_limit(app, gap_after_check):
    with TestClient(app, base_url="http://testserver") as client:
        cid, auth = start(client)
    statuses = burst(app, f"{V1}/conversations/{cid}/verify/start", [{"phone": NOURA}] * BURST, auth)
    assert statuses.count(200) == identity.SEND_LIMIT
    assert statuses.count(429) == BURST - identity.SEND_LIMIT


def login(email, password="nope"):
    return {"email": email, "password": password}


def test_a_burst_of_login_guesses_only_checks_the_allowed_number(app, gap_after_check):
    statuses = burst(app, f"{V1}/desk/session", [login(GOOD_EMAIL)] * BURST)
    assert audit_count(app, "desk.login_failed") == throttle.MAX_FAILURES
    assert statuses.count(401) == throttle.MAX_FAILURES
    assert statuses.count(429) == BURST - throttle.MAX_FAILURES


def test_failed_logins_do_not_lock_out_a_colleague_at_the_same_address(app):
    for _ in range(throttle.MAX_FAILURES):
        burst(app, f"{V1}/desk/session", [login(GOOD_EMAIL)])
    assert burst(app, f"{V1}/desk/session", [login(GOOD_EMAIL, PASSWORD)]) == [429]
    assert burst(app, f"{V1}/desk/session", [login(OTHER_EMAIL, PASSWORD)]) == [200]


def test_failed_logins_from_one_address_do_not_lock_the_account_everywhere(app):
    for _ in range(throttle.MAX_FAILURES):
        burst(app, f"{V1}/desk/session", [login(GOOD_EMAIL)], client="198.51.100.7")
    assert burst(app, f"{V1}/desk/session", [login(GOOD_EMAIL, PASSWORD)]) == [200]


def test_trying_many_accounts_from_one_address_is_still_limited(app):
    from jalboot.api.app import LOGIN_CLIENT_LIMIT

    statuses = []
    for number in range(LOGIN_CLIENT_LIMIT + 1):
        statuses.extend(burst(app, f"{V1}/desk/session", [login(f"nobody{number}@jalboot.example")]))
    assert statuses[:LOGIN_CLIENT_LIMIT] == [401] * LOGIN_CLIENT_LIMIT
    assert statuses[-1] == 429


def test_a_good_login_clears_its_own_count(app):
    with TestClient(app, base_url="http://testserver") as client:
        for _ in range(throttle.MAX_FAILURES - 1):
            client.post(f"{V1}/desk/session", json=login(GOOD_EMAIL))
        signed_in(client)
        for _ in range(throttle.MAX_FAILURES - 1):
            assert client.post(f"{V1}/desk/session", json=login(GOOD_EMAIL)).status_code == 401
