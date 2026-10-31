"""The expected numbers here come from the worked examples in the policy documents
(REF-09, CAN-01, LAT-01), so these tests fail if the code drifts from the written policy."""

from datetime import datetime, timedelta, timezone
import pytest

from jalboot.policy import engine
from jalboot.policy.engine import APPROVAL, DENY, ESCALATE, EXECUTE, ClaimFacts, ItemFact, OrderFacts
from jalboot.policy.rules import Rules, percent_of, to_dh, to_qar

RULES = Rules.load()

NOW = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)
BURGER = ItemFact("Burger", 1, 4000)
FRIES = ItemFact("Fries", 1, 2000)
JUICE = ItemFact("Juice", 1, 4000)


def base_order(**overrides):
    """The base order of REF-09: items 100, code 20, delivery 8, service 3, tip 5."""
    values = dict(
        id="Q-1", category="food", status="delivered",
        placed_at=NOW - timedelta(hours=2), promised_at=NOW - timedelta(hours=1),
        delivered_at=NOW - timedelta(hours=1),
        subtotal_dh=10000, discount_dh=2000, delivery_fee_dh=800, other_fees_dh=300, tip_dh=500,
        items=(BURGER, FRIES, JUICE),
    )
    values.update(overrides)
    return OrderFacts(**values)


def refund(amount_qar, reason="missing_item", order=None, claims=ClaimFacts(), **kwargs):
    return engine.decide_refund(RULES, order or base_order(), claims, to_dh(amount_qar), reason, NOW, **kwargs)


def test_money_rounds_half_up_without_float_error():
    assert to_dh("0.1") == 10
    assert to_dh(16.005) == 1601
    assert percent_of(1050, 50) == 525
    assert to_qar(1600) == 16.0


def test_amount_paid_matches_the_worked_example():
    assert base_order().paid_dh == 9600


def test_ref09_example_1_net_price_of_the_missing_fries():
    order = base_order()
    assert engine.net_item_refund_dh(order, FRIES, 1) == 1600
    assert refund(16).outcome == EXECUTE


def test_ref09_example_2_seventy_percent_rule_and_full_refund():
    order = base_order()
    assert engine.full_refund_applies(RULES, order, [(BURGER, 1), (JUICE, 1)])
    assert engine.full_refund_dh(order, ClaimFacts()) == 9100
    decision = refund(91, "wrong_item", photo_provided=True)
    assert decision.outcome == APPROVAL
    assert decision.code == "above_automated_limit"
    assert decision.required_role == "agent"


def test_exactly_seventy_percent_converts_and_just_below_does_not():
    order = base_order(subtotal_dh=10000)
    assert engine.full_refund_applies(RULES, order, [(ItemFact("x", 1, 7000), 1)])
    assert not engine.full_refund_applies(RULES, order, [(ItemFact("x", 1, 6999), 1)])


def test_ref09_example_3_late_credit_capped_at_thirty_percent():
    order = base_order(
        subtotal_dh=2000, discount_dh=0, delivery_fee_dh=500, other_fees_dh=0, tip_dh=0,
        promised_at=NOW - timedelta(hours=2), delivered_at=NOW - timedelta(minutes=55),
    )
    result = engine.late_entitlement(RULES, order, NOW)
    assert result["minutes_late"] == 65
    assert result["credit_dh"] == 600
    assert result["fee_refund_dh"] == 500


def test_ref09_example_5_credit_already_issued_reduces_the_full_refund():
    assert engine.full_refund_dh(base_order(), ClaimFacts(credit_on_order_dh=1000)) == 8100


@pytest.mark.parametrize("late,credit", [(19, 0), (20, 500), (39, 500), (40, 1000), (59, 1000), (60, 2000)])
def test_late_tier_boundaries(late, credit):
    order = base_order(promised_at=NOW - timedelta(hours=3), delivered_at=NOW - timedelta(hours=3) + timedelta(minutes=late))
    assert engine.late_entitlement(RULES, order, NOW)["credit_dh"] == credit


def test_only_the_top_late_tier_refunds_the_delivery_fee():
    middle = base_order(promised_at=NOW - timedelta(hours=3), delivered_at=NOW - timedelta(hours=2, minutes=15))
    top = base_order(promised_at=NOW - timedelta(hours=3), delivered_at=NOW - timedelta(hours=1, minutes=50))
    assert engine.late_entitlement(RULES, middle, NOW)["fee_refund_dh"] == 0
    assert engine.late_entitlement(RULES, top, NOW)["fee_refund_dh"] == 800


