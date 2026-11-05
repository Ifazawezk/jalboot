"""The policy section behind each action the tools take.

A reply that rests on a tool result often says what happened and stops there. The tool
knows which rule it applied, so it names the section, and the reply shows that section
as its source. A reason that more than one section could cover is left out rather than
guessed, and so are parcels, which have their own rules.
"""

from __future__ import annotations

CANCEL_SECTIONS = {
    "grace_period": "CAN-03", "scheduled_free": "CAN-03", "scheduled_late": "CAN-03",
    "late_free_cancel": "CAN-04", "eta_slip_free_cancel": "CAN-04", "jalboot_auto_cancel": "CAN-04",
}
# The late order table in LAT-03 states these rules too. A reply that already cites it
# shows where the rule comes from, so the action adds no second section.
ALSO_STATED = {"late_free_cancel": ("LAT-03",), "jalboot_auto_cancel": ("LAT-03",)}
REASON_SECTIONS = {
    "cancellation_credit": "CAN-04",
    "cold_food": "WRG-05",
    "damaged_item": "WRG-05",
    "duplicate_charge": "PAY-03",
    "expired_item_credit": "GRC-05",
    "failed_contact_refund": "LAT-05",
    "late_delivery": "LAT-01",
    "late_delivery_fee": "LAT-01",
    "modifier_missed": "WRG-02",
    "not_received": "LAT-04",
    "quality": "WRG-05",
    "substitute_rejected": "GRC-04",
}


def cancel_section(code: str, category: str, cash_charge: bool) -> str:
    if code in CANCEL_SECTIONS:
        return CANCEL_SECTIONS[code]
    if cash_charge:
        return "CAN-05"
    return "CAN-01" if category == "food" else "CAN-02"


def cancel_also(code: str) -> tuple[str, ...]:
    return ALSO_STATED.get(code, ())


def refund_section(reason: str, category: str) -> str | None:
    if category == "parcel":
        return None
    if reason == "expired_product":
        return "GRC-05" if category == "grocery" else None
    return REASON_SECTIONS.get(reason)
