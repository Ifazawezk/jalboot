"""Fixed replies and handoff summaries.

These are used where no model should be trusted to write the text: a forced
handoff, a fallback after failed checks, and the summary a human agent reads. They
are built only from the conversation and the tool log, so the summary cannot claim
an action that did not happen.
"""

from __future__ import annotations

import re
from typing import Any, Collection, Sequence

ORDER_ID = re.compile(r"\b[A-Z]{1,3}-\d{3,}\b")

HANDOFF_REPLIES = {
    "safety": {
        "en": "If anyone is in danger or needs a doctor, please call emergency services on 999 first. I am passing this to our safety team now.",
        "ar": "إذا كان أي شخص في خطر أو يحتاج إلى طبيب، يُرجى الاتصال بالطوارئ على الرقم 999 أولًا. أحوّل الأمر الآن إلى فريق السلامة.",
    },
    "customer_request": {
        "en": "Of course. I have asked a person to join. They will see this conversation, so you do not have to repeat yourself.",
        "ar": "بالتأكيد. طلبت انضمام موظف، وسيطّلع على هذه المحادثة دون الحاجة إلى إعادة ما قلته.",
    },
    "upset_customer": {
        "en": "I am sorry about this. I am connecting you with a person who can look at it properly, and they will see everything so far.",
        "ar": "نأسف لذلك. أحوّلك إلى موظف ليتابع الأمر معك، وسيطّلع على كل ما سبق.",
    },
    "account_security": {
        "en": "I am sorry. I am passing this to our safety team now so your account can be protected.",
        "ar": "نأسف لذلك. أحوّل الأمر الآن إلى فريق السلامة لحماية حسابك.",
    },
    "agent_complaint": {
        "en": "I am sorry about your experience. I am passing this to a person who can look into it.",
        "ar": "نأسف لما واجهته. سأحوّل الأمر إلى موظف ليتابعه معك.",
    },
    "policy_requires_person": {
        "en": "This needs a person to review, so I have passed it to the team. They will see everything so far.",
        "ar": "يحتاج هذا الأمر إلى مراجعة موظف، لذا حوّلته إلى الفريق، وسيطّلع على كل ما سبق.",
    },
    "rule_conflict": {
        "en": "I do not want to guess on this one, so I am connecting you with a person who can decide.",
        "ar": "هذه الحالة تحتاج إلى قرار موظف، لذا أحوّلك إليه الآن.",
    },
    "repeated_failure": {
        "en": "I have not been able to solve this, so I am connecting you with a person who can help.",
        "ar": "لم أتمكن من حل هذا الأمر، لذا أحوّلك إلى موظف يمكنه مساعدتك.",
    },
    "legal_threat": {
        "en": "I understand. I am passing this to a person on our team who can respond to you directly.",
        "ar": "أتفهم ذلك. سأحوّل الأمر إلى أحد أفراد فريقنا ليرد عليك مباشرة.",
    },
    "low_confidence": {
        "en": "I am not sure I can answer this correctly, so I am connecting you with a person who can help.",
        "ar": "لا أستطيع تأكيد الإجابة الصحيحة هنا، لذا أحوّلك إلى موظف.",
    },
}

ACTION_LABELS = {
    "track_order": "looked up order status",
    "get_order_details": "read order details",
    "explain_delay": "read delay reason",
    "quote_refund": "worked out the refund",
    "get_customer_profile": "read customer profile",
    "issue_refund": "refund",
    "issue_credit": "wallet credit",
    "apply_promo": "promo code",
    "change_address": "address change",
    "cancel_order": "cancellation",
    "create_ticket": "ticket",
    "search_knowledge": "searched the help articles",
}


IDENTITY_REPLY = {
    "en": "I need to confirm it is you before I can open your order.",
    "ar": "أحتاج إلى التأكد من هويتك قبل أن أفتح طلبك.",
}


def identity_reply(language: str) -> str:
    return IDENTITY_REPLY.get(language, IDENTITY_REPLY["en"])


def _qar(value: float) -> str:
    return f"{float(value):.2f}".removesuffix(".00")


def _refund_line(result: dict[str, Any], arabic: bool) -> str:
    amount, order = _qar(result["amount_qar"]), result["order_id"]
    original, credit = result.get("to_original_payment_qar"), result.get("to_credit_qar")
    if arabic:
        head = f"تم استرداد {amount} ر.ق لطلب {order}"
        if original and credit:
            return f"{head}: {_qar(original)} ر.ق إلى وسيلة الدفع الأصلية و{_qar(credit)} ر.ق إلى رصيدك."
        return f"{head}، وأُضيف إلى رصيدك." if credit else f"{head}، ويعود إلى وسيلة الدفع الأصلية."
    head = f"Refund of QAR {amount} on {order} is done"
    if original and credit:
        return f"{head}: QAR {_qar(original)} to your original payment and QAR {_qar(credit)} to your wallet."
    return f"{head}: it is in your wallet." if credit else f"{head}: it goes back to your original payment."


