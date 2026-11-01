"""Attempts only add up inside a window, so a limit means that many in a short time,
not that many ever. Otherwise a customer who verifies once a month gets blocked."""

from datetime import timedelta

from sqlalchemy import text
from sqlalchemy.schema import CreateTable

from jalboot.db.base import create_schema, make_engine, make_session_factory
from jalboot.db.models import Conversation, Driver, LoginThrottle
from jalboot.security import throttle
from tests.conftest import ANCHOR

KEY = "some-key"


def attempt(session, at, limit=5, minutes=15):
    throttle.note_failure(session, KEY, at, limit, minutes)
    session.commit()


def test_attempts_spread_over_months_never_block(db):
    moments = [ANCHOR + timedelta(days=30 * month) for month in range(12)]
    for moment in moments:
        attempt(db, moment)
    assert not throttle.is_blocked(db, KEY, moments[-1] + timedelta(seconds=1))


def test_the_limit_inside_one_window_still_blocks(db):
    for minute in range(5):
        attempt(db, ANCHOR + timedelta(minutes=minute))
    assert throttle.is_blocked(db, KEY, ANCHOR + timedelta(minutes=5))


def test_a_block_ends_and_counting_starts_again(db):
    for minute in range(5):
        attempt(db, ANCHOR + timedelta(minutes=minute))
    after = ANCHOR + timedelta(minutes=4 + 15)
    assert not throttle.is_blocked(db, KEY, after)
    attempt(db, after)
    assert db.get(LoginThrottle, KEY).failures == 1


def test_a_window_runs_from_its_first_attempt(db):
    for _ in range(4):
        attempt(db, ANCHOR)
    attempt(db, ANCHOR + timedelta(minutes=14, seconds=59))
    assert throttle.is_blocked(db, KEY, ANCHOR + timedelta(minutes=15))


def test_an_attempt_after_the_window_starts_a_new_count(db):
    for _ in range(4):
        attempt(db, ANCHOR)
    attempt(db, ANCHOR + timedelta(minutes=15))
    assert not throttle.is_blocked(db, KEY, ANCHOR + timedelta(minutes=15))
    assert db.get(LoginThrottle, KEY).failures == 1


def test_a_counter_saved_before_windows_existed_starts_fresh(db):
    db.add(LoginThrottle(key=KEY, failures=4))
    db.commit()
    attempt(db, ANCHOR)
    assert not throttle.is_blocked(db, KEY, ANCHOR)
    assert db.get(LoginThrottle, KEY).failures == 1


def test_a_database_from_before_windows_existed_is_upgraded(tmp_path):
    engine = make_engine(f"sqlite:///{(tmp_path / 'old.sqlite3').as_posix()}")
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE login_throttle (key VARCHAR(64) PRIMARY KEY, failures INTEGER NOT NULL, blocked_until DATETIME)"
        ))
        connection.execute(text("INSERT INTO login_throttle (key, failures) VALUES ('some-key', 4)"))
    create_schema(engine)
    with make_session_factory(engine)() as session:
        attempt(session, ANCHOR)
        assert not throttle.is_blocked(session, KEY, ANCHOR)
    engine.dispose()


def test_upgrading_twice_changes_nothing(tmp_path):
    engine = make_engine(f"sqlite:///{(tmp_path / 'new.sqlite3').as_posix()}")
    create_schema(engine)
    create_schema(engine)
    engine.dispose()


def test_a_database_from_before_arabic_driver_names_is_upgraded(tmp_path):
    engine = make_engine(f"sqlite:///{(tmp_path / 'old.sqlite3').as_posix()}")
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE drivers (id VARCHAR(32) PRIMARY KEY, name VARCHAR(120) NOT NULL, "
            "vehicle VARCHAR(16) NOT NULL, zone VARCHAR(60) NOT NULL, rating FLOAT NOT NULL)"
        ))
        connection.execute(text("INSERT INTO drivers VALUES ('D-1', 'Saad Nair', 'car', 'Al Sadd', 4.5)"))
    create_schema(engine)
    with make_session_factory(engine)() as session:
        assert session.get(Driver, "D-1").name_ar == ""
    engine.dispose()


def test_a_database_with_the_removed_topic_column_can_still_add_conversations(tmp_path):
    """The old column was NOT NULL, so leaving it behind would break every new chat."""
    engine = make_engine(f"sqlite:///{(tmp_path / 'old.sqlite3').as_posix()}")
    current = str(CreateTable(Conversation.__table__).compile(engine))
    old = current.replace("PRIMARY KEY (id)", "topic VARCHAR(32) NOT NULL, PRIMARY KEY (id)")
    assert "topic" in old
    with engine.begin() as connection:
        connection.execute(text(old))
    create_schema(engine)
    with make_session_factory(engine)() as session:
        session.add(Conversation(id="cv-new", created_at=ANCHOR, updated_at=ANCHOR))
        session.commit()
    engine.dispose()