def test_iftar_window_moves_each_tier_ten_minutes():
    start = NOW - timedelta(hours=3)
    normal = base_order(promised_at=start, delivered_at=start + timedelta(minutes=25))
    iftar = base_order(promised_at=start, delivered_at=start + timedelta(minutes=25), iftar_window=True)
    assert engine.late_entitlement(RULES, normal, NOW)["credit_dh"] == 500
    assert engine.late_entitlement(RULES, iftar, NOW)["credit_dh"] == 0


@pytest.mark.parametrize("flag", ["severe_weather", "failed_contact"])
def test_no_late_credit_with_an_exception(flag):
    start = NOW - timedelta(hours=3)
    order = base_order(promised_at=start, delivered_at=start + timedelta(minutes=70), **{flag: True})
    assert engine.late_entitlement(RULES, order, NOW)["credit_dh"] == 0


def test_a_refund_at_exactly_the_automated_limit_is_automatic_and_one_dirham_more_is_not():
    assert refund(50).outcome == EXECUTE
    assert refund("50.01").outcome == APPROVAL


def test_prior_value_on_the_order_counts_toward_the_limit():
    decision = refund(30, claims=ClaimFacts(refunded_on_order_dh=3000))
    assert decision.outcome == APPROVAL


def test_new_accounts_have_a_lower_automated_limit():
    assert refund(25, claims=ClaimFacts(account_age_days=3)).outcome == EXECUTE
    assert refund(26, claims=ClaimFacts(account_age_days=3)).outcome == APPROVAL


@pytest.mark.parametrize("total,role", [(300, "agent"), ("300.01", "supervisor"), (1500, "supervisor"), (1501, "finance_lead")])
def test_approval_levels(total, role):
    assert engine.approval_role(RULES, to_dh(total)) == role


def test_refund_cannot_exceed_what_was_paid():
    decision = refund(97)
    assert decision.outcome == DENY
    assert decision.code == "amount_exceeds_paid"


def test_refund_cannot_exceed_what_is_left_after_earlier_refunds():
    assert refund(90, claims=ClaimFacts(refunded_on_order_dh=1000)).code == "amount_exceeds_paid"


def test_refund_needs_a_positive_amount():
    assert refund(0).code == "amount_must_be_positive"
    assert refund(-5).code == "amount_must_be_positive"


def test_an_undelivered_order_is_not_refunded_as_a_claim():
    assert refund(10, order=base_order(status="on_the_way", delivered_at=None)).code == "order_not_delivered"


@pytest.mark.parametrize("hours,outcome", [(24, EXECUTE), (24.02, DENY)])
def test_reporting_window_end_is_inclusive(hours, outcome):
    order = base_order(delivered_at=NOW - timedelta(hours=hours))
    assert refund(10, order=order).outcome == outcome


def test_a_specific_window_beats_the_general_one():
    order = base_order(delivered_at=NOW - timedelta(hours=3))
    assert refund(10, "cold_food", order=order).code == "outside_reporting_window"
    assert refund(10, "missing_item", order=order).outcome == EXECUTE


def test_pharmacy_refunds_always_need_a_person():
    decision = refund(5, order=base_order(category="pharmacy"))
    assert decision.outcome == APPROVAL
    assert decision.code == "pharmacy_needs_person"


def test_safety_cases_always_need_a_person_and_pass_a_trust_review():
    decision = refund(5, "allergen", claims=ClaimFacts(claims_90d=20))
    assert decision.outcome == APPROVAL
    assert decision.code == "safety_needs_person"


def test_repeat_claims_go_to_an_agent():
    assert refund(5, claims=ClaimFacts(claims_30d=3)).code == "repeat_claims"
    assert refund(5, claims=ClaimFacts(claims_30d=2)).outcome == EXECUTE


def test_claims_over_the_thirty_day_total_go_to_an_agent():
    assert refund(10, claims=ClaimFacts(claims_total_30d_dh=29500)).code == "repeat_claims"


def test_a_trust_review_stops_the_bot_and_goes_to_a_person():
    decision = refund(5, claims=ClaimFacts(claims_90d=8))
    assert decision.outcome == ESCALATE
    assert decision.code == "trust_review_pause"


def test_a_missing_photo_sends_the_claim_to_a_person_and_never_refuses_it():
    for decision in (refund(31, "wrong_item"), refund(5, "expired_product")):
        assert decision.outcome == APPROVAL
        assert decision.code == "photo_needed"


