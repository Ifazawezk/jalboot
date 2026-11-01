"""Checks every reply against what really happened before a customer sees it.

A reply is free text from a model, so nothing in it can be trusted by default:
    citations   each [n] must point at a passage that was retrieved in this turn
    figures     each money amount, duration or percentage must appear in the sources,
                the tool results or the customer's own message
    claims      a reply may only say a refund, credit, address change or cancellation
                happened when a tool result in this turn shows that it did
    leaks       no system prompt text, and no phone number or email except the
                customer's own
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from jalboot.text.normalize import normalize

CITATION = re.compile(r"\[(\d{1,2})\]")
# A number followed or preceded by something that makes it a claim about the policy.
NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
FIGURE = re.compile(
    r"(?:qar|ريال|ر\.?ق)\s*(\d+(?:[.,]\d+)?)"
    r"|(\d+(?:[.,]\d+)?)\s*(?:qar|ريال|ر\.?ق|%|percent|minutes?|mins?|hours?|days?|دقيقه|دقائق|ساعه|ساعات|يوم|ايام)"
)
PHONE = re.compile(r"(?<![\w-])\+?\d[\d\s-]{7,14}\d(?![\w-])")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
ISO_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")

CLAIM_WORDS = {
    "refund": (
        "refunded", "has been refunded", "refund has been issued", "refund is issued", "issued a refund",
        "credited", "added to your wallet", "تم الاسترداد", "تم استرداد", "تم رد المبلغ", "تمت اعاده",
        "تم اضافه", "اعدنا المبلغ", "تم ارجاع", "late credit to your wallet", "اضفنا رصيد", "اعدنا رسوم التوصيل",
    ),
    "address": (
        "address has been changed", "address has been updated", "updated your address",
        "changed your address", "تم تغيير العنوان", "تم تحديث العنوان", "غيرنا العنوان",
    ),
    # No tool can arrange this, so a reply that claims it always fails.
    "redelivery": (
        "arranged a redelivery", "arranged redelivery", "redelivery is on its way", "will be redelivered",
        "رتبت اعاده التوصيل", "تم ترتيب اعاده التوصيل", "سيعاد توصيل",
    ),
    "cancel": (
        "has been cancelled", "has been canceled", "cancelled your order", "canceled your order",
        "تم الغاء", "الغينا طلبك",
    ),
}


# Models like typographic hyphens and spaces. An order number holding one cannot be
# searched or copied, and it slips past every pattern here.
LOOKALIKES = str.maketrans({
    "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-",
    "\u00a0": " ", "\u202f": " ", "\u2009": " ", "\u2007": " ",
})


def tidy_reply(reply: str) -> str:
    return reply.translate(LOOKALIKES).strip()


@dataclass
class CheckResult:
    ok: bool = True
    problems: list[str] = field(default_factory=list)
    citations: list[int] = field(default_factory=list)

    def fail(self, problem: str) -> None:
        self.ok = False
        self.problems.append(problem)


def _value(text: str) -> float | None:
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return None


def known_numbers(texts: Iterable[str]) -> set[float]:
    found: set[float] = set()
    for text in texts:
        for match in NUMBER.findall(normalize(text)):
            value = _value(match)
            if value is not None:
                found.add(value)
    return found


def figures_in(reply: str) -> list[float]:
    """The numbers a reply states as money, durations or percentages."""
    out = []
    for first, second in FIGURE.findall(normalize(reply)):
        value = _value(first or second)
        if value is not None:
            out.append(value)
    return out


def check_citations(reply: str, source_count: int, result: CheckResult) -> None:
    seen: list[int] = []
    for match in CITATION.findall(reply):
        number = int(match)
        if number < 1 or number > source_count:
            result.fail(f"citation [{number}] does not match a retrieved passage")
        elif number not in seen:
            seen.append(number)
    result.citations = seen


UNSURE_WORDS = tuple(normalize(word) for word in (
    "not sure", "don't know", "do not know", "no information", "cannot find", "can't find", "ticket", "a person",
    "لست متاكد", "لا اعرف", "ليس لدي", "لا املك", "تذكره", "موظف",
))


def check_cited(reply: str, source_count: int, used_tools: bool, result: CheckResult) -> None:
    """An answer drawn from the policy has to say where it came from. A short greeting,
    a reply built on tool results and an honest "I do not know" do not need a source."""
    if used_tools or not source_count or result.citations:
        return
    folded = normalize(reply)
    if any(word in folded for word in UNSURE_WORDS):
        return
    if re.search(r"\d", folded) or len(folded) > 120:
        result.fail("the answer does not cite its source with a marker such as [1]")


def check_figures(reply: str, evidence: Sequence[str], result: CheckResult) -> None:
    allowed = known_numbers(evidence)
    for value in figures_in(reply):
        if value not in allowed:
            result.fail(f"figure {value:g} is not in the sources or tool results")


def check_claims(reply: str, done: set[str], result: CheckResult) -> None:
    folded = normalize(reply)
    for action, phrases in CLAIM_WORDS.items():
        if action in done:
            continue
        for phrase in phrases:
            if normalize(phrase) in folded:
                result.fail(f"reply claims {action} but no tool result shows it")
                break


def check_leaks(
    reply: str, allowed_contacts: Iterable[str], system_prompt: str, canary: str, result: CheckResult
) -> None:
    if canary and canary in reply:
        result.fail("reply contains the system prompt marker")
    folded_prompt = normalize(system_prompt)
    words = normalize(reply).split()
    for start in range(0, max(len(words) - 11, 0)):
        if " ".join(words[start:start + 12]) in folded_prompt:
            result.fail("reply repeats the system prompt")
            break
    digits_allowed = {re.sub(r"\D", "", contact) for contact in allowed_contacts if contact}
    # A date such as 2026-09-30 has the shape of a phone number.
    for match in PHONE.findall(ISO_DATE.sub(" ", reply)):
        digits = re.sub(r"\D", "", match)
        if len(digits) >= 8 and digits not in digits_allowed and not reply_is_order_id(match):
            result.fail("reply contains a phone number that is not the customer's")
            break
    lowered = {contact.lower() for contact in allowed_contacts if contact}
    for match in EMAIL.findall(reply):
        if match.lower() not in lowered:
            result.fail("reply contains an email address that is not the customer's")
            break


def reply_is_order_id(text: str) -> bool:
    return text.strip().startswith(("JB-", "Q-"))


def check_reply(
    reply: str,
    *,
    source_count: int,
    evidence: Sequence[str],
    done: set[str],
    allowed_contacts: Iterable[str],
    system_prompt: str,
    canary: str,
    used_tools: bool = True,
) -> CheckResult:
    result = CheckResult()
    check_citations(reply, source_count, result)
    check_cited(reply, source_count, used_tools, result)
    check_figures(reply, evidence, result)
    check_claims(reply, done, result)
    check_leaks(reply, allowed_contacts, system_prompt, canary, result)
    return result
