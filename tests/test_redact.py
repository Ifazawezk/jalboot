"""A code typed into the chat must not be stored or reach a model, however it was typed.

While a check is open the digits in a message are compared with the open code, which
can be strict about separators without touching order numbers or other digits.
"""

import pytest

from jalboot.security.redact import CODE_MARK, redact
from tests.test_api import LAYLA, V1, client, find, reply_text, runtime, say, start  # noqa: F401
from jalboot.db.models import Message
from sqlalchemy import select

CODE = "748350"


def is_code(digits):
    return digits == CODE


@pytest.mark.parametrize("typed", [
    "748 350", "748-350", "74 83 50", "7 4 8 3 5 0", "7.4.8.3.5.0", "748_350", "otp748350", "code_748350",
    "748350abc", "my code is 748 350 thanks", "٧٤٨ ٣٥٠", "7 4 8\n3 5 0",
])
def test_the_open_code_is_removed_however_it_is_typed(typed):
    clean, removed = redact(typed, code_expected=True, is_code=is_code)
    assert removed == ["code"]
    assert CODE_MARK in clean
    assert not any(character.isdigit() for character in clean)


def test_an_order_number_beside_the_code_is_kept():
    clean, removed = redact("JB-700102 748 350", code_expected=True, is_code=is_code)
    assert clean == f"JB-700102 {CODE_MARK}"
    assert removed == ["code"]


def test_the_code_is_removed_each_time_it_appears():
    clean, _ = redact("748 350 and again 7-4-8-3-5-0", code_expected=True, is_code=is_code)
    assert clean == f"{CODE_MARK} and again {CODE_MARK}"


def test_digits_that_are_not_the_code_are_left_alone():
    for text in ("JB-700102", "order 123 456 was late", "I paid 748 riyals"):
        assert redact(text, code_expected=True, is_code=is_code) == (text, [])


def test_with_no_check_open_nothing_is_compared():
    assert redact("748 350") == ("748 350", [])


def test_a_code_with_a_space_typed_in_chat_is_not_stored_or_passed_on(client):  # noqa: F811
    cid, auth = start(client)
    sent = client.post(f"{V1}/conversations/{cid}/verify/start", headers=auth, json={"phone": LAYLA}).json()
    code = sent["simulatedCode"]
    response = say(client, cid, auth, f"my code is {code[:3]} {code[3:]}")
    assert find(response, "message.end") == {"finish": "complete"}
    assert "secure form" in reply_text(response)
    with runtime(client).sessions() as session:
        stored = session.scalars(select(Message.text).where(Message.conversation_id == cid)).all()
    assert all(code[:3] not in text and code[3:] not in text for text in stored)