def test_no_photo_is_needed_at_or_below_the_threshold_or_for_missing_items():
    assert refund(30, "wrong_item").outcome == EXECUTE
    assert refund(45, "missing_item").outcome == EXECUTE
    assert refund(31, "wrong_item", photo_provided=True).outcome == EXECUTE


def charged(*amounts, kinds=None):
    at = NOW - timedelta(days=3)
    kinds = kinds or ["final"] * len(amounts)
    return tuple((at + timedelta(minutes=i), amount, kinds[i]) for i, amount in enumerate(amounts))


def test_pay03_duplicate_has_its_own_limit_and_needs_no_photo():
    order = base_order(charges=charged(17280, 17280), subtotal_dh=30000)
    assert refund("172.80", "duplicate_charge", order=order).outcome == EXECUTE


def test_pay03_duplicate_above_three_hundred_needs_a_person():
    order = base_order(charges=charged(40000, 40000), subtotal_dh=60000)
    assert refund(400, "duplicate_charge", order=order).outcome == APPROVAL


def test_pay03_a_hold_plus_a_final_charge_is_not_a_duplicate():
    order = base_order(charges=charged(9600, 9600, kinds=["hold", "final"]))
    assert refund(96, "duplicate_charge", order=order).code == "no_duplicate_charge_found"


def test_pay03_refund_cannot_exceed_the_extra_charge():
    order = base_order(charges=charged(5000, 5000), subtotal_dh=60000)
    assert refund(60, "duplicate_charge", order=order).code == "amount_exceeds_paid"


def test_pay03_window():
    old = tuple((NOW - timedelta(days=31), amount, "final") for amount in (5000, 5000))
    assert refund(50, "duplicate_charge", order=base_order(charges=old)).code == "outside_reporting_window"


def test_gen04_a_bank_dispute_blocks_before_any_other_rule():
    assert refund(5, order=base_order(open_bank_dispute=True)).code == "bank_dispute_open"
    order = base_order(open_bank_dispute=True, charges=charged(5000, 5000))
    assert refund(50, "duplicate_charge", order=order).code == "bank_dispute_open"


def test_late_fee_refunds_do_not_trigger_repeat_claim_review():
    assert refund(8, "late_delivery_fee", claims=ClaimFacts(claims_30d=5)).outcome == EXECUTE


def test_ambiguous_rule_pairs_go_to_a_person_and_never_pay():
    pharmacy = base_order(category="pharmacy", charges=charged(5000, 5000))
    assert refund(50, "duplicate_charge", order=pharmacy).outcome == ESCALATE
    cold = base_order(cold_chain=True)
    assert refund(10, "expired_product", order=cold).outcome == ESCALATE
    full = ClaimFacts(wallet_dh=199800)
    assert engine.decide_credit(RULES, base_order(), full, 500, "goodwill", NOW).outcome == ESCALATE


def test_a_charge_on_a_cash_order_part_paid_with_credit_is_not_guessed():
    order = base_order(status="preparing", delivered_at=None, payment_method="cash", credit_paid_dh=2000,
                       placed_at=NOW - timedelta(minutes=10), promised_at=NOW + timedelta(minutes=20))
    terms = engine.cancellation_terms(RULES, order, NOW)
    assert terms["allowed"] is False
    assert terms["escalate"] is True


def test_gen03_late_credit_cap_uses_the_final_subtotal():
    start = NOW - timedelta(hours=3)
    order = base_order(subtotal_dh=10000, final_subtotal_dh=2000, discount_dh=0,
                       promised_at=start, delivered_at=start + timedelta(minutes=70))
    assert engine.late_entitlement(RULES, order, NOW)["credit_dh"] == 600


def test_goodwill_does_not_use_up_late_credit():
    start = NOW - timedelta(hours=3)
    order = base_order(promised_at=start, delivered_at=start + timedelta(minutes=25))
    assert engine.late_credit_due_dh(RULES, order, ClaimFacts(credit_on_order_dh=500), NOW) == 500


def test_lat05_failed_contact_amounts():
    food = base_order(status="failed_customer")
    assert engine.failed_contact_refund_dh(RULES, food) == 500
    grocery = base_order(status="failed_customer", category="grocery")
    assert engine.failed_contact_refund_dh(RULES, grocery) == 8000 - 1200 + 500
    pharmacy = base_order(status="failed_customer", category="pharmacy")
    assert engine.failed_contact_refund_dh(RULES, pharmacy) == 8000 - 1000 + 500


