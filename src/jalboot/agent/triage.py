"""Reads a customer message before any model sees it.

These checks run in code on every message, so a handoff for a safety problem or a
request for a person cannot be talked out of by anything in the conversation. They
use word lists in Arabic and English, which means they will miss phrasing nobody
listed. The model can still hand off on its own; this is the floor, not the ceiling.

A false alarm costs a person's time and a miss can cost much more, so the lists lean
toward firing. The exceptions are narrow: phrases that plainly report nothing.
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


# Arabic attaches the article and prepositions to the word itself, so a search that
# starts at the word boundary misses الحساسية, بالحساسية and للتحرش.
ARABIC_PREFIX = r"(?:[وفبكل]|ال|لل|بال|وال|فال|كال)?"


def _alternative(term: str) -> str:
    """A Latin term ends at the word boundary, so "accident" does not match "accidentally"
    and "a person" does not match "a personal". A trailing * marks a stem that may go on.
    Arabic stays open, because suffixes attach to the word."""
    if term.endswith("*"):
        return re.escape(term[:-1]) + r"\w*"
    return re.escape(term) + (r"(?!\w)" if term[-1].isascii() else "")


def _pattern(*words: str) -> re.Pattern[str]:
    alternatives = "|".join(_alternative(term) for term in sorted(_terms(*words), key=len, reverse=True))
    return re.compile(rf"(?<![\w]){ARABIC_PREFIX}(?:{alternatives})")


HUMAN_REQUEST = _pattern(
    "real person", "a human", "human agent", "live agent", "real agent", "an agent", "a person",
    "a representative", "customer service", "your manager", "a manager", "supervisor",
    "someone real", "talk to someone", "speak to someone", "speak with someone",
    "موظف", "موظفه", "شخص حقيقي", "انسان", "مندوب خدمه", "خدمه العملاء", "المشرف", "مشرف",
    "المدير", "مدير", "احد من الدعم", "بشري",
)
HUMAN_VERB = _pattern(
    "talk*", "speak*", "connect*", "transfer*", "want*", "need*", "get me", "give me", "put me through",
    "let me", "escalat*",
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
    "allergic", "anaphyla*", "food poisoning", "poisoned", "emergency room",
    "can't breathe", "cant breathe", "cannot breathe", "can't breath", "cant breath", "struggling to breathe",
    "swelling", "swollen", "vomit*", "injur*",
    "accident", "accidents", "crashed", "harass*", "assault*", "threatened me", "threatening me", "unsafe",
    "wrong medicine", "wrong medication", "wrong dose", "wrong strength", "overdos*", "heart is racing",
    "had a reaction", "bad stomach", "stomach pain*", "at the clinic", "i'm scared", "i am scared",
    "make me pay for", "glass in", "bleeding", "choking", "trouble breathing", "difficulty breathing",
    "hard to breathe", "a rash", "hives", "throat is closing", "threw up",
    "تسمم", "طوارئ", "الطوارئ", "اختناق", "تورم", "اصابه", "مصاب", "حادث", "تحرش", "هددني", "تهديد",
    "دواء خطا", "جرعه", "خايفه", "خايف", "انجرح", "ينزل دم", "قزاز", "زجاج في", "رسايل مزعجه", "يطق الباب",
    "يرفض يمشي", "صعوبه في التنفس", "ضيق تنفس", "ضيق في التنفس", "ما اقدر اتنفس", "طفح", "استفراغ", "يهدد",
)
# These hold a safety word and report nothing.
NOT_A_SAFETY_REPORT = _pattern(
    "by accident", "app crashed", "app has crashed", "website crashed", "site crashed",
)
ALLERGY = _pattern("allergy", "allergies", "allergen*", "حساسيه")
# Someone it happened to, or something that happened. With either, the mention is a report.
ALLERGY_EVENT = _pattern(
    "i have", "i've", "i got", "i had", "i am", "i'm", "we have", "my allerg*", "our allerg*", "reaction", "attack",
    "after", "ate", "eaten", "eating", "son", "daughter", "wife", "husband", "mother", "mum", "mom", "father", "dad",
    "baby", "child", "children", "kid*", "friend", "brother", "sister",
    "عندي", "عنده", "عندها", "لدي", "ابني", "بنتي", "ولدي", "زوجي", "زوجتي", "امي", "ابوي", "اخوي", "اختي",
    "طفلي", "طفلتي", "اكلت", "اكلته", "اكلها", "بعد",
)
ALLERGY_QUESTION = _pattern(
    "do you", "does", "is there", "are there", "what", "which", "where", "how", "can i", "can you", "could you",
    "tell me", "show me", "info", "information", "policy", "rules", "question",
    "هل", "ايش", "وش", "شو", "ما هي", "ما هو", "كيف", "وين", "اين", "معلومات", "سياسه",
)
HAVE_A_QUESTION = _pattern("i have a question", "i've got a question", "عندي سوال")
# A hospital is only a safety signal when someone went there because of the order.
HOSPITAL = _pattern("hospital*", "مستشفي", "المستشفي")
WORKS_THERE = _pattern(
    "i work*", "work at", "work in", "working at", "working in", "nurse*", "doctor at",
    "اشتغل", "ممرضه", "ممرض", "دوامي", "طبيب في",
)
LEGAL_TERMS = _pattern(
    "lawyer*", "attorney*", "sue you", "legal action", "in court", "to court", "take you to", "consumer protection",
    "journalist*", "newspaper*", "the press", "the media", "regulator*", "the ministry",
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
    "your agent was", "your staff was", "the agent who", "complain about her", "complain about him",
    "شكوي علي موظف", "شكوي ضد موظف", "شكوي من موظف", "موظف الدعم كان",
    "الموظف كان", "موظفكم كان",
)
PRAISE = _pattern(
    "great", "helpful", "amazing", "excellent", "kind", "nice", "friendly", "polite", "lovely", "wonderful",
    "fantastic", "good", "thank*",
    "ممتاز", "رائع", "محترم", "شكرا", "لطيف", "متعاون", "كفو",
)
COMPLAINT_WORDS = _pattern(
    "complain*", "rude", "not", "never", "hung up", "ignor*", "wasn't", "isn't",
    "شكوي", "وقح", "ما رد", "ما ساعد", "مو زين", "مو كويس", "مو محترم", "غير محترم",
)
ANGER_STRONG = _pattern(
    "unacceptable", "end of my rope", "you people", "furious", "scam*", "fraud*", "thieves", "disgust*", "pathetic",
    "disgrace*", "worst", "fed up", "sick of", "never again", "ridiculous", "useless", "outrageous", "enraged",
    "نصب", "نصابين", "حراميه", "حرامي", "مهزله", "فضيحه", "كارثه", "قرف", "اسوا", "زفت", "غاضب",
    "معصب", "مقهور", "زهقت", "طفشت", "مستفز", "سئمت", "غير مقبول",
)
ANGER_MILD = _pattern(
    "terrible", "awful", "angry", "upset", "annoyed", "frustrated", "disappointed", "third time",
    "again and again", "nobody helps", "no one helps", "still waiting",
    "سيء", "سيئ", "زعلان", "متضايق", "منزعج", "محبط", "للمره الثالثه", "ما حد يرد", "لا احد يرد",
    "ثالث مره",
)
# These hold an angry word and say nothing about how the customer feels.
NOT_ANGER = _pattern(
    "worst case", "worst-case", "report fraud", "reporting fraud", "report a fraud", "fraud team", "fraud department",
)

INJECTION = _pattern(
    "ignore previous", "ignore all previous", "ignore your instructions", "ignore the above",
    "disregard your", "disregard previous", "forget your instructions", "system prompt*",
    "developer mode", "jailbreak*", "you are now", "act as", "pretend to be", "new instructions",
    "overrid*", "admin mode", "as the administrator", "your instructions",
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


def reports_allergy(folded: str) -> bool:
    """Asking what the menu lists is a question, which SAF-01 answers. Every other mention
    counts as a report, so a message has to look like a question to stay with the bot."""
    if not ALLERGY.search(folded):
        return False
    remaining = HAVE_A_QUESTION.sub(" ", folded)
    asking = "?" in folded or ALLERGY_QUESTION.search(folded)
    return bool(ALLERGY_EVENT.search(remaining)) or not asking


def reports_safety(folded: str) -> bool:
    if SAFETY_TERMS.search(NOT_A_SAFETY_REPORT.sub(" ", folded)) or reports_allergy(folded):
        return True
    return bool(HOSPITAL.search(folded)) and not WORKS_THERE.search(folded)


def complains_about_staff(folded: str) -> bool:
    if not AGENT_COMPLAINT_TERMS.search(folded):
        return False
    return not PRAISE.search(folded) or bool(COMPLAINT_WORDS.search(folded))


def upset_score(original: str, folded: str) -> int:
    calm = NOT_ANGER.sub(" ", folded)
    score = 2 * len(ANGER_STRONG.findall(calm)) + len(ANGER_MILD.findall(calm))
    letters = [c for c in original if c.isascii() and c.isalpha()]
    if len(letters) >= 12 and sum(c.isupper() for c in letters) / len(letters) > 0.7:
        score += 2
    if re.search(r"[!؟?]{3,}", original):
        score += 1
    return score


def triage_message(text: str, default_language: str = "en", upset_threshold: int = 2) -> Triage:
    # Phone keyboards type a curly apostrophe, which would hide "can't breathe".
    folded = normalize(text).replace("\u2019", "'")
    # A reply of a word or two, such as "ok" or an order number, keeps the conversation's language.
    language = detect_language(text, default_language) if len(text.split()) >= 3 else default_language
    result = Triage(language=language)
    result.upset_score = upset_score(text, folded)
    result.injection_suspected = bool(INJECTION.search(folded))
    if result.injection_suspected:
        result.signals.append("injection_pattern")

    # In order of harm, so a safety report inside an angry message keeps its reason.
    checks = (
        (reports_safety(folded), SAFETY, "safety_term"),
        (ACCOUNT_TAKEOVER.search(folded), SECURITY, "account_takeover"),
        (LEGAL_TERMS.search(folded), LEGAL, "legal_term"),
        (complains_about_staff(folded), AGENT_COMPLAINT, "agent_complaint"),
        (wants_person(folded), HUMAN, "asked_for_person"),
        (result.upset_score >= upset_threshold, UPSET, "upset"),
    )
    for matched, reason, signal in checks:
        if matched:
            result.handoff_reason = reason
            result.signals.append(signal)
            break
    return result
