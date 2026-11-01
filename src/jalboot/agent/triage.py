"""Reads a customer message before any model sees it.

These checks run in code on every message, so a handoff for a safety problem or a
request for a person cannot be talked out of by anything in the conversation. They
use word lists in Arabic and English, which means they will miss phrasing nobody
listed. The model can still hand off on its own; this is the floor, not the ceiling.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from jalboot.text.normalize import detect_language, normalize

SAFETY = "safety"
SECURITY = "account_security"
HUMAN = "customer_request"
UPSET = "upset_customer"
LEGAL = "legal_threat"
AGENT_COMPLAINT = "agent_complaint"


def _terms(*words: str) -> tuple[str, ...]:
    return tuple(normalize(word) for word in words)


def _pattern(*words: str) -> re.Pattern[str]:
    alternatives = "|".join(re.escape(term) for term in _terms(*words))
    return re.compile(rf"(?<![\w])(?:{alternatives})")


HUMAN_REQUEST = _pattern(
    "real person", "a human", "human agent", "live agent", "real agent", "an agent", "a person",
    "a representative", "customer service", "your manager", "a manager", "supervisor",
    "someone real", "talk to someone", "speak to someone", "speak with someone",
    "موظف", "موظفه", "شخص حقيقي", "انسان", "مندوب خدمه", "خدمه العملاء", "المشرف", "مشرف",
    "المدير", "مدير", "احد من الدعم", "بشري",
)
HUMAN_VERB = _pattern(
    "talk", "speak", "connect", "transfer", "want", "need", "get me", "give me", "put me through",
    "let me", "escalate",
    "اكلم", "اتكلم", "اتحدث", "ابي", "ابغي", "ابغا", "اريد", "حولني", "حولوني", "وصلني", "كلموني",
    "ودي", "بكلم", "ممكن",
)
HUMAN_DIRECT = _pattern(
    "talk to a human", "speak to a human", "talk to a person", "speak to a person",
    "talk to an agent", "speak to an agent", "human please", "agent please", "representative please",
    "حولني لموظف", "حولني علي موظف", "ابي موظف", "ابغي موظف", "اريد موظف", "اكلم موظف",
    "ابي اكلم", "ابغي اكلم", "اريد التحدث",
)
NEGATION = _pattern(
    "no need", "don't need", "do not need", "dont need", "don't want", "do not want", "dont want",
    "not asking for", "without", "لا اريد", "ما ابي", "ما ابغي", "مو لازم", "لا داعي", "بدون",
    "ما احتاج", "لا احتاج",
)

SAFETY_TERMS = _pattern(
    "allergic", "allergy", "anaphyla", "food poisoning", "poisoned", "hospital", "emergency room",
    "can't breathe", "cannot breathe", "swelling", "vomiting", "injured", "injury", "accident",
    "crashed", "harass", "assault", "threatened me", "unsafe", "wrong medicine", "wrong medication",
    "wrong dose", "overdose",
    "حساسيه", "تسمم", "مستشفي", "المستشفي", "طوارئ", "الطوارئ", "اختناق", "تورم", "اصابه", "مصاب",
    "حادث", "تحرش", "هددني", "تهديد", "دواء خطا", "جرعه",
)
LEGAL_TERMS = _pattern(
    "lawyer", "attorney", "sue you", "legal action", "court", "consumer protection",
    "journalist", "newspaper", "the press", "the media", "regulator", "the ministry",
    "محامي", "المحكمه", "قضيه", "شكوي رسميه", "حمايه المستهلك", "وزاره التجاره",
    "صحفي", "الصحافه", "الجريده", "الاعلام", "الجهات المختصه",
)
ACCOUNT_TAKEOVER = _pattern(
    "hacked", "account takeover", "someone logged in", "someone else logged", "stolen account",
    "took over my account", "not me who ordered", "orders i did not place", "orders i didn't place",
    "unauthorised access", "unauthorized access",
    "مخترق", "اخترق", "تهكير", "تهكر", "هكر", "سرقوا حسابي", "دخل حسابي", "طلبات ما طلبتها",
)
AGENT_COMPLAINT_TERMS = _pattern(
    "complain about your agent", "complaint about your agent", "complaint about the agent",
    "complaint about a support", "complaint about support", "your support agent", "the support agent was",
    "your agent was", "your staff was", "شكوي علي موظف", "شكوي ضد موظف", "شكوي من موظف", "موظف الدعم كان",
    "الموظف كان", "موظفكم كان",
)
ANGER_STRONG = _pattern(
    "unacceptable", "furious", "scam", "fraud", "thieves", "disgusting", "pathetic", "disgrace",
    "worst", "fed up", "sick of", "never again", "ridiculous", "useless", "outrageous", "enraged",
    "نصب", "نصابين", "حراميه", "حرامي", "مهزله", "فضيحه", "كارثه", "قرف", "اسوا", "زفت", "غاضب",
    "معصب", "مقهور", "زهقت", "طفشت", "مستفز", "سئمت", "غير مقبول",
)
ANGER_MILD = _pattern(
    "terrible", "awful", "angry", "upset", "annoyed", "frustrated", "disappointed", "third time",
    "again and again", "nobody helps", "no one helps", "still waiting",
    "سيء", "سيئ", "زعلان", "متضايق", "منزعج", "محبط", "للمره الثالثه", "ما حد يرد", "لا احد يرد",
    "ثالث مره",
)

INJECTION = _pattern(
    "ignore previous", "ignore all previous", "ignore your instructions", "ignore the above",
    "disregard your", "disregard previous", "forget your instructions", "system prompt",
    "developer mode", "jailbreak", "you are now", "act as", "pretend to be", "new instructions",
    "override", "admin mode", "as the administrator", "your instructions",
    "تجاهل التعليمات", "تجاهل كل التعليمات", "تجاهل تعليماتك", "تعليماتك", "انس التعليمات",
    "وضع المطور", "وضع المسؤول", "اكشف التعليمات", "رساله النظام", "موجه النظام",
)


@dataclass
class Triage:
    language: str
    handoff_reason: str = ""
    upset_score: int = 0
    injection_suspected: bool = False
    signals: list[str] = field(default_factory=list)


def wants_person(folded: str) -> bool:
    for pattern in (HUMAN_DIRECT, HUMAN_REQUEST):
        for match in pattern.finditer(folded):
            # The negation can sit inside the match too: ما ابي موظف holds ابي موظف.
            if NEGATION.search(folded[max(0, match.start() - 28):match.end()]):
                continue
            if pattern is HUMAN_DIRECT:
                return True
            # "agent" alone is not a request; "I want an agent" is. Short messages
            # such as "موظف" or "a human" are requests by themselves.
            window = folded[max(0, match.start() - 32):match.end() + 12]
            if HUMAN_VERB.search(window) or len(folded.split()) <= 3:
                return True
    return False


def upset_score(original: str, folded: str) -> int:
    score = 2 * len(ANGER_STRONG.findall(folded)) + len(ANGER_MILD.findall(folded))
    letters = [c for c in original if c.isascii() and c.isalpha()]
    if len(letters) >= 12 and sum(c.isupper() for c in letters) / len(letters) > 0.7:
        score += 2
    if re.search(r"[!؟?]{3,}", original):
        score += 1
    return score


def triage_message(text: str, default_language: str = "en", upset_threshold: int = 2) -> Triage:
    folded = normalize(text)
    # A reply of a word or two, such as "ok" or an order number, keeps the conversation's language.
    language = detect_language(text, default_language) if len(text.split()) >= 3 else default_language
    result = Triage(language=language)
    result.upset_score = upset_score(text, folded)
    result.injection_suspected = bool(INJECTION.search(folded))
    if result.injection_suspected:
        result.signals.append("injection_pattern")

    # In order of harm, so a safety report inside an angry message keeps its reason.
    checks = (
        (SAFETY_TERMS.search(folded), SAFETY, "safety_term"),
        (ACCOUNT_TAKEOVER.search(folded), SECURITY, "account_takeover"),
        (LEGAL_TERMS.search(folded), LEGAL, "legal_term"),
        (AGENT_COMPLAINT_TERMS.search(folded), AGENT_COMPLAINT, "agent_complaint"),
        (wants_person(folded), HUMAN, "asked_for_person"),
        (result.upset_score >= upset_threshold, UPSET, "upset"),
    )
    for matched, reason, signal in checks:
        if matched:
            result.handoff_reason = reason
            result.signals.append(signal)
            break
    return result