def test_not_received_with_nearby_proof_needs_a_person():
    order = base_order(proof_of_delivery=True, gps_distance_m=150)
    assert refund(10, "not_received", order=order).code == "proof_of_delivery_exists"


def test_not_received_with_far_proof_is_treated_as_not_delivered():
    order = base_order(proof_of_delivery=True, gps_distance_m=151)
    assert refund(10, "not_received", order=order).outcome == EXECUTE


def test_third_not_received_refund_goes_to_a_person_even_without_proof():
    assert refund(10, "not_received", claims=ClaimFacts(not_received_90d=2)).code == "not_received_limit"


def test_compensation_credit_cap_per_order():
    decision = engine.decide_credit(
        RULES, base_order(), ClaimFacts(credit_on_order_dh=2000), 1500, "goodwill", NOW
    )
    assert decision.code == "credit_cap_per_order"
    assert decision.limit_dh == 1000


def test_goodwill_limits():
    assert engine.decide_credit(RULES, base_order(), ClaimFacts(), 1000, "goodwill", NOW).outcome == EXECUTE
    assert engine.decide_credit(RULES, base_order(), ClaimFacts(), 1001, "goodwill", NOW).outcome == APPROVAL
    capped = ClaimFacts(goodwill_30d_dh=5500)
    assert engine.decide_credit(RULES, base_order(), capped, 1000, "goodwill", NOW).code == "goodwill_cap_30d"


def test_late_credit_cannot_be_more_than_is_due():
    start = NOW - timedelta(hours=3)
    order = base_order(promised_at=start, delivered_at=start + timedelta(minutes=25))
    assert engine.decide_credit(RULES, order, ClaimFacts(), 500, "late_delivery", NOW).outcome == EXECUTE
    assert engine.decide_credit(RULES, order, ClaimFacts(), 600, "late_delivery", NOW).code == "above_credit_due"


def test_wallet_at_its_limit_is_not_paid():
    claims = ClaimFacts(wallet_dh=199800)
    assert engine.decide_credit(RULES, base_order(), claims, 500, "goodwill", NOW).code == "wallet_at_limit"


def cancel(status, **overrides):
    order = base_order(
        status=status, delivered_at=None, placed_at=NOW - timedelta(minutes=10),
        promised_at=NOW + timedelta(minutes=20), **overrides,
    )
    return engine.cancellation_terms(RULES, order, NOW)


def test_can01_example_preparing_and_ready():
    assert cancel("preparing")["charge_dh"] == 4000
    assert cancel("preparing")["refund_dh"] == 5600
    assert cancel("ready")["refund_dh"] == 500


def test_cancelling_a_placed_order_is_free():
    assert cancel("placed")["charge_dh"] == 0


def test_grace_period_is_free_before_pickup():
    order = base_order(status="preparing", delivered_at=None, placed_at=NOW - timedelta(minutes=2), promised_at=NOW + timedelta(minutes=20))
    assert engine.cancellation_terms(RULES, order, NOW)["code"] == "grace_period"


def test_parcels_have_no_grace_period_and_cannot_cancel_after_pickup():
    order = base_order(category="parcel", status="driver_assigned", delivered_at=None,
                       placed_at=NOW - timedelta(minutes=1), promised_at=NOW + timedelta(hours=3))
    assert engine.cancellation_terms(RULES, order, NOW)["charge_dh"] == 500
    picked = base_order(category="parcel", status="picked_up", delivered_at=None,
                        placed_at=NOW - timedelta(minutes=30), promised_at=NOW + timedelta(hours=3))
    assert engine.cancellation_terms(RULES, picked, NOW)["code"] == "cannot_cancel_now"


def test_grocery_picking_charge_has_a_floor():
    order = base_order(category="grocery", status="picking", delivered_at=None, subtotal_dh=5000,
                       discount_dh=0, placed_at=NOW - timedelta(minutes=10), promised_at=NOW + timedelta(minutes=40))
    assert engine.cancellation_terms(RULES, order, NOW)["charge_dh"] == 1000


def test_free_exit_at_forty_five_minutes_late_even_on_the_way():
    order = base_order(status="on_the_way", delivered_at=None, placed_at=NOW - timedelta(hours=2),
                       promised_at=NOW - timedelta(minutes=45))
    terms = engine.cancellation_terms(RULES, order, NOW)
    assert terms["code"] == "late_free_cancel"
    assert terms["refund_dh"] == 9600


