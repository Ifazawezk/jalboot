"""Checks every reply against what really happened before a customer sees it.

A reply is free text from a model, so nothing in it can be trusted by default:
    citations   each [n] must point at a passage that was retrieved in this turn
    figures     each money amount, duration or percentage must appear in the sources or
                the tool results, as the same kind of figure
    claims      a reply may only say that money moved, or that an address or an order
                changed, when a tool result in this turn shows it, for the amount the
                tool shows
    leaks       no system prompt text, and no phone number or email except the
                customer's own

The customer's own message is not evidence. Otherwise "I want my QAR 500 back" would
vouch for a reply that promises exactly that.

These are phrase lists, so a claim worded in a way nobody listed still gets through.
That is why the loop also states finished actions itself, from the tool results.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Iterator, Mapping, Sequence

from jalboot.text.normalize import normalize

CITATION = re.compile(r"\[(\d{1,2})\]")
# A comma before one or two digits is a decimal point. Before three it groups thousands.
AMOUNT = r"\d+(?:,\d{3}(?!\d))*(?:[.,]\d+)?"
MONEY_UNIT = r"(?:qar|qr|riyals?|rials?|ريال\w*|ر\.?\s?ق)"
# Passed through normalize, because دقائق reaches these patterns as دقايق.
OTHER_UNIT = "(?:" + "|".join(normalize(unit) for unit in (
    "%", "percent", "per cent", "minutes?", "mins?", "hours?", "hrs?", "(?:business |working )?days?", "weeks?",
    "months?", "دقيقة", "دقائق", "ساعة", "ساعات", "يوم", "أيام", "أسبوع", "أسابيع", "شهر", "أشهر", "بالمئة",
    "بالمائة", "في المئة", "في المائة",
)) + ")"
FIGURE = re.compile(
    rf"(?<![a-z]){MONEY_UNIT}(?![a-z])\s*[:.]?\s*(?P<first>{AMOUNT})"
    rf"|(?<!\w)(?P<second>{AMOUNT})[\s-]*(?:(?P<money>{MONEY_UNIT})|{OTHER_UNIT})(?![a-z])"
)
# A table cell holds a bare number, with its unit in the column header or the caption.
BARE_NUMBER = re.compile(rf"(?<![\w-]){AMOUNT}")
# The policy writes an Arabic dual with its digit after it: ساعتان (2).
COUNT_IN_BRACKETS = re.compile(r"\((\d+)\)")
PHONE = re.compile(r"(?<![\w-])\+?\d[\d\s-]{7,14}\d(?![\w-])")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
ISO_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
ARABIC_SEPARATORS = str.maketrans({"٫": ".", "٬": ","})
SENTENCE_END = re.compile(r"(?<=[.!?;])\s+|\n+")
CLAUSE_END = re.compile(r"[,;:]|\bbut\b|لكن")


def _phrases(*phrases: str) -> re.Pattern[str]:
    alternatives = "|".join(normalize(phrase) for phrase in phrases)
    return re.compile(rf"(?<!\w)[وف]?(?:{alternatives})(?!\w)")


ARABIC_MONEY = r"(?:ال)?(?:مبلغ|رسوم)"
# Said as already done. A citation does not excuse these: no policy text can make a
# payment have happened.
COMPLETED = {
    "refund": _phrases(
        "been refunded", "(?:was|were) refunded", "(?:i|we)(?: have|['’]ve)? refunded",
        "refund (?:has been|was|is) (?:issued|processed|approved|completed|paid|sent)",
        r"(?:processed|issued|sent|completed) (?:your|a|the)(?: \w+)? refund",
        "your money is on its way", "on (?:its|the) way back", "(?:returned|sent back) your money",
        "sent your money back",
        "تم الاسترداد", "تم استرداد", "تم رد", "تم إرجاع", f"تمت إعادة {ARABIC_MONEY}",
        f"(?:أعدنا|أرجعنا|رجعنا|رددنا) {ARABIC_MONEY}",
    ),
    "credit": _phrases(
        "been credited", "(?:was|were) credited", "(?:i|we)(?: have|['’]ve)? credited",
        "(?:i|we)(?: have|['’]ve)? added [^.]*(?:credit|wallet)", r"(?:been|was|were) added to your \w+",
        r"أضفنا رصيد\w*", "(?:تم|تمت) (?:إضافة|إيداع) (?:رصيد|مبلغ|المبلغ)",
    ),
    "address": _phrases(
        "address (?:has been|was|is) (?:changed|updated|moved)", "(?:updated|changed) your address",
        "تم (?:تغيير|تحديث|تعديل) (?:ال)?عنوان", "غيرنا (?:ال)?عنوان",
    ),
    # No tool can arrange this, so a reply that claims it always fails.
    "redelivery": _phrases(
        "(?:arranged|scheduled|booked)(?: a| your)? redelivery", "redelivery is on its way",
        "redelivery (?:has been|is) (?:arranged|scheduled|booked|confirmed)", "will be redelivered", "will redeliver",
        "رتبت إعادة التوصيل", "رتبنا إعادة التوصيل", "تم ترتيب إعادة التوصيل", "سيعاد توصيل", "سنعيد توصيل",
    ),
    "cancel": _phrases(
        "(?:has been|was) cancell?ed", "(?:i|we)(?: have|['’]ve)? cancell?ed", "cancell?ed your order",
        "تم إلغاء", "ألغينا طلبك",
    ),
}
# Said as what will happen. A policy answer can fairly sound like this, so these only
# count in a turn that used tools, or with no source behind them.
PROMISED = {
    "refund": _phrases(
        r"you(?: will|['’]ll)? (?:get|receive)\b.*\b(?:back|refund\w*)", "will be (?:refunded|returned)", "is refunded",
        "comes? back to you", "will reach your (?:card|bank|account)",
        "سيتم (?:استرداد|رد|إرجاع)", "ستسترد", "س?يعود إليك", "س?ترجع لك", "سيرجع لك",
    ),
    "credit": _phrases(
        "will be credited", r"will be added to your \w+", "added to your wallet", "سيضاف", "ستضاف", "سيتم إضافة",
    ),
}
NEGATED = re.compile(r"(?<!\w)(?:not|never|no longer|cannot|unable|failed|لم|لن|لا|ما|مو|ليس|تعذر)(?!\w)|n['’]t(?!\w)")
CONDITION = re.compile(
    r"(?<!\w)(?:if|once|when|unless|until|whether|in case|as soon as|اذا|لو|في حال|عند|عندما|بمجرد|فور)(?!\w)"
)
# Softer words that only make a promise conditional. "After checking, your refund has
# been issued" is still a claim, so these are not read for completed claims.
SPECULATION = re.compile(r"(?<!\w)(?:would|could|might|may|can|should|after|بعد|قد|يمكن|ممكن)(?!\w)")

ACTION_FIELDS = (
    "amount_qar", "refund_qar", "charge_qar", "credit_qar", "to_original_payment_qar", "to_credit_qar", "fee_qar",
)
WRITE_EFFECTS = {
    "issue_refund": "refund", "issue_credit": "credit", "change_address": "address", "cancel_order": "cancel",
}
# Refused because it already happened, so saying that it happened is true.
ALREADY_DONE = {
    "already_refunded": "refund", "item_already_refunded": "refund", "full_refund_already_given": "refund",
    "late_credit_already_issued": "credit",
}


# Models like typographic hyphens and spaces. An order number holding one cannot be
# searched or copied, and it slips past every pattern here.
LOOKALIKES = str.maketrans({
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-",
    " ": " ", " ": " ", " ": " ", " ": " ",
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


@dataclass(frozen=True)
class Known:
    """The figures a reply may state, kept apart so that a duration cannot vouch for money."""

    money: frozenset[float]
    other: frozenset[float]


@dataclass(frozen=True)
class Effects:
    """What the tools in this turn really did, what they offered, and for how much."""

    done: frozenset[str] = frozenset()
    offered: frozenset[str] = frozenset()
    amounts: frozenset[float] = frozenset()


@dataclass(frozen=True)
class Claim:
    action: str
    sentence: str
    promised: bool


def _fold(text: str) -> str:
    return normalize(text.translate(ARABIC_SEPARATORS))


def _value(text: str) -> float:
    head, comma, tail = text.rpartition(",")
    if comma and "." not in tail and len(tail) <= 2:
        text = f"{head}.{tail}"
    return round(float(text.replace(",", "")), 2)


def _figures(text: str) -> Iterator[tuple[float, bool]]:
    """Each figure in a text, and whether it is money."""
    for match in FIGURE.finditer(_fold(text)):
        yield _value(match["first"] or match["second"]), bool(match["first"] or match["money"])


def figures_in(reply: str) -> list[float]:
    """The numbers a reply states as money, durations or percentages."""
    return [value for value, _ in _figures(reply)]


def _tool_numbers(value: Any, key: str = "") -> Iterator[tuple[float, bool]]:
    """Only real number fields count. Text inside a result, such as a timestamp or a
    merchant's note, cannot vouch for a figure."""
    if isinstance(value, Mapping):
        for name, item in value.items():
            yield from _tool_numbers(item, str(name))
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _tool_numbers(item, key)
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        if key.endswith("_dh"):
            yield round(value / 100, 2), True
        else:
            yield round(float(value), 2), key.endswith("_qar")


