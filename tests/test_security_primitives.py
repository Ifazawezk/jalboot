from datetime import timedelta

from sqlalchemy import select, text

from jalboot import audit
from jalboot.db.base import create_schema, make_engine, make_session_factory, utcnow
from jalboot.db.models import AuditEvent, WebSession
from jalboot.security import throttle, tokens
from jalboot.security import passwords
from jalboot.security.passwords import hash_password, verify_password

SECRET = "unit-test-secret"


def fresh():
    engine = make_engine("sqlite:///:memory:")
    create_schema(engine)
    return make_session_factory(engine)()


def add_events(session, count=3):
    with audit.serial_write(session):
        for index in range(count):
            audit.record(
                session, actor_type="bot", action="tool.called", outcome="allowed",
                detail={"n": index, "text": "مرحبا"},
            )


def test_password_round_trip():
    stored = hash_password("correct horse")
    assert verify_password("correct horse", stored)
    assert not verify_password("wrong", stored)
    assert "correct horse" not in stored


def test_a_malformed_stored_hash_fails_closed():
    assert not verify_password("x", "not-a-hash")
    assert not verify_password("x", "md5$1$1$1$a$b")


def test_session_token_is_not_stored_in_clear():
    session = fresh()
    token, row = tokens.create_session(session, SECRET, "staff")
    assert token not in row.token_hash
    assert tokens.find_session(session, SECRET, token, "staff") is row


def test_a_staff_lookup_cannot_use_a_customer_session():
    session = fresh()
    token, _ = tokens.create_session(session, SECRET, "customer")
    assert tokens.find_session(session, SECRET, token, "staff") is None


def test_an_expired_session_is_refused():
    session = fresh()
    token, row = tokens.create_session(session, SECRET, "staff")
    row.expires_at = utcnow() - timedelta(minutes=1)
    assert tokens.find_session(session, SECRET, token, "staff") is None


def test_a_session_made_with_another_secret_is_refused():
    session = fresh()
    token, _ = tokens.create_session(session, SECRET, "staff")
    assert tokens.find_session(session, "other", token, "staff") is None


def test_csrf_must_match_exactly():
    row = WebSession(csrf_token="abc")
    assert tokens.csrf_matches(row, "abc")
    assert not tokens.csrf_matches(row, "abd")
    assert not tokens.csrf_matches(row, None)
    assert not tokens.csrf_matches(row, "")


def test_login_blocks_after_repeated_failures_then_expires():
    session = fresh()
    now = utcnow()
    for _ in range(throttle.MAX_FAILURES):
        assert not throttle.is_blocked(session, "k", now)
        throttle.note_failure(session, "k", now)
    assert throttle.is_blocked(session, "k", now)
    assert not throttle.is_blocked(session, "k", now + timedelta(minutes=throttle.BLOCK_MINUTES + 1))


def test_success_clears_the_failure_count():
    session = fresh()
    now = utcnow()
    throttle.note_failure(session, "k", now)
    throttle.note_success(session, "k")
    session.flush()
    for _ in range(throttle.MAX_FAILURES - 1):
        throttle.note_failure(session, "k", now)
    assert not throttle.is_blocked(session, "k", now)


def test_audit_chain_verifies_when_untouched():
    session = fresh()
    add_events(session)
    assert audit.verify_chain(session) == (True, None)


def test_editing_a_row_breaks_the_chain_at_that_row():
    session = fresh()
    add_events(session)
    session.execute(text("UPDATE audit_events SET outcome='denied' WHERE seq=2"))
    session.commit()
    session.expire_all()
    assert audit.verify_chain(session) == (False, 2)


def test_deleting_a_row_breaks_the_chain():
    session = fresh()
    add_events(session)
    session.execute(text("DELETE FROM audit_events WHERE seq=2"))
    session.commit()
    session.expire_all()
    assert audit.verify_chain(session) == (False, 3)


def test_chain_continues_across_transactions():
    session = fresh()
    add_events(session, 2)
    add_events(session, 2)
    rows = list(session.scalars(select(AuditEvent).order_by(AuditEvent.seq)))
    assert [r.seq for r in rows] == [1, 2, 3, 4]
    assert rows[2].prev_hash == rows[1].hash
    assert audit.verify_chain(session) == (True, None)


def test_a_failed_transaction_writes_no_audit_row():
    session = fresh()
    try:
        with audit.serial_write(session):
            audit.record(session, actor_type="bot", action="x", outcome="allowed")
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    assert session.scalar(select(AuditEvent).limit(1)) is None


def test_known_limit_deleting_the_newest_audit_rows_is_not_detected():
    """The module and docs/security.md say so. If this ever fails, update them."""
    session = fresh()
    add_events(session)
    session.execute(text("DELETE FROM audit_events WHERE seq=3"))
    session.commit()
    assert audit.verify_chain(session) == (True, None)


def test_a_memory_error_from_scrypt_is_not_mistaken_for_a_wrong_password(monkeypatch):
    stored = passwords.hash_password("right")

    def out_of_memory(*_args):
        raise ValueError("memory limit exceeded")

    monkeypatch.setattr(passwords, "_derive", out_of_memory)
    try:
        passwords.verify_password("right", stored)
    except ValueError as error:
        assert "memory" in str(error)
    else:
        raise AssertionError("the error was swallowed")


def test_a_stored_value_that_cannot_be_parsed_is_still_just_a_failed_check():
    assert not passwords.verify_password("x", "scrypt$not-a-number$8$1$AAAA$AAAA")
    assert not passwords.verify_password("x", "scrypt$16384$8$1$!!!$AAAA")