def test_a_finished_order_cannot_be_cancelled():
    assert not engine.cancellation_terms(RULES, base_order(), NOW)["allowed"]


def promo(code, **overrides):
    values = dict(order_placed=False, category="food", eligible_subtotal_dh=10000, now=NOW)
    values.update(overrides)
    return engine.promo_decision(RULES, code, **values)


def test_a_valid_code_passes():
    assert promo("SAVE20").outcome == EXECUTE


def test_a_code_cannot_be_added_after_the_order_is_placed():
    assert promo("SAVE20", order_placed=True).code == "code_cannot_be_added_after_placing"


def test_an_expired_code_fails_before_anything_else():
    assert promo("SUMMER25", order_placed=True).code == "code_expired"


def test_codes_are_case_insensitive_and_unknown_codes_fail():
    assert promo("save20").outcome == EXECUTE
    assert promo("NOPE").code == "unknown_code"


def test_minimum_spend_and_category():
    assert promo("SAVE20", eligible_subtotal_dh=5999).code == "below_minimum_spend"
    assert promo("GROCERY15").code == "code_not_for_this_category"


def test_usage_limits():
    assert promo("SAVE20", used_this_month=True).code == "code_already_used"
    assert promo("WELCOME40", has_delivered_order=True).code == "code_already_used"


def test_percent_discounts_have_a_ceiling():
    assert engine.promo_discount_dh(RULES, "SAVE20", 10000, 800) == 2000
    assert engine.promo_discount_dh(RULES, "SAVE20", 50000, 800) == 2500
    assert engine.promo_discount_dh(RULES, "FREEDROP", 10000, 800) == 800


def scheduled(status="placed", minutes_to_slot=119, category="grocery"):
    return base_order(
        category=category, status=status, delivered_at=None, discount_dh=0, placed_at=NOW - timedelta(hours=3),
        promised_at=NOW + timedelta(hours=3), scheduled_slot_at=NOW + timedelta(minutes=minutes_to_slot),
    )


def test_can03_past_the_scheduled_limit_the_stage_charge_applies():
    terms = engine.cancellation_terms(RULES, scheduled(), NOW)
    assert terms["code"] == "scheduled_late"
    assert terms["charge_dh"] == 1500


def test_can03_cancelling_exactly_at_the_limit_is_free():
    assert engine.cancellation_terms(RULES, scheduled(minutes_to_slot=120), NOW)["charge_dh"] == 0


def test_can05_a_cash_order_returns_nothing_and_caps_the_balance():
    order = base_order(status="preparing", delivered_at=None, payment_method="cash", subtotal_dh=8000, discount_dh=0,
                       placed_at=NOW - timedelta(minutes=10), promised_at=NOW + timedelta(minutes=20))
    terms = engine.cancellation_terms(RULES, order, NOW)
    assert terms["charge_dh"] == 3000
    assert terms["refund_dh"] == 0


def test_can05_a_small_cash_charge_stays_as_it_is():
    order = base_order(status="preparing", delivered_at=None, payment_method="cash", subtotal_dh=4000, discount_dh=0,
                       placed_at=NOW - timedelta(minutes=10), promised_at=NOW + timedelta(minutes=20))
    assert engine.cancellation_terms(RULES, order, NOW)["charge_dh"] == 2000


def test_can01_the_status_at_the_first_request_sets_the_charge():
    order = base_order(status="picked_up", delivered_at=None, status_at_first_request="accepted",
                       placed_at=NOW - timedelta(minutes=10), promised_at=NOW + timedelta(minutes=20))
    assert engine.cancellation_terms(RULES, order, NOW)["charge_dh"] == 4000


def test_can04_cancellation_credit_needs_a_merchant_cancellation_after_thirty_minutes():
    placed = NOW - timedelta(hours=2)

    def order(minutes, by="merchant"):
        return base_order(status="cancelled", delivered_at=None, placed_at=placed, cancelled_by=by,
                          cancelled_at=placed + timedelta(minutes=minutes))

    credit = lambda o: engine.decide_credit(RULES, o, ClaimFacts(), 1000, "cancellation_credit", NOW)  # noqa: E731
    assert credit(order(30)).outcome == EXECUTE
    assert credit(order(29)).code == "no_cancellation_credit_due"
    assert credit(order(40, "customer")).code == "no_cancellation_credit_due"


