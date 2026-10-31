"""Policy decisions as pure functions.

Nothing here reads a database, calls a model or looks at the clock, so every rule can
be tested with plain values. The tool layer collects the facts from the database and
acts on the decision. A model can ask for anything; it cannot change what comes out
of these functions.

Section ids in comments point at the policy documents in knowledge/.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Sequence

from jalboot.policy.rules import Rules, percent_of, to_dh

EXECUTE, APPROVAL, DENY = "execute", "approval", "deny"
# GEN-04 step 6: two rules conflict, so automated support does not choose. Nothing
# happens to the money, and the conversation goes to a person.
ESCALATE = "escalate"
ROLES = ("agent", "supervisor", "finance_lead")

# Reason code to its window in refunds.windows_hours (REF-02). None means the window
# depends on the order type.
REASON_WINDOWS: dict[str, str | None] = {
    "missing_item": None,
    "wrong_item": None,
    "damaged_item": None,
    "spoiled_item": None,
    "quality": "food_quality",
    "cold_food": "food_temperature",
    "chilled_item": "grocery_chilled_frozen",
    "expired_product": "expired_product",
    "cold_chain": "pharmacy_cold_chain",
    "allergen": "allergen_mismatch",
    "foreign_object": "foreign_object",
    "broken_seal": "broken_seal",
    "illness": "suspected_illness",
    "not_received": "not_received",
    "modifier_missed": None,
    "whole_wrong_order": None,
    "substitute_rejected": "grocery_ambient",
    "late_delivery_fee": "late_credit",
}
# These have their own rules for when they can be claimed, handled below.
OWN_WINDOW_REASONS = {"duplicate_charge", "failed_contact_refund"}
ALL_REFUND_REASONS = set(REASON_WINDOWS) | OWN_WINDOW_REASONS
CATEGORY_WINDOWS = {
    "food": "food_standard",
    "grocery": "grocery_ambient",
    "pharmacy": "pharmacy_standard",
}
SAFETY_REASONS = {"allergen", "foreign_object", "illness", "broken_seal"}
# ESC-02: these go to a person at once, not only to the approval queue.
HANDOFF_CODES = {
    "pharmacy_needs_person", "safety_needs_person", "parcel_needs_person", "proof_of_delivery_exists",
}
PHOTO_ALWAYS = {"foreign_object", "expired_product", "broken_seal"}
PHOTO_ABOVE_LIMIT = {"wrong_item", "damaged_item", "spoiled_item", "quality"}
# REF-05 and GRC-04: these never count as claims for the repeat and trust checks.
NOT_CLAIMS = {
    "duplicate_charge", "merchant_cancelled", "late_delivery", "late_delivery_fee", "goodwill",
    "cancellation_credit", "expired_item_credit", "allergen", "foreign_object", "illness",
    "broken_seal", "customer_cancelled", "substitute_rejected",
}
CREDIT_REASONS = {"late_delivery", "goodwill"}


@dataclass(frozen=True)
class ItemFact:
    name: str
    quantity: int
    unit_dh: int
    promo_eligible: bool = True


@dataclass(frozen=True)
class OrderFacts:
    id: str
    category: str
    status: str
    placed_at: datetime
    promised_at: datetime | None
    delivered_at: datetime | None
    subtotal_dh: int
    discount_dh: int = 0
    delivery_fee_dh: int = 0
    other_fees_dh: int = 0
    tip_dh: int = 0
    payment_method: str = "card"
    severe_weather: bool = False
    failed_contact: bool = False
    proof_of_delivery: bool = False
    gps_distance_m: int | None = None
    items: tuple[ItemFact, ...] = ()
    estimate_at: datetime | None = None
    iftar_window: bool = False
    cancelled_by: str = ""
    scheduled_slot_at: datetime | None = None
    charges: tuple[tuple[datetime, int, str], ...] = ()
    open_bank_dispute: bool = False
    cold_chain: bool = False
    credit_paid_dh: int = 0
    # GEN-03: refunds and late credit use the subtotal after picking and substitutions.
    final_subtotal_dh: int | None = None

    @property
    def refund_subtotal_dh(self) -> int:
        return self.subtotal_dh if self.final_subtotal_dh is None else self.final_subtotal_dh

    @property
    def paid_dh(self) -> int:
        return self.subtotal_dh - self.discount_dh + self.delivery_fee_dh + self.other_fees_dh + self.tip_dh

    @property
    def net_items_dh(self) -> int:
        return self.subtotal_dh - self.discount_dh


@dataclass(frozen=True)
class ClaimFacts:
    """What has already happened, worked out from the database by the tool layer."""

    refunded_on_order_dh: int = 0
    credit_on_order_dh: int = 0
    claims_30d: int = 0
    claims_90d: int = 0
    claims_total_30d_dh: int = 0
    not_received_90d: int = 0
    goodwill_30d_dh: int = 0
    account_age_days: int = 365
    wallet_dh: int = 0


@dataclass(frozen=True)
class Decision:
    outcome: str
    code: str
    required_role: str = ""
    limit_dh: int = 0
    detail: dict[str, Any] = field(default_factory=dict)


def hours_since(moment: datetime | None, now: datetime) -> float | None:
    return None if moment is None else (now - moment).total_seconds() / 3600


def minutes_late(order: OrderFacts, now: datetime) -> int:
    """LAT-01: delivered_at minus promised_at, rounded down. An order still on its way
    is measured against now."""
    if order.promised_at is None:
        return 0
    end = order.delivered_at or now
    return max(int((end - order.promised_at).total_seconds() // 60), 0)


def window_hours(rules: Rules, reason: str, category: str) -> int | None:
    key = REASON_WINDOWS.get(reason)
    if reason in REASON_WINDOWS and key is None:
        key = CATEGORY_WINDOWS.get(category)
    return None if key is None else int(rules.get(f"refunds.windows_hours.{key}"))


def in_window(rules: Rules, reason: str, order: OrderFacts, now: datetime) -> bool:
    limit = window_hours(rules, reason, order.category)
    since = hours_since(order.delivered_at, now)
    if limit is None or since is None:
        return False
    return since <= limit  # window_end_inclusive


def approval_role(rules: Rules, total_dh: int) -> str:
    """REF-05: the level is set by the total value on the order, and an amount exactly
    at a limit stays at that level."""
    if total_dh <= rules.dh("refunds.approval_limits_qar.agent"):
        return "agent"
    if total_dh <= rules.dh("refunds.approval_limits_qar.supervisor"):
        return "supervisor"
    return "finance_lead"


def automated_limit_dh(rules: Rules, account_age_days: int) -> int:
    if account_age_days < int(rules.get("refunds.new_account.age_days")):
        return rules.dh("refunds.new_account.automated_limit_qar")
    return rules.dh("refunds.approval_limits_qar.automated")


def remaining_refundable_dh(order: OrderFacts, claims: ClaimFacts) -> int:
    """REF-03 cap: refunds on one order can never exceed the amount paid."""
    return max(order.paid_dh - claims.refunded_on_order_dh - claims.credit_on_order_dh, 0)


def photo_needed(rules: Rules, reason: str, amount_dh: int) -> bool:
    """REF-06."""
    if reason in PHOTO_ALWAYS:
        return True
    return reason in PHOTO_ABOVE_LIMIT and amount_dh > rules.dh("refunds.photo.required_above_qar")


def duplicate_amount_dh(order: OrderFacts) -> int:
    """PAY-03: two final charges of the same amount on one order. A hold plus a final
    charge is not a duplicate. Returns the extra amount taken, or 0."""
    finals: dict[int, int] = {}
    for _at, amount, kind in order.charges:
        if kind == "final":
            finals[amount] = finals.get(amount, 0) + 1
    extra = [amount * (count - 1) for amount, count in finals.items() if count > 1]
    return max(extra, default=0)


def duplicate_in_window(rules: Rules, order: OrderFacts, now: datetime) -> bool:
    days = int(rules.get("payments.duplicate_charge.window_days"))
    latest = max((at for at, _amount, kind in order.charges if kind == "final"), default=None)
    return latest is not None and now - latest <= timedelta(days=days)


def _decide_duplicate(rules: Rules, order: OrderFacts, amount_dh: int, now: datetime) -> Decision:
    extra = duplicate_amount_dh(order)
    if extra == 0:
        return Decision(DENY, "no_duplicate_charge_found")
    if not duplicate_in_window(rules, order, now):
        return Decision(DENY, "outside_reporting_window")
    if amount_dh > extra:
        return Decision(DENY, "amount_exceeds_paid", limit_dh=extra)
    # A pharmacy refund always needs a person, yet PAY-03 automates a confirmed
    # duplicate. The documents do not say which wins.
    if order.category == "pharmacy":
        return Decision(ESCALATE, "duplicate_on_pharmacy_order")
    # Separate from REF-05, because the money was never owed.
    if amount_dh <= rules.dh("payments.duplicate_charge.automated_limit_qar"):
        return Decision(EXECUTE, "confirmed_duplicate")
    return Decision(APPROVAL, "above_duplicate_limit", approval_role(rules, amount_dh))


def decide_refund(
    rules: Rules,
    order: OrderFacts,
    claims: ClaimFacts,
    amount_dh: int,
    reason: str,
    now: datetime,
    *,
    photo_provided: bool = False,
) -> Decision:
    if amount_dh <= 0:
        return Decision(DENY, "amount_must_be_positive")
    if reason not in ALL_REFUND_REASONS:
        return Decision(DENY, "reason_not_refundable")
    # GEN-04 step 2: a block stops a refund before any other rule is looked at.
    if order.open_bank_dispute:
        return Decision(DENY, "bank_dispute_open")
    if reason == "duplicate_charge":
        return _decide_duplicate(rules, order, amount_dh, now)

    if reason == "failed_contact_refund":
        if order.status != "failed_customer":
            return Decision(DENY, "order_not_failed")
    elif order.status != "delivered":
        return Decision(DENY, "order_not_delivered")
    elif reason == "expired_product" and order.cold_chain:
        # Expired products have 7 days and cold-chain products 2 hours.
        return Decision(ESCALATE, "expired_cold_chain_window")
    elif not in_window(rules, reason, order, now):
        return Decision(DENY, "outside_reporting_window", detail={"window_hours": window_hours(rules, reason, order.category)})

    available = remaining_refundable_dh(order, claims)
    if amount_dh > available:
        return Decision(DENY, "amount_exceeds_paid", limit_dh=available)

    safety = reason in SAFETY_REASONS
    # The pause is clear, but what the customer is owed during it is not, so a person decides.
    if claims.claims_90d >= int(rules.get("refunds.trust_review.from_prior_claims")) and not safety:
        return Decision(ESCALATE, "trust_review_pause")

    total = claims.refunded_on_order_dh + claims.credit_on_order_dh + amount_dh
    role = approval_role(rules, total)

    # Always a person, at any amount (REF-05).
    if order.category == "pharmacy":
        return Decision(APPROVAL, "pharmacy_needs_person", role)
    if safety:
        return Decision(APPROVAL, "safety_needs_person", role)
    if order.category == "parcel":
        return Decision(APPROVAL, "parcel_needs_person", role)
    if reason == "not_received":
        if claims.not_received_90d >= int(rules.get("not_received.max_refunds")):
            return Decision(APPROVAL, "not_received_limit", role)
        close = order.gps_distance_m is not None and order.gps_distance_m <= int(rules.get("not_received.gps_radius_m"))
        if order.proof_of_delivery and close:
            return Decision(APPROVAL, "proof_of_delivery_exists", role)

    # REF-06: the photo may follow up to a day after the report, so a missing photo
    # never refuses a claim. The claim waits with a person until it arrives.
    if photo_needed(rules, reason, amount_dh) and not photo_provided:
        return Decision(APPROVAL, "photo_needed", role)

    repeat_count = int(rules.get("refunds.repeat_claims.agent_review_from_prior_claims"))
    repeat_total = rules.dh("refunds.repeat_claims.agent_review_above_total_qar")
    counted = reason not in NOT_CLAIMS
    if counted and (claims.claims_30d >= repeat_count or claims.claims_total_30d_dh + amount_dh > repeat_total):
        return Decision(APPROVAL, "repeat_claims", role)

    limit = automated_limit_dh(rules, claims.account_age_days)
    if total <= limit:
        return Decision(EXECUTE, "within_automated_limit", limit_dh=limit)
    return Decision(APPROVAL, "above_automated_limit", role, limit_dh=limit)


def failed_contact_refund_dh(rules: Rules, order: OrderFacts) -> int:
    """LAT-05 for a properly failed contact."""
    net = order.net_items_dh
    if order.category == "food":
        return order.tip_dh
    if order.category == "grocery":
        charge = percent_of(net, rules.get("cancellations.grocery.picking_charge_pct"))
        charge = max(charge, rules.dh("cancellations.grocery.picking_charge_min_qar"))
        charge = min(charge, rules.dh("cancellations.grocery.picking_charge_max_qar"), net)
        return net - charge + order.tip_dh
    if order.category == "pharmacy":
        return max(net - rules.dh("cancellations.pharmacy.packed_charge_qar"), 0) + order.tip_dh
    return 0


def late_entitlement(rules: Rules, order: OrderFacts, now: datetime) -> dict[str, int]:
    """LAT-01 and LAT-02. Returns credit and delivery fee refund in dirhams."""
    nothing = {"credit_dh": 0, "fee_refund_dh": 0, "minutes_late": minutes_late(order, now)}
    if order.status != "delivered" or order.category == "parcel":
        return nothing
    if order.severe_weather or order.failed_contact:
        return nothing
    late = nothing["minutes_late"]
    shift = int(rules.get("late_delivery.iftar_tier_shift_minutes")) if order.iftar_window else 0
    chosen = None
    for tier in rules.get("late_delivery.tiers"):
        if late >= int(tier["min_minutes"]) + shift:
            chosen = tier
    if chosen is None:
        return nothing
    cap = percent_of(order.refund_subtotal_dh, rules.get("late_delivery.credit_cap_pct_of_item_subtotal"))
    return {
        "credit_dh": min(to_dh(chosen["credit_qar"]), cap),
        "fee_refund_dh": order.delivery_fee_dh if chosen["refund_delivery_fee"] else 0,
        "minutes_late": late,
    }


def decide_credit(
    rules: Rules,
    order: OrderFacts,
    claims: ClaimFacts,
    amount_dh: int,
    reason: str,
    now: datetime,
) -> Decision:
    if amount_dh <= 0:
        return Decision(DENY, "amount_must_be_positive")
    if reason not in CREDIT_REASONS:
        return Decision(DENY, "reason_not_creditable")

    per_order = rules.dh("compensation_credit_cap_per_order_qar")
    room = per_order - claims.credit_on_order_dh
    if amount_dh > room:
        return Decision(DENY, "credit_cap_per_order", limit_dh=max(room, 0))
    if claims.wallet_dh + amount_dh > rules.dh("credit_wallet.max_balance_qar"):
        return Decision(ESCALATE, "wallet_at_limit")

    if reason == "late_delivery":
        if order.status != "delivered":
            return Decision(DENY, "order_not_delivered")
        since = hours_since(order.delivered_at, now)
        if since is None or since > float(rules.get("refunds.windows_hours.late_credit")):
            return Decision(DENY, "outside_reporting_window")
        entitled = late_entitlement(rules, order, now)["credit_dh"]
        if entitled == 0:
            return Decision(DENY, "no_late_credit_due")
        if amount_dh > entitled:
            return Decision(DENY, "above_late_credit_due", limit_dh=entitled)
        return Decision(EXECUTE, "late_credit_due", limit_dh=entitled)

    # Goodwill (REF-07).
    if claims.claims_90d >= int(rules.get("refunds.trust_review.from_prior_claims")):
        return Decision(DENY, "trust_review")
    if claims.goodwill_30d_dh + amount_dh > rules.dh("goodwill.max_per_customer_30d_qar"):
        return Decision(DENY, "goodwill_cap_30d")
    if amount_dh > rules.dh("goodwill.automated_max_qar"):
        return Decision(APPROVAL, "goodwill_above_automated", "agent")
    return Decision(EXECUTE, "within_goodwill_limit")


def cancellation_terms(rules: Rules, order: OrderFacts, now: datetime) -> dict[str, Any]:
    """CAN-01 to CAN-04. Returns allowed, charge_dh, refund_dh and the rule that applied."""
    paid, tip, net = order.paid_dh, order.tip_dh, order.net_items_dh
    if order.status in rules.get("general.terminal_statuses"):
        return {"allowed": False, "code": "order_already_finished", "charge_dh": 0, "refund_dh": 0}

    late = minutes_late(order, now)
    free_exit = int(rules.get("late_delivery.free_cancel_after_minutes_late"))
    if order.promised_at is not None and late >= free_exit:
        return {"allowed": True, "code": "late_free_cancel", "charge_dh": 0, "refund_dh": paid}
    slip = int(rules.get("late_delivery.eta_slip_free_cancel_minutes"))
    early_stage = order.status not in {"picked_up", "on_the_way"}
    if order.estimate_at and order.promised_at and early_stage:
        if (order.estimate_at - order.promised_at) >= timedelta(minutes=slip):
            return {"allowed": True, "code": "eta_slip_free_cancel", "charge_dh": 0, "refund_dh": paid}

    in_grace = (now - order.placed_at) <= timedelta(minutes=int(rules.get("cancellations.grace_minutes")))
    if in_grace and order.category != "parcel" and early_stage:
        return {"allowed": True, "code": "grace_period", "charge_dh": 0, "refund_dh": paid}

    charge = _status_charge(rules, order, net)
    if charge is None:
        return {"allowed": False, "code": "cannot_cancel_now", "charge_dh": 0, "refund_dh": 0}
    charge = min(charge, paid - tip)
    # A charge on a cash order part-paid with credit has no written order of recovery.
    if charge > 0 and order.payment_method == "cash" and order.credit_paid_dh > 0:
        return {"allowed": False, "code": "cash_and_credit_charge", "escalate": True, "charge_dh": 0, "refund_dh": 0}
    return {"allowed": True, "code": "standard", "charge_dh": charge, "refund_dh": paid - charge}


def _status_charge(rules: Rules, order: OrderFacts, net: int) -> int | None:
    status, category = order.status, order.category
    all_but_tip = order.paid_dh - order.tip_dh
    if category == "food":
        if status == "placed":
            return 0
        if status in {"accepted", "preparing"}:
            return percent_of(net, rules.get("cancellations.food.preparing_charge_pct"))
        return all_but_tip
    if category == "grocery":
        if status in {"placed", "accepted"}:
            return 0
        if status == "picking":
            charge = percent_of(net, rules.get("cancellations.grocery.picking_charge_pct"))
            charge = max(charge, rules.dh("cancellations.grocery.picking_charge_min_qar"))
            charge = min(charge, rules.dh("cancellations.grocery.picking_charge_max_qar"))
            return min(charge, net)
        return all_but_tip
    if category == "pharmacy":
        if status in {"placed", "accepted"}:
            return 0
        if status == "packed":
            return min(rules.dh("cancellations.pharmacy.packed_charge_qar"), net)
        return all_but_tip
    if status == "placed":
        return 0
    if status == "driver_assigned":
        return rules.dh("cancellations.parcel.driver_assigned_charge_qar")
    return None


def promo_decision(
    rules: Rules,
    code: str,
    *,
    order_placed: bool,
    category: str,
    eligible_subtotal_dh: int,
    now: datetime,
    used_this_month: bool = False,
    used_ever: bool = False,
    has_delivered_order: bool = False,
) -> Decision:
    """PRM-01. A code can only be added before an order is placed, so support can check
    a code but cannot put one on an existing order."""
    codes = rules.get("promos.codes")
    promo = codes.get(code.strip().upper())
    if promo is None:
        return Decision(DENY, "unknown_code")
    valid_until = promo.get("valid_until")
    if valid_until and now.date().isoformat() > valid_until:
        return Decision(DENY, "code_expired")
    if order_placed:
        return Decision(DENY, "code_cannot_be_added_after_placing")
    if category not in promo["verticals"]:
        return Decision(DENY, "code_not_for_this_category")
    minimum = promo.get("min_spend_qar")
    if minimum is not None and eligible_subtotal_dh < to_dh(minimum):
        return Decision(DENY, "below_minimum_spend", limit_dh=to_dh(minimum))
    limit = promo.get("limit")
    if limit == "first_delivered_order" and has_delivered_order:
        return Decision(DENY, "code_already_used")
    if limit == "once_per_calendar_month" and used_this_month:
        return Decision(DENY, "code_already_used")
    if limit == "once_per_account" and used_ever:
        return Decision(DENY, "code_already_used")
    return Decision(EXECUTE, "code_valid")


def promo_discount_dh(rules: Rules, code: str, eligible_subtotal_dh: int, delivery_fee_dh: int) -> int:
    promo = rules.get("promos.codes")[code.strip().upper()]
    if promo["type"] == "free_delivery":
        return delivery_fee_dh
    if promo["type"] == "fixed":
        return min(to_dh(promo["value"]), eligible_subtotal_dh)
    discount = percent_of(eligible_subtotal_dh, promo["value"])
    return min(discount, to_dh(promo["max_discount_qar"]))


def net_item_refund_dh(order: OrderFacts, item: ItemFact, quantity: int) -> int:
    """GEN-03: the listed price less the item's share of the promo discount, rounded
    half up once per line."""
    eligible = sum(i.unit_dh * i.quantity for i in order.items if i.promo_eligible)
    listed = item.unit_dh * quantity
    if not item.promo_eligible or eligible == 0 or order.discount_dh == 0:
        return listed
    value = Decimal(listed) * (1 - Decimal(order.discount_dh) / Decimal(eligible))
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def full_refund_applies(rules: Rules, order: OrderFacts, affected: Sequence[tuple[ItemFact, int]]) -> bool:
    """REF-03 step 2: exactly 70 percent converts."""
    if order.subtotal_dh == 0:
        return False
    listed = sum(item.unit_dh * quantity for item, quantity in affected)
    return listed * 100 >= order.subtotal_dh * int(rules.get("refunds.full_refund_conversion_pct"))


def full_refund_dh(order: OrderFacts, claims: ClaimFacts, delivered: bool = True) -> int:
    """GEN-03: the amount paid, less the tip if the order was delivered, less refunds
    and compensation credit already given."""
    tip = order.tip_dh if delivered else 0
    return max(order.paid_dh - tip - claims.refunded_on_order_dh - claims.credit_on_order_dh, 0)
