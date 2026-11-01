"""Removes phone numbers and one-time codes from customer text.

ACC-01 says a code is never entered in chat, and the web page locks the chat box
during the identity check, but a page can be bypassed. So the server applies the same
rule itself: this runs before a message is stored or reaches a model. It also runs on
free text the model writes into a ticket or a handoff summary.
"""

from __future__ import annotations

import re
from typing import Callable

from jalboot.text.normalize import DIGITS, strip_invisible

PHONE = re.compile(r"(?<![\w-])\+?\d(?:[\s-]?\d){7,14}(?![\w-])")
CODE = re.compile(r"(?<![\w-])\d{6}(?![\w-])")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
CARD = re.compile(r"(?<![\w-])(?:\d[ -]?){13,19}(?![\w-])")
DIGIT_RUN = re.compile(r"\d(?:[\s._,/-]*\d)*")
CODE_LENGTH = 6
PHONE_MARK = "[phone removed]"
CODE_MARK = "[code removed]"
CARD_MARK = "[card number removed]"
EMAIL_MARK = "[email removed]"


def _without_code(text: str, is_code: Callable[[str], bool]) -> str:
    """Removes the open code from any run of digits, whatever separates them or sits
    beside them. Comparing with the real code is what makes this safe to apply so
    widely: a pattern this loose would also remove order numbers."""

    def clean(match: re.Match[str]) -> str:
        run = match.group()
        places = [index for index, character in enumerate(run) if character.isdigit()]
        digits = "".join(run[index] for index in places)
        for start in range(len(digits) - CODE_LENGTH + 1):
            if is_code(digits[start:start + CODE_LENGTH]):
                before = run[:places[start]]
                after = run[places[start + CODE_LENGTH - 1] + 1:]
                return before + CODE_MARK + DIGIT_RUN.sub(clean, after)
        return run

    return DIGIT_RUN.sub(clean, text)


def redact(
    text: str, *, code_expected: bool = False, is_code: Callable[[str], bool] | None = None,
) -> tuple[str, list[str]]:
    """Returns the cleaned text and what was removed. A bare six digit number is only
    treated as a code while an identity check is open, because it could otherwise be
    an order number. is_code recognises the open code, so it is found however it was
    typed: 748 350, 7-4-8-3-5-0 or otp748350."""
    # Arabic-Indic digits and zero width marks would otherwise slip past the patterns.
    probe = strip_invisible(text).translate(DIGITS)
    removed: list[str] = []
    if is_code is not None:
        without = _without_code(probe, is_code)
        if without != probe:
            probe = without
            removed.append("code")
    if CARD.search(probe):
        probe = CARD.sub(CARD_MARK, probe)
        removed.append("card")
    if PHONE.search(probe):
        probe = PHONE.sub(PHONE_MARK, probe)
        removed.append("phone")
    if EMAIL.search(probe):
        probe = EMAIL.sub(EMAIL_MARK, probe)
        removed.append("email")
    if code_expected and CODE.search(probe):
        probe = CODE.sub(CODE_MARK, probe)
        if "code" not in removed:
            removed.append("code")
    return (probe if removed else text), removed