def _credit_line(result: dict[str, Any], arabic: bool) -> str:
    amount, order = _qar(result["amount_qar"]), result["order_id"]
    return f"أُضيف {amount} ر.ق إلى رصيدك عن طلب {order}." if arabic else f"QAR {amount} credit on {order} is in your wallet."


def _address_line(result: dict[str, Any], arabic: bool) -> str:
    order, fee = result["order_id"], result.get("fee_qar")
    if arabic:
        return f"تم تحديث عنوان طلب {order}." + (f" وتبلغ رسوم التغيير {_qar(fee)} ر.ق." if fee else "")
    return f"The address on {order} is updated." + (f" The change costs QAR {_qar(fee)}." if fee else "")


def _cancel_line(result: dict[str, Any], arabic: bool) -> str:
    order = result["order_id"]
    charge, refund, credit = (result.get(name) for name in ("charge_qar", "refund_qar", "credit_qar"))
    if arabic:
        parts = [f"تم إلغاء طلب {order}."]
        parts += [f"ورسوم الإلغاء {_qar(charge)} ر.ق."] if charge else []
        parts += [f"ويعود إليك {_qar(refund)} ر.ق."] if refund else []
        parts += [f"وأُضيف {_qar(credit)} ر.ق إلى رصيدك."] if credit else []
        return " ".join(parts)
    parts = [f"{order} is cancelled."]
    parts += [f"The cancellation charge is QAR {_qar(charge)}."] if charge else []
    parts += [f"QAR {_qar(refund)} comes back to you."] if refund else []
    parts += [f"QAR {_qar(credit)} credit is in your wallet."] if credit else []
    return " ".join(parts)


# The action each sentence reports, as agent.checks names it, so a reply that already
# says it does not get it twice.
ACTION_SENTENCES = {
    "issue_refund": ("refund", _refund_line),
    "issue_credit": ("credit", _credit_line),
    "change_address": ("address", _address_line),
    "cancel_order": ("cancel", _cancel_line),
}


def action_lines(tool_log: Sequence[dict[str, Any]], language: str, skip: Collection[str] = ()) -> list[str]:
    """What this turn really did, built only from tool results. A finished action reaches
    the customer in these words even when the model left it out or its reply was held
    back. Nothing here reads a pending or refused result."""
    lines = []
    for entry in tool_log:
        result = entry.get("result") or {}
        if entry["tool"] in ACTION_SENTENCES and result.get("status") == "done":
            action, sentence = ACTION_SENTENCES[entry["tool"]]
            if action not in skip:
                lines.append(sentence(result, language == "ar"))
    return list(dict.fromkeys(lines))


def handoff_reply(reason: str, language: str) -> str:
    table = HANDOFF_REPLIES.get(reason, HANDOFF_REPLIES["low_confidence"])
    return table.get(language, table["en"])


def _describe(entry: dict[str, Any]) -> str:
    label = ACTION_LABELS.get(entry["tool"], entry["tool"])
    result = entry.get("result") or {}
    order = (entry.get("arguments") or {}).get("order_id")
    amount = (entry.get("arguments") or {}).get("amount_qar")
    parts = [label]
    if order:
        parts.append(str(order))
    if amount is not None:
        parts.append(f"QAR {amount}")
    if not result.get("ok", False):
        parts.append(f"refused: {result.get('error', 'unknown')}")
    elif result.get("status"):
        parts.append(str(result["status"]))
    return " ".join(parts)


def handoff_summary(
    reason: str,
    text: str,
    history: Sequence[dict[str, str]],
    tool_log: Sequence[dict[str, Any]],
    customer_label: str,
    language: str,
) -> str:
    """What the human agent reads first. Plain facts, oldest first."""
    customer_lines = [turn["text"] for turn in history if turn["role"] == "customer"]
    first = customer_lines[0] if customer_lines else text
    orders = list(dict.fromkeys(
        ORDER_ID.findall(" ".join([*customer_lines, text]))
        + [str(e["arguments"]["order_id"]) for e in tool_log if (e.get("arguments") or {}).get("order_id")]
    ))
    lines = [
        f"Reason: {reason}",
        f"Customer: {customer_label or 'not verified'}",
        f"Language: {language}",
        f"Orders: {', '.join(orders) if orders else 'none named'}",
        f"Asked first: {first[:300]}",
    ]
    if customer_lines:
        lines.append(f"Latest message: {text[:300]}")
    actions = [_describe(entry) for entry in tool_log if entry["tool"] != "handoff_to_human"]
    lines.append("Done so far: " + ("; ".join(actions) if actions else "nothing yet"))
    return "\n".join(lines)
