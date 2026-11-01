"""The HTTP contract in web/API.md, through the real app with the mock planner.

These run through a test client, which is not a browser. The browser flows are in
e2e/, because a passing test client proves nothing about cookies, CORS or forms.
"""

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from jalboot import audit
from jalboot.api.app import COOKIE, create_app
from jalboot.config import Settings
from jalboot.db.models import Message, Refund, WebSession
from jalboot.world.demo import DEMO_PHONES

V1 = "/api/v1"
PASSWORD = "jalboot-local-demo"
LAYLA = "+97401001001"
NOURA = "+97401001002"
ALLOWED = "http://allowed.test"


@pytest.fixture
def client(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{(tmp_path / 't.sqlite3').as_posix()}",
        allowed_origins=(ALLOWED,),
        web_dist=tmp_path / "missing",
        world_scale=0.05,
    )
    with TestClient(create_app(settings), base_url="http://testserver") as test_client:
        yield test_client


def runtime(client):
    return client.app.state.runtime


def events(response):
    """Parses a finished SSE body into (name, data) pairs."""
    found = []
    for block in response.text.split("\n\n"):
        name = next((line[7:] for line in block.split("\n") if line.startswith("event: ")), None)
        data = next((line[6:] for line in block.split("\n") if line.startswith("data: ")), None)
        if name:
            found.append((name, json.loads(data)))
    return found


def names(response):
    return [name for name, _ in events(response)]


def find(response, name):
    return next(data for found, data in events(response) if found == name)


def reply_text(response):
    return "".join(data["delta"] for found, data in events(response) if found == "text.delta")


def start(client, locale="en"):
    body = client.post(f"{V1}/conversations", json={"locale": locale}).json()
    return body["id"], {"Authorization": f"Bearer {body['token']}"}


def say(client, cid, auth, text, client_id="c1", locale="en"):
    return client.post(
        f"{V1}/conversations/{cid}/messages", headers=auth,
        json={"clientMessageId": client_id, "text": text, "locale": locale},
    )


def verify(client, cid, auth, phone=LAYLA):
    sent = client.post(f"{V1}/conversations/{cid}/verify/start", headers=auth, json={"phone": phone}).json()
    confirmed = client.post(f"{V1}/conversations/{cid}/verify/confirm", headers=auth, json={"code": sent["simulatedCode"]})
    assert confirmed.status_code == 200
    return confirmed.json()