def test_grc05_expired_item_credit_is_limited_and_in_window():
    def credit(order, amount):
        return engine.decide_credit(RULES, order, ClaimFacts(), amount, "expired_item_credit", NOW, photo_provided=True)

    order = base_order(category="grocery", delivered_at=NOW - timedelta(days=3))
    assert credit(order, 1000).outcome == EXECUTE
    assert credit(order, 1100).outcome == DENY
    old = base_order(category="grocery", delivered_at=NOW - timedelta(days=8))
    assert credit(old, 1000).code == "no_expired_item_credit_due"


def failed(**overrides):
    values = dict(status="failed_customer", delivered_at=None, failed_contact=True, driver_wait_minutes=8, driver_calls=2)
    values.update(overrides)
    return base_order(**values)


def test_lat05_a_short_wait_means_a_full_refund_with_the_tip():
    assert engine.failed_contact_refund_dh(RULES, failed(driver_wait_minutes=4)) == 9600


def test_lat05_too_few_calls_means_a_full_refund():
    assert engine.failed_contact_refund_dh(RULES, failed(driver_calls=1)) == 9600


def test_lat05_a_proper_attempt_returns_only_the_tip():
    assert engine.failed_contact_refund_dh(RULES, failed()) == 500


def test_drv04_leaving_for_safety_is_not_a_short_wait():
    assert engine.failed_contact_refund_dh(RULES, failed(driver_wait_minutes=3, left_for_safety=True)) == 500


def test_pay04_a_change_shortfall_is_paid_up_to_what_is_on_record():
    order = base_order(payment_method="cash", change_short_dh=1500)
    assert refund(15, "driver_change_short", order=order).outcome == EXECUTE
    assert refund(16, "driver_change_short", order=order).code == "amount_exceeds_paid"
    assert refund(5, "driver_change_short").code == "no_change_shortfall_recorded"


def test_late_credit_paid_before_is_not_paid_again():
    start = NOW - timedelta(hours=3)
    order = base_order(promised_at=start, delivered_at=start + timedelta(minutes=25))
    claims = ClaimFacts(credit_on_order_dh=500, late_credit_on_order_dh=500)
    assert engine.decide_credit(RULES, order, claims, 500, "late_delivery", NOW).code == "late_credit_already_issued"


def test_other_credit_on_the_order_leaves_only_the_room_under_the_cap():
    start = NOW - timedelta(hours=3)
    order = base_order(promised_at=start, delivered_at=start + timedelta(minutes=45))
    claims = ClaimFacts(credit_on_order_dh=2500)
    assert engine.late_credit_due_dh(RULES, order, claims, NOW) == 500
    assert engine.decide_credit(RULES, order, claims, 500, "late_delivery", NOW).outcome == EXECUTE


def parcel(**overrides):
    values = dict(category="parcel", subtotal_dh=0, discount_dh=0, delivery_fee_dh=3000, other_fees_dh=0, tip_dh=0,
                  items=())
    values.update(overrides)
    return base_order(**values)


def test_can02_a_parcel_on_its_way_cannot_be_cancelled_however_late():
    order = parcel(status="on_the_way", delivered_at=None, placed_at=NOW - timedelta(hours=5),
                   promised_at=NOW - timedelta(minutes=60))
    assert engine.cancellation_terms(RULES, order, NOW)["code"] == "cannot_cancel_now"


def test_can04_an_estimate_slip_does_not_free_a_parcel():
    order = parcel(status="driver_assigned", delivered_at=None, placed_at=NOW - timedelta(hours=1),
                   promised_at=NOW + timedelta(hours=1), estimate_at=NOW + timedelta(minutes=95))
    assert engine.cancellation_terms(RULES, order, NOW)["charge_dh"] == 500


def test_pcl04_damage_window_is_72_hours_and_goes_to_a_person():
    order = parcel(delivered_at=NOW - timedelta(hours=1))
    decision = engine.decide_refund(RULES, order, ClaimFacts(), 15000, "damaged_item", NOW)
    assert decision.code == "parcel_needs_person"
    late = parcel(delivered_at=NOW - timedelta(hours=80))
    assert engine.decide_refund(RULES, late, ClaimFacts(), 100, "damaged_item", NOW).code == "outside_reporting_window"