def known_figures(sources: Iterable[str], tool_results: Iterable[Any] = ()) -> Known:
    money: set[float] = set()
    other: set[float] = set()
    for value, is_money in _tool_numbers(list(tool_results)):
        (money if is_money else other).add(value)
    for text in sources:
        for value, is_money in _figures(text):
            (money if is_money else other).add(value)
        folded = _fold(text)
        other.update(float(count) for count in COUNT_IN_BRACKETS.findall(folded))
        for line in folded.splitlines():
            if line.lstrip().startswith("|"):
                cells = {_value(number) for number in BARE_NUMBER.findall(line)}
                money |= cells
                other |= cells
    return Known(frozenset(money), frozenset(other))


def effects_of(tool_log: Sequence[Mapping[str, Any]]) -> Effects:
    done: set[str] = set()
    offered: set[str] = set()
    amounts: set[float] = set()

    def note_amounts(result: Mapping[str, Any]) -> None:
        amounts.update(round(float(result[name]), 2) for name in ACTION_FIELDS if result.get(name) is not None)

    for entry in tool_log:
        tool, result = entry["tool"], entry["result"]
        status = result.get("status")
        if result.get("error") in ALREADY_DONE:
            done.add(ALREADY_DONE[result["error"]])
        elif status == "cancelled":
            done.add("cancel")
        elif tool in WRITE_EFFECTS and status == "done":
            done.add(WRITE_EFFECTS[tool])
            if tool == "cancel_order":
                done.add("refund")
            if result.get("credit_qar") or result.get("to_credit_qar"):
                done.add("credit")
            note_amounts(result)
        elif status == "needs_confirmation" or (tool == "quote_refund" and result.get("ok")):
            offered.add("refund")
            note_amounts(result)
    return Effects(frozenset(done), frozenset(offered), frozenset(amounts))


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


