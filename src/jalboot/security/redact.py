"""Removes phone numbers and one-time codes from customer text.

ACC-01 says a code is never entered in chat, and the web page locks the chat box
during the identity check, but a page can be bypassed. So the server applies the same
rule itself: this runs before a message is stored or reaches a model. It also runs on
free text the model writes into a ticket or a handoff summary.
"""

from __future__ import annotations

import re

from jalboot.text.normalize import DIGITS, strip_invisible

PHONE = re.compile(r"(?<![\w-])\+?\d(?:[\s-]?\d){7,14}(?![\w-])")
CODE = re.compile(r"(?<![\w-])\d{6}(?![\w-])")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
CARD = re.compile(r"(?<![\w-])(?:\d[ -]?){13,19}(?![\w-])")
PHONE_MARK = "[phone removed]"
CODE_MARK = "[code removed]"
CARD_MARK = "[card number removed]"
EMAIL_MARK = "[email removed]"


def redact(text: str, *, code_expected: bool = False) -> tuple[str, list[str]]:
    """Returns the cleaned text and what was removed. A bare six digit number is only
    treated as a code while an identity check is open, because it could otherwise be
    an order number."""
    # Arabic-Indic digits and zero width marks would otherwise slip past the patterns.
    probe = strip_invisible(text).translate(DIGITS)
    removed: list[str] = []
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
        removed.append("code")
    return (probe if removed else text), removed