def test_pcl03_a_payout_is_not_held_to_the_amount_paid():
    order = parcel(delivered_at=NOW - timedelta(hours=1), declared_value_dh=30000)
    assert engine.decide_refund(RULES, order, ClaimFacts(), 20000, "damaged_item", NOW).outcome == APPROVAL
    assert engine.parcel_cover_dh(RULES, order) == 20000


@pytest.mark.parametrize("hours,refund", [(24, 0), (25, 1500), (48, 1500), (49, 3000)])
def test_pcl04_delay_refund_rows(hours, refund):
    order = parcel(promised_at=NOW - timedelta(hours=hours), delivered_at=NOW)
    assert engine.parcel_delay_refund_dh(RULES, order, NOW) == refund


def test_pcl04_a_parcel_is_not_lost_until_72_hours_past_promised():
    order = parcel(status="on_the_way", delivered_at=None, promised_at=NOW - timedelta(hours=71))
    assert engine.decide_refund(RULES, order, ClaimFacts(), 100, "not_received", NOW).code == "parcel_not_lost_yet"
    lost = parcel(status="on_the_way", delivered_at=None, promised_at=NOW - timedelta(hours=73))
    assert engine.decide_refund(RULES, lost, ClaimFacts(), 100, "not_received", NOW).code == "parcel_needs_person"


def test_phr05_a_pharmacy_seal_has_48_hours():
    order = base_order(category="pharmacy", delivered_at=NOW - timedelta(hours=30))
    assert refund(5, "broken_seal", order=order, photo_provided=True).outcome == APPROVAL


def test_lat02_and_ref07_no_credit_after_a_full_refund():
    claims = ClaimFacts(refunded_on_order_dh=9100)
    assert engine.decide_credit(RULES, base_order(), claims, 500, "goodwill", NOW).code == "full_refund_already_given"
    start = NOW - timedelta(hours=3)
    late = base_order(promised_at=start, delivered_at=start + timedelta(minutes=70))
    assert engine.decide_credit(RULES, late, claims, 500, "late_delivery", NOW).code == "full_refund_already_given"


def test_can04_cancellation_credit_is_the_one_exception_to_that():
    placed = NOW - timedelta(hours=2)
    order = base_order(status="cancelled", delivered_at=None, placed_at=placed, cancelled_by="merchant",
                       cancelled_at=placed + timedelta(minutes=40))
    claims = ClaimFacts(refunded_on_order_dh=9600)
    assert engine.decide_credit(RULES, order, claims, 1000, "cancellation_credit", NOW).outcome == EXECUTE


def test_ref07_automated_goodwill_stops_at_the_claim_window():
    old = base_order(delivered_at=NOW - timedelta(days=9))
    assert engine.decide_credit(RULES, old, ClaimFacts(), 500, "goodwill", NOW).code == "goodwill_outside_window"


def test_ref05_late_credit_counts_toward_the_total_on_the_order():
    start = NOW - timedelta(hours=3)
    order = base_order(promised_at=start, delivered_at=start + timedelta(minutes=70))
    decision = engine.decide_credit(RULES, order, ClaimFacts(refunded_on_order_dh=4000), 2000, "late_delivery", NOW)
    assert decision.outcome == APPROVAL


def test_grc05_expired_credit_is_grocery_only_and_needs_a_photo():
    grocery = base_order(category="grocery", delivered_at=NOW - timedelta(days=3))
    pharmacy = base_order(category="pharmacy", delivered_at=NOW - timedelta(days=3))
    decide = lambda order, **kw: engine.decide_credit(RULES, order, ClaimFacts(), 1000, "expired_item_credit", NOW, **kw)  # noqa: E731
    assert decide(pharmacy, photo_provided=True).code == "no_expired_item_credit_due"
    assert decide(grocery).code == "photo_needed"
    assert decide(grocery, photo_provided=True).outcome == EXECUTE


def test_lat03_at_120_minutes_jalboot_cancels():
    order = base_order(status="on_the_way", delivered_at=None, placed_at=NOW - timedelta(hours=4),
                       promised_at=NOW - timedelta(minutes=120))
    terms = engine.cancellation_terms(RULES, order, NOW)
    assert terms["code"] == "jalboot_auto_cancel"
    assert terms["refund_dh"] == 9600


@pytest.mark.parametrize("reason", ["cold_food", "chilled_item", "whole_wrong_order"])
def test_ref06_these_claims_need_a_photo_above_the_line(reason):
    order = base_order(delivered_at=NOW - timedelta(minutes=30))
    assert engine.photo_needed(RULES, reason, 3001)
    assert not engine.photo_needed(RULES, reason, 3000)
    assert refund(31, reason, order=order).code == "photo_needed"