def signed_in(client, email="sara@jalboot.example"):
    response = client.post(f"{V1}/desk/session", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200
    return {"X-CSRF-Token": response.json()["csrfToken"]}


def test_routes_are_really_registered(client):
    assert client.get(f"{V1}/health").json() == {"status": "ok", "assistant": "mock", "data": "simulated"}


def test_policy_comes_from_the_rules_file(client):
    body = client.get(f"{V1}/policy").json()
    rules = json.loads(Path("knowledge/rules.json").read_text(encoding="utf-8"))
    assert body["refund"]["automatedLimitQar"] == rules["refunds"]["approval_limits_qar"]["automated"]
    assert body["policyVersion"] == rules["meta"]["policy_version"]


def test_every_response_carries_the_browser_protections(client):
    headers = client.get(f"{V1}/health").headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert "default-src 'self'" in headers["content-security-policy"]
    assert headers["x-data-notice"] == "simulated"
    assert headers["cache-control"] == "no-store"


def test_a_message_needs_the_conversation_token(client):
    cid, _ = start(client)
    assert say(client, cid, {}, "hello").status_code == 401
    assert say(client, cid, {"Authorization": "Bearer nope"}, "hello").status_code == 401


def test_one_conversations_token_cannot_read_another(client):
    cid, _ = start(client)
    _, other = start(client)
    assert say(client, cid, other, "hello").status_code == 401


def test_errors_use_the_envelope_and_the_request_language(client):
    response = client.post(
        f"{V1}/conversations/x/messages", headers={"Accept-Language": "ar"},
        json={"clientMessageId": "a", "text": "hi", "locale": "ar"},
    )
    assert response.json()["error"]["code"] == "unauthorized"
    assert re.search("[؀-ۿ]", response.json()["error"]["message"])


def test_a_general_question_needs_no_identity_and_cites_its_source(client):
    cid, auth = start(client)
    response = say(client, cid, auth, "how much is the cancellation charge for a food order")
    assert response.headers["content-type"].startswith("text/event-stream")
    assert names(response)[0] == "message.start"
    assert names(response)[-1] == "message.end"
    assert "citation" in names(response)
    citation = find(response, "citation")
    assert {"n", "sourceId", "title", "section", "excerpt", "updatedAt"} <= set(citation["citation"])
    assert names(response).index("citation") < names(response).index("text.delta")


def test_order_question_stops_for_identity_then_resumes_with_the_same_message(client):
    cid, auth = start(client)
    first = say(client, cid, auth, "where is my order JB-700101")
    assert "identity.required" in names(first)
    assert find(first, "message.end") == {"finish": "identity_required"}
    assert "order.card" not in names(first)
    assert verify(client, cid, auth) == {"verified": True, "customerName": "Layla"}

    second = say(client, cid, auth, "where is my order JB-700101")
    assert find(second, "message.end") == {"finish": "complete"}
    assert find(second, "order.card")["order"]["id"] == "JB-700101"
    assert find(second, "tool.start")["label"] == "Checking your order"
    assert find(second, "tool.end")["status"] == "ok"
    with runtime(client).sessions() as session:
        rows = session.scalars(select(Message).where(Message.conversation_id == cid, Message.role == "customer")).all()
    assert len(rows) == 1


def test_a_repeat_of_a_finished_message_is_refused(client):
    cid, auth = start(client)
    say(client, cid, auth, "how do refunds work")
    response = say(client, cid, auth, "how do refunds work")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "duplicate_message"


def test_verify_start_looks_the_same_for_an_unknown_phone(client):
    cid, auth = start(client)
    known = client.post(f"{V1}/conversations/{cid}/verify/start", headers=auth, json={"phone": LAYLA}).json()
    unknown = client.post(f"{V1}/conversations/{cid}/verify/start", headers=auth, json={"phone": "+97409998888"}).json()
    assert set(known) == set(unknown)
    assert known["status"] == unknown["status"]
    assert known["expiresInSeconds"] == unknown["expiresInSeconds"]


def test_a_code_for_an_unknown_phone_never_verifies(client):
    cid, auth = start(client)
    sent = client.post(f"{V1}/conversations/{cid}/verify/start", headers=auth, json={"phone": "+97409998888"}).json()
    response = client.post(f"{V1}/conversations/{cid}/verify/confirm", headers=auth, json={"code": sent["simulatedCode"]})
    assert response.status_code == 400


def test_a_bad_phone_is_refused(client):
    cid, auth = start(client)
    response = client.post(f"{V1}/conversations/{cid}/verify/start", headers=auth, json={"phone": "12345"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_phone"


def test_a_wrong_code_reports_attempts_left(client):
    cid, auth = start(client)
    client.post(f"{V1}/conversations/{cid}/verify/start", headers=auth, json={"phone": LAYLA})
    response = client.post(f"{V1}/conversations/{cid}/verify/confirm", headers=auth, json={"code": "000000"})
    assert response.status_code == 400
    assert response.json()["error"]["attemptsLeft"] == 4


def test_failed_codes_lock_the_phone_even_from_a_new_conversation(client):
    cid, auth = start(client)
    client.post(f"{V1}/conversations/{cid}/verify/start", headers=auth, json={"phone": LAYLA})
    for _ in range(4):
        client.post(f"{V1}/conversations/{cid}/verify/confirm", headers=auth, json={"code": "000000"})
    locked = client.post(f"{V1}/conversations/{cid}/verify/confirm", headers=auth, json={"code": "000000"})
    assert locked.status_code == 429
    assert int(locked.headers["retry-after"]) > 0
    other, other_auth = start(client)
    again = client.post(f"{V1}/conversations/{other}/verify/start", headers=other_auth, json={"phone": LAYLA})
    assert again.status_code == 429


def test_an_identity_code_typed_in_chat_is_not_stored_or_passed_on(client):
    cid, auth = start(client)
    sent = client.post(f"{V1}/conversations/{cid}/verify/start", headers=auth, json={"phone": LAYLA}).json()
    response = say(client, cid, auth, f"my code is {sent['simulatedCode']}")
    assert "secure form" in reply_text(response)
    with runtime(client).sessions() as session:
        stored = " ".join(session.scalars(select(Message.text).where(Message.conversation_id == cid)).all())
    assert sent["simulatedCode"] not in stored
    assert "[code removed]" in stored


def test_a_phone_number_typed_in_chat_is_not_stored(client):
    cid, auth = start(client)
    say(client, cid, auth, "my number is +974 5555 1234, what are the delivery fees")
    with runtime(client).sessions() as session:
        stored = " ".join(session.scalars(select(Message.text).where(Message.conversation_id == cid)).all())
    assert "5555" not in stored


def test_no_phone_or_code_reaches_the_audit_log(client):
    cid, auth = start(client)
    sent = client.post(f"{V1}/conversations/{cid}/verify/start", headers=auth, json={"phone": LAYLA}).json()
    client.post(f"{V1}/conversations/{cid}/verify/confirm", headers=auth, json={"code": sent["simulatedCode"]})
    signed_in(client)
    body = str(client.get(f"{V1}/desk/audit").json())
    assert "identity.verified" in body
    assert sent["simulatedCode"] not in body
    assert "0100" not in body


def test_a_refund_runs_end_to_end(client):
    cid, auth = start(client)
    verify(client, cid, auth)
    response = say(client, cid, auth, "the karak tea was missing from JB-700102")
    assert find(response, "refund.update")["refund"]["status"] == "auto_approved"
    assert "refunded" in reply_text(response)
    with runtime(client).sessions() as session:
        assert session.scalar(select(Refund).where(Refund.order_id == "JB-700102")) is not None


def test_a_large_refund_waits_for_a_person_then_pays(client):
    cid, auth = start(client)
    verify(client, cid, auth)
    response = say(client, cid, auth, "the grilled hammour was wrong on JB-700103")
    summary = find(response, "refund.update")["refund"]
    assert summary["status"] == "pending"
    with runtime(client).sessions() as session:
        assert session.scalar(select(Refund).where(Refund.order_id == "JB-700103")) is None

    csrf = signed_in(client)
    refunds = client.get(f"{V1}/desk/refunds").json()["refunds"]
    refund = next(row for row in refunds if row["id"] == summary["id"])
    assert refund["canDecide"] is True
    assert refund["requiredRole"] == "agent"

    decided = client.post(
        f"{V1}/desk/refunds/{refund['id']}/decision", headers=csrf,
        json={"action": "approve", "note": "", "version": refund["version"]},
    )
    assert decided.status_code == 200
    assert decided.json()["status"] == "approved"
    with runtime(client).sessions() as session:
        assert session.scalar(select(Refund).where(Refund.order_id == "JB-700103")) is not None


def test_deciding_twice_is_refused(client):
    cid, auth = start(client)
    verify(client, cid, auth)
    summary = find(say(client, cid, auth, "the grilled hammour was wrong on JB-700103"), "refund.update")["refund"]
    csrf = signed_in(client)
    body = {"action": "approve", "note": "", "version": 1}
    assert client.post(f"{V1}/desk/refunds/{summary['id']}/decision", headers=csrf, json=body).status_code == 200
    second = client.post(f"{V1}/desk/refunds/{summary['id']}/decision", headers=csrf, json=body)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "refund_already_decided"


def test_a_rejection_needs_a_reason(client):
    cid, auth = start(client)
    verify(client, cid, auth)
    summary = find(say(client, cid, auth, "the grilled hammour was wrong on JB-700103"), "refund.update")["refund"]
    csrf = signed_in(client)
    response = client.post(
        f"{V1}/desk/refunds/{summary['id']}/decision", headers=csrf,
        json={"action": "reject", "note": "no", "version": 1},
    )
    assert response.status_code == 422


def test_login_cookie_is_http_only_and_lax_and_the_body_holds_no_session(client):
    response = client.post(f"{V1}/desk/session", json={"email": "sara@jalboot.example", "password": PASSWORD})
    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{COOKIE}=")
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "token" not in response.json()


def test_the_cookie_value_is_not_stored_in_the_database(client):
    signed_in(client)
    value = client.cookies.get(COOKIE)
    with runtime(client).sessions() as session:
        assert value not in session.scalars(select(WebSession.token_hash)).all()


def test_wrong_password_and_unknown_email_look_the_same(client):
    wrong = client.post(f"{V1}/desk/session", json={"email": "sara@jalboot.example", "password": "nope"})
    unknown = client.post(f"{V1}/desk/session", json={"email": "ghost@jalboot.example", "password": "nope"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_repeated_login_failures_are_blocked(client):
    for _ in range(5):
        client.post(f"{V1}/desk/session", json={"email": "sara@jalboot.example", "password": "nope"})
    response = client.post(f"{V1}/desk/session", json={"email": "sara@jalboot.example", "password": PASSWORD})
    assert response.status_code == 429


def test_desk_pages_need_a_session(client):
    for path in ("me", "summary", "conversations", "refunds", "audit", "metrics/quality"):
        assert client.get(f"{V1}/desk/{path}").status_code == 401


def test_a_customer_token_opens_nothing_on_the_desk(client):
    _, auth = start(client)
    assert client.get(f"{V1}/desk/refunds", headers=auth).status_code == 401


def test_a_desk_write_without_the_csrf_token_is_refused(client):
    signed_in(client)
    response = client.post(f"{V1}/desk/logout")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"


def test_a_desk_write_with_a_wrong_csrf_token_is_refused(client):
    signed_in(client)
    assert client.post(f"{V1}/desk/logout", headers={"X-CSRF-Token": "wrong"}).status_code == 403


def test_me_restores_the_csrf_token_after_a_refresh(client):
    csrf = signed_in(client)
    body = client.get(f"{V1}/desk/me").json()
    assert body["csrfToken"] == csrf["X-CSRF-Token"]
    assert body["agent"]["role"] == "agent"


def test_logout_ends_the_session(client):
    csrf = signed_in(client)
    value = client.cookies.get(COOKIE)
    assert client.post(f"{V1}/desk/logout", headers=csrf).status_code == 204
    client.cookies.set(COOKIE, value)
    assert client.get(f"{V1}/desk/me").status_code == 401


def test_an_unlisted_origin_cannot_write_even_with_a_session(client):
    csrf = signed_in(client)
    response = client.post(f"{V1}/desk/logout", headers={**csrf, "Origin": "http://evil.test"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "origin_not_allowed"


def test_a_listed_origin_can_write(client):
    csrf = signed_in(client)
    assert client.post(f"{V1}/desk/logout", headers={**csrf, "Origin": ALLOWED}).status_code == 204


def test_same_origin_writes_are_allowed(client):
    assert client.post(
        f"{V1}/conversations", json={"locale": "en"}, headers={"Origin": "http://testserver"},
    ).status_code == 201


def test_a_browser_write_from_another_site_with_no_origin_is_refused(client):
    response = client.post(f"{V1}/conversations", json={"locale": "en"}, headers={"Sec-Fetch-Site": "cross-site"})
    assert response.status_code == 403


def test_preflight_allows_the_listed_origin_and_the_csrf_header(client):
    response = client.options(f"{V1}/desk/logout", headers={
        "Origin": ALLOWED, "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "x-csrf-token",
    })
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED
    assert response.headers["access-control-allow-credentials"] == "true"


def test_preflight_gives_an_unlisted_origin_nothing(client):
    response = client.options(f"{V1}/desk/logout", headers={
        "Origin": "http://evil.test", "Access-Control-Request-Method": "POST",
    })
    assert "access-control-allow-origin" not in response.headers


def test_handoff_stops_the_bot_and_forwards_messages(client):
    cid, auth = start(client)
    handoff = client.post(f"{V1}/conversations/{cid}/handoff", headers=auth, json={"reason": "customer_request"})
    assert handoff.json()["status"] == "queued"
    response = say(client, cid, auth, "hello, is anyone there?")
    assert names(response) == ["message.start", "message.end"]
    assert find(response, "message.end") == {"finish": "forwarded"}


def test_a_person_can_claim_and_reply(client):
    cid, auth = start(client)
    say(client, cid, auth, "I want to talk to a human")
    csrf = signed_in(client)
    claimed = client.post(f"{V1}/desk/conversations/{cid}/claim", headers=csrf)
    assert claimed.json()["state"] == "agent"
    assert client.post(f"{V1}/desk/conversations/{cid}/reply", headers=csrf, json={"text": "Hello"}).status_code == 204
    detail = client.get(f"{V1}/desk/conversations/{cid}").json()
    assert [row["author"] for row in detail["transcript"]][-1] == "agent"
    assert detail["summary"].startswith("Reason: customer_request")


def test_desk_lists_show_arabic_labels_when_asked(client):
    signed_in(client)
    issues = client.get(f"{V1}/desk/metrics/top-issues?windowDays=30", headers={"Accept-Language": "ar"}).json()
    assert issues["issues"]
    assert re.search("[؀-ۿ]", issues["issues"][0]["label"])


def test_quality_report_has_the_documented_shape(client):
    signed_in(client)
    report = client.get(f"{V1}/desk/metrics/quality?windowDays=7").json()
    assert report["windowDays"] == 7
    assert len(report["series"]) == 7
    assert {"id", "label", "value", "unit", "delta", "higherIsBetter", "trend"} <= set(report["hero"])


def test_a_bad_window_is_refused(client):
    signed_in(client)
    assert client.get(f"{V1}/desk/metrics/quality?windowDays=9").status_code == 422


def test_audit_filters_and_paging(client):
    cid, auth = start(client)
    verify(client, cid, auth)
    say(client, cid, auth, "where is JB-700201")
    signed_in(client)
    guardrail = client.get(f"{V1}/desk/audit?filter=guardrail").json()["entries"]
    assert guardrail and all(row["action"] == "guardrail.blocked" for row in guardrail)
    bot = client.get(f"{V1}/desk/audit?filter=bot").json()["entries"]
    assert all(row["action"] != "guardrail.blocked" for row in bot)


def test_the_audit_chain_is_intact_after_a_full_flow(client):
    cid, auth = start(client)
    verify(client, cid, auth)
    say(client, cid, auth, "the karak tea was missing from JB-700102")
    signed_in(client)
    assert client.get(f"{V1}/desk/audit/verify").json() == {"intact": True, "firstBadEntry": None}
    with runtime(client).sessions() as session:
        assert audit.verify_chain(session) == (True, None)


def test_an_arabic_conversation_gets_arabic_labels_and_text(client):
    cid, auth = start(client, "ar")
    verify(client, cid, auth, NOURA)
    response = say(client, cid, auth, "وين طلبي JB-700201؟", locale="ar")
    assert re.search("[؀-ۿ]", find(response, "tool.start")["label"])
    assert re.search("[؀-ۿ]", reply_text(response))
    card = find(response, "order.card")["order"]
    assert re.search("[؀-ۿ]", card["items"][0]["name"])


def test_demo_phones_match_the_verify_format():
    assert DEMO_PHONES["C-1001"].replace(" ", "") == LAYLA