def check_figures(reply: str, known: Known, result: CheckResult) -> None:
    for value, is_money in _figures(reply):
        if value not in (known.money if is_money else known.other):
            result.fail(f"figure {value:g} is not in the sources or tool results")


def _denied(sentence: str, match: re.Match[str]) -> bool:
    clause = CLAUSE_END.split(sentence[:match.start()])[-1]
    return NEGATED.search(clause + match.group()) is not None


def claims_in(reply: str) -> Iterator[Claim]:
    """Sentences saying that something happened, or will, to this customer. Anything
    negated or conditional is left out: "if a person approves it, you will be refunded"
    is what the system prompt asks for."""
    for sentence in SENTENCE_END.split(_fold(reply)):
        for action, pattern in COMPLETED.items():
            for match in pattern.finditer(sentence):
                if not _denied(sentence, match) and not CONDITION.search(sentence[:match.start()]):
                    yield Claim(action, sentence, False)
        if CONDITION.search(sentence) or SPECULATION.search(sentence):
            continue
        for action, pattern in PROMISED.items():
            for match in pattern.finditer(sentence):
                if not _denied(sentence, match):
                    yield Claim(action, sentence, True)


def claimed_actions(reply: str) -> set[str]:
    return {claim.action for claim in claims_in(reply)}


def check_claims(
    reply: str, done: Iterable[str], result: CheckResult, *,
    offered: Iterable[str] = (), amounts: Iterable[float] = (), used_tools: bool = True,
) -> None:
    done, offered, amounts = set(done), set(offered), set(amounts)
    # A quote is only an offer while the reply is still asking the customer.
    asking = "?" in _fold(reply)
    failed: set[str] = set()
    for claim in claims_in(reply):
        figures = list(_figures(claim.sentence))
        policy_answer = not used_tools and CITATION.search(claim.sentence) and not any(money for _, money in figures)
        if claim.promised and policy_answer:
            continue
        if claim.action not in done and not (claim.promised and asking and claim.action in offered):
            if claim.action not in failed:
                result.fail(f"reply claims {claim.action} but no tool result shows it")
            failed.add(claim.action)
            continue
        for value, is_money in figures:
            if is_money and value not in amounts:
                result.fail(f"reply claims {claim.action} of {value:g} but the tool result shows another amount")


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
    done: Iterable[str],
    allowed_contacts: Iterable[str],
    system_prompt: str,
    canary: str,
    used_tools: bool = True,
    tool_results: Sequence[Any] = (),
    offered: Iterable[str] = (),
    amounts: Iterable[float] = (),
) -> CheckResult:
    """evidence holds the source passages. Tool results are read by their number fields."""
    result = CheckResult()
    check_citations(reply, source_count, result)
    check_cited(reply, source_count, used_tools, result)
    check_figures(reply, known_figures(evidence, tool_results), result)
    check_claims(reply, done, result, offered=offered, amounts=amounts, used_tools=used_tools)
    check_leaks(reply, allowed_contacts, system_prompt, canary, result)
    return result