def test_ref06_a_report_cannot_be_split_to_stay_under_the_line():
    assert refund(25, "wrong_item", claims=ClaimFacts(refunded_on_order_dh=2500)).code == "photo_needed"


def test_ref09_example_4_card_part_first_then_credit():
    order = base_order(subtotal_dh=8000, discount_dh=0, delivery_fee_dh=0, other_fees_dh=0, tip_dh=0, credit_paid_dh=3000)
    assert engine.refund_split(RULES, order, 6000, 0) == (5000, 1000, 0)


def test_ref04_the_wallet_stops_at_its_limit_and_the_card_takes_the_rest():
    order = base_order(credit_paid_dh=9600)
    assert engine.refund_split(RULES, order, 4000, 198000) == (2000, 2000, 0)


def test_ref04_cash_above_the_wallet_limit_needs_a_person():
    order = base_order(payment_method="cash")
    assert engine.refund_split(RULES, order, 4000, 198000) == (0, 2000, 2000)


def test_ref04_the_customer_can_choose_credit():
    assert engine.refund_split(RULES, base_order(), 4000, 0, to_credit=True) == (0, 4000, 0)


def test_lat05_a_cash_failure_pays_nothing_because_nothing_was_collected():
    order = failed(payment_method="cash", driver_wait_minutes=3)
    assert engine.failed_contact_refund_dh(RULES, order) == 0
    assert engine.failed_contact_refund_dh(RULES, failed(payment_method="cash", credit_paid_dh=2000)) == 2000


def test_lat05_a_failed_cash_order_leaves_a_capped_balance():
    assert engine.failed_cash_balance_dh(RULES, failed(payment_method="cash")) == 3000


def test_lat05_cold_chain_items_are_not_refunded():
    item = ItemFact("Insulin", 1, 9000, cold_chain=True)
    order = failed(category="pharmacy", subtotal_dh=9000, discount_dh=0, tip_dh=500, items=(item,))
    assert engine.failed_contact_refund_dh(RULES, order) == 500


def test_lat05_a_failed_cash_order_owes_for_the_cold_chain_items_a_card_would_lose():
    cold = ItemFact("Insulin", 1, 1000, cold_chain=True)
    plain = ItemFact("Vitamin D3", 1, 1000)
    order = failed(
        category="pharmacy", payment_method="cash", subtotal_dh=2000, discount_dh=0, delivery_fee_dh=0,
        other_fees_dh=0, tip_dh=0, items=(cold, plain),
    )
    packed = RULES.dh("cancellations.pharmacy.packed_charge_qar")
    assert engine.failed_cash_balance_dh(RULES, order) == 1000 + packed


def test_can01_the_picking_charge_stays_inside_its_floor_and_ceiling_and_the_items():
    floor = RULES.dh("cancellations.grocery.picking_charge_min_qar")
    ceiling = RULES.dh("cancellations.grocery.picking_charge_max_qar")
    assert engine.picking_charge_dh(RULES, 100) == 100
    assert engine.picking_charge_dh(RULES, floor) == floor
    assert engine.picking_charge_dh(RULES, 10_000_000) == ceiling


def test_gen03_the_final_subtotal_sets_the_amount_paid_and_the_seventy_percent_rule():
    order = base_order(subtotal_dh=20000, final_subtotal_dh=15000, discount_dh=0)
    assert order.paid_dh == 15000 + 800 + 300 + 500
    assert engine.full_refund_applies(RULES, order, [(ItemFact("x", 1, 10500), 1)])


def test_prm01_dates_are_doha_dates():
    from datetime import datetime as moment

    late_utc = moment(2026, 9, 30, 20, 59, tzinfo=timezone.utc)
    doha_next_day = moment(2026, 9, 30, 22, 30, tzinfo=timezone.utc)
    assert promo("SUMMER25", now=late_utc).outcome == EXECUTE
    assert promo("SUMMER25", now=doha_next_day).code == "code_expired"


def test_prm01_zone_and_base_fee_rules():
    assert promo("FREEDROP", zone="D").code == "code_not_for_this_zone"
    assert promo("FREEDROP", zone="A").outcome == EXECUTE
    assert promo("PARCEL10", category="parcel", base_fee_dh=1500).code == "below_minimum_spend"
    assert promo("PARCEL10", category="parcel", base_fee_dh=2000).outcome == EXECUTE
