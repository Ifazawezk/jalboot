"""The rules that must hold no matter what a model asks for.

These tests call the tool layer directly, the way a compromised model would. Nothing
here depends on a prompt.
"""

from datetime import timedelta

import pytest
from sqlalchemy import func, select

from jalboot import audit
from jalboot.db.models import Address, Approval, AuditEvent, Customer, Order, Refund, StaffUser, Ticket
from jalboot.security.passwords import hash_password
from jalboot.tools import approvals
from jalboot.tools.approvals import DecisionError, decide
from tests.conftest import ANCHOR, RULES, make_conversation, tools_for

MISSING = dict(order_id="JB-700102", amount_qar=4.0, reason="missing_item", items=[{"name": "Karak tea"}])


def refund_count(db):
    return db.scalar(select(func.count()).select_from(Refund))


def audit_rows(db, action):
    return db.scalars(select(AuditEvent).where(AuditEvent.action == action)).all()


def test_nothing_about_an_order_shows_before_the_identity_check(db):
    tools = tools_for(db, make_conversation(db, verified=False))
    for name, args in [
        ("track_order", {"order_id": "JB-700101"}),
        ("get_order_details", {"order_id": "JB-700101"}),
        ("explain_delay", {"order_id": "JB-700101"}),
        ("get_customer_profile", {}),
        ("quote_refund", {"order_id": "JB-700102", "reason": "not_received"}),
        ("issue_refund", MISSING),
    ]:
        assert tools.execute(name, args) == {"ok": False, "error": "identity_required"}


def test_a_customer_cannot_reach_another_customers_order(layla):
    assert layla.execute("track_order", {"order_id": "JB-700201"})["error"] == "order_not_found"


def test_an_unknown_order_and_a_foreign_order_look_the_same(layla):
    foreign = layla.execute("track_order", {"order_id": "JB-700201"})
    unknown = layla.execute("track_order", {"order_id": "JB-123456"})
    assert foreign == unknown


def test_a_foreign_refund_is_refused_and_pays_nothing(db, layla):
    before = refund_count(db)
    result = layla.execute("issue_refund", {
        "order_id": "JB-700202", "amount_qar": 5.0, "reason": "missing_item", "items": [{"name": "Lentil soup"}],
    })
    assert result["error"] == "order_not_found"
    assert refund_count(db) == before


@pytest.mark.parametrize("extra", [
    {"customer_id": "C-1002"}, {"skip_limits": True}, {"approved_by": "manager"}, {"photo_provided": True},
])
def test_an_unlisted_argument_is_refused_not_ignored(db, layla, extra):
    assert layla.execute("issue_refund", {**MISSING, **extra})["error"] == "unknown_argument"
    assert refund_count(db) == 0


def test_a_tool_that_does_not_exist_is_refused(layla):
    assert layla.execute("delete_all_orders", {})["error"] == "unknown_tool"


def test_arguments_that_were_not_valid_json_are_refused(layla):
    assert layla.execute("issue_refund", {}, malformed=True)["error"] == "arguments_not_valid_json"


@pytest.mark.parametrize("value", ["lots", True, None])
def test_a_bad_amount_type_is_refused(layla, value):
    assert layla.execute("issue_refund", {**MISSING, "amount_qar": value})["error"] == "invalid_argument"


def test_a_small_refund_runs_and_is_audited(db, layla):
    result = layla.execute("issue_refund", MISSING)
    assert result["ok"] and result["status"] == "done" and result["amount_qar"] == 4.0
    assert refund_count(db) == 1
    rows = audit_rows(db, "refund.auto_approved")
    assert len(rows) == 1
    assert rows[0].order_id == "JB-700102"


def test_a_repeat_refund_pays_once_even_with_a_new_amount(db, layla):
    first = layla.execute("issue_refund", MISSING)
    second = layla.execute("issue_refund", {**MISSING, "amount_qar": 3.0})
    assert second["replayed"] is True
    assert second["refund_id"] == first["refund_id"]
    assert refund_count(db) == 1


def test_a_second_conversation_cannot_refund_the_same_item(db, layla):
    layla.execute("issue_refund", MISSING)
    other = tools_for(db, make_conversation(db, name="conv-2"))
    assert other.execute("issue_refund", MISSING).get("replayed") is True
    assert refund_count(db) == 1


def test_a_different_spelling_cannot_refund_an_item_twice(db, layla):
    layla.execute("issue_refund", MISSING)
    result = layla.execute("issue_refund", {**MISSING, "items": [{"name": "karak"}]})
    assert result.get("replayed") is True
    assert refund_count(db) == 1


def test_arabic_item_names_match(layla):
    result = layla.execute("issue_refund", {**MISSING, "items": [{"name": "شاي كرك"}]})
    assert result["status"] == "done"


def test_a_refund_cannot_be_more_than_the_item_is_worth(db, layla):
    result = layla.execute("issue_refund", {**MISSING, "amount_qar": 40.0})
    assert result["error"] == "above_item_value"
    assert result["max_qar"] == 4.0
    assert refund_count(db) == 0


def test_an_item_claim_must_name_the_item(layla):
    args = {k: v for k, v in MISSING.items() if k != "items"}
    assert layla.execute("issue_refund", args)["error"] == "items_required"


def test_an_item_that_is_not_on_the_order_is_refused(layla):
    assert layla.execute("issue_refund", {**MISSING, "items": [{"name": "Gold watch"}]})["error"] == "item_not_in_order"


def test_quote_uses_the_seventy_percent_rule_and_reveals_no_limits(layla):
    quote = layla.execute("quote_refund", {
        "order_id": "JB-700103", "reason": "wrong_item",
        "items": [{"name": "Mixed grill plate", "quantity": 2}, {"name": "Grilled hammour"}],
    })
    assert quote["amount_qar"] == 250 + 8 + 3
    assert set(quote) == {"ok", "order_id", "reason", "amount_qar"}


def test_above_the_limit_files_an_approval_and_pays_nothing(db, layla):
    result = layla.execute("issue_refund", {
        "order_id": "JB-700103", "amount_qar": 90.0, "reason": "wrong_item", "items": [{"name": "Grilled hammour"}],
    })
    assert result["status"] == "pending_approval"
    assert refund_count(db) == 0
    approval = db.get(Approval, result["approval_id"])
    assert approval.status == "pending"
    assert approval.amount_dh == 9000
    assert audit_rows(db, "refund.proposed")


def test_repeating_a_request_above_the_limit_files_one_approval(db, layla):
    args = {"order_id": "JB-700103", "amount_qar": 90.0, "reason": "wrong_item", "items": [{"name": "Grilled hammour"}]}
    layla.execute("issue_refund", args)
    assert layla.execute("issue_refund", args).get("replayed") is True
    assert db.scalar(select(func.count()).select_from(Approval)) == 1


def test_pharmacy_refunds_go_to_a_person_and_ask_for_a_handoff(db):
    tools = tools_for(db, make_conversation(db, customer_id="C-1002"))
    result = tools.execute("issue_refund", {
        "order_id": "JB-700204", "amount_qar": 45.0, "reason": "wrong_item", "items": [{"name": "Vitamin D3"}],
    })
    assert result["status"] == "pending_approval"
    assert result["handoff_required"] == "policy_requires_person"
    assert refund_count(db) == 0


def test_every_refused_call_is_audited(db, layla):
    layla.execute("track_order", {"order_id": "JB-700201"})
    rows = audit_rows(db, "guardrail.blocked")
    assert len(rows) == 1
    assert rows[0].detail["error"] == "order_not_found"


def test_audit_chain_stays_valid_through_real_tool_calls(db, layla):
    layla.execute("issue_refund", MISSING)
    layla.execute("track_order", {"order_id": "JB-700201"})
    assert audit.verify_chain(db) == (True, None)


def test_no_phone_number_reaches_the_audit_log(db, layla):
    layla.execute("create_ticket", {"category": "other", "details": "call me on +974 5555 1234 please"})
    assert all("5555" not in str(row.detail) for row in audit_rows(db, "tool.called"))


def test_a_refused_refund_leaves_the_wallet_alone(db, layla):
    before = db.get(Customer, "C-1001").wallet_dh
    layla.execute("issue_refund", {**MISSING, "amount_qar": 999.0})
    assert db.get(Customer, "C-1001").wallet_dh == before


def test_late_credit_is_computed_by_policy_and_cannot_be_inflated(layla):
    assert layla.execute("issue_credit", {
        "order_id": "JB-700104", "amount_qar": 30.0, "reason": "late_delivery",
    })["error"] == "above_credit_due"
    assert layla.execute("issue_credit", {
        "order_id": "JB-700104", "amount_qar": 20.0, "reason": "late_delivery",
    })["status"] == "done"


def test_a_late_delivery_fee_is_only_refunded_when_due(layla):
    args = {"order_id": "JB-700102", "amount_qar": 8.0, "reason": "late_delivery_fee"}
    assert layla.execute("issue_refund", args)["error"] == "no_fee_refund_due"


def test_a_saved_address_moves_the_order_once(db):
    tools = tools_for(db, make_conversation(db, customer_id="C-1002"))
    result = tools.execute("change_address", {"order_id": "JB-700201", "new_address": "Street 410, Building 7"})
    assert result["status"] == "done"
    assert "410" in db.get(Order, "JB-700201").address_text
    second = tools.execute("change_address", {"order_id": "JB-700201", "new_address": "my home"})
    assert second["error"] == "address_change_limit_reached"


def test_a_new_address_needs_a_person(db):
    tools = tools_for(db, make_conversation(db, customer_id="C-1002"))
    result = tools.execute("change_address", {"order_id": "JB-700201", "new_address": "Some villa near the park"})
    assert result["status"] == "pending_approval"
    assert "villa" not in db.get(Order, "JB-700201").address_text


def test_the_address_is_locked_after_pickup(layla):
    result = layla.execute("change_address", {"order_id": "JB-700101", "new_address": "work"})
    assert result["error"] == "address_locked_after_pickup"


def test_a_cancellation_with_a_charge_needs_a_later_turn_to_confirm(db):
    conversation = make_conversation(db, customer_id="C-1002")
    args = {"order_id": "JB-700201"}
    first = tools_for(db, conversation, turn="t1").execute("cancel_order", args)
    assert first["status"] == "needs_confirmation"
    assert first["charge_qar"] > 0

    same_turn = tools_for(db, conversation, turn="t1").execute("cancel_order", {**args, "confirm_charge": True})
    assert same_turn["status"] == "needs_confirmation"
    assert db.get(Order, "JB-700201").status == "picking"

    later = tools_for(db, conversation, turn="t2").execute("cancel_order", {**args, "confirm_charge": True})
    assert later["status"] == "done"
    assert db.get(Order, "JB-700201").status == "cancelled"


def test_a_confirmation_with_no_quote_does_not_run(db):
    tools = tools_for(db, make_conversation(db, customer_id="C-1002"))
    result = tools.execute("cancel_order", {"order_id": "JB-700201", "confirm_charge": True})
    assert result["status"] == "needs_confirmation"


def test_promo_cannot_go_on_a_placed_order(layla):
    result = layla.execute("apply_promo", {"code": "SAVE20", "order_id": "JB-700102"})
    assert result["error"] == "code_cannot_be_added_after_placing"


def test_promo_applies_to_the_basket_once_a_month(db, layla):
    first = layla.execute("apply_promo", {"code": "SAVE20"})
    assert first["status"] == "done"
    assert first["discount_qar"] == 16.0
    assert db.get(Order, "BASKET-C-1001").discount_dh == 1600
    assert layla.execute("apply_promo", {"code": "SAVE20"})["error"] == "one_code_per_order"
    assert db.get(Order, "BASKET-C-1001").discount_dh == 1600


def test_an_expired_code_states_its_date(layla):
    result = layla.execute("apply_promo", {"code": "SUMMER25"})
    assert result["error"] == "code_expired"
    assert result["valid_until"] == "2026-09-30"


def test_ticket_works_without_verification_but_not_for_a_foreign_order(db):
    tools = tools_for(db, make_conversation(db, verified=False))
    assert tools.execute("create_ticket", {"category": "other", "details": "a general question"})["status"] == "done"
    denied = tools.execute("create_ticket", {"category": "other", "details": "x", "order_id": "JB-700101"})
    assert denied["error"] == "order_not_found"


def test_a_repeat_ticket_is_not_opened_twice(db, layla):
    args = {"category": "other", "details": "please follow up"}
    layla.execute("create_ticket", args)
    layla.execute("create_ticket", args)
    assert db.scalar(select(func.count()).select_from(Ticket).where(Ticket.source == "bot")) == 1


def test_handoff_needs_no_verification_and_a_safety_reason_stays_p1(db):
    conversation = make_conversation(db, verified=False)
    tools = tools_for(db, conversation)
    result = tools.execute("handoff_to_human", {"reason": "safety", "summary": "allergy", "priority": "P4"})
    assert result["ok"] and result["priority"] == "P1"
    assert conversation.status == "waiting"


def test_a_customer_id_in_the_conversation_alone_is_not_verified(db):
    conversation = make_conversation(db, verified=False)
    conversation.customer_id = "C-1001"
    db.commit()
    assert tools_for(db, conversation).execute("track_order", {"order_id": "JB-700101"})["error"] == "identity_required"


def staff(db, role="agent", staff_id="S-9"):
    user = StaffUser(id=staff_id, email=f"{staff_id}@sim.jalboot.example", name="Sim", role=role,
                     password_hash=hash_password("x"))
    db.add(user)
    db.commit()
    return user


def file_large_refund(db, layla, amount=90.0):
    return layla.execute("issue_refund", {
        "order_id": "JB-700103", "amount_qar": amount, "reason": "wrong_item", "items": [{"name": "Grilled hammour"}],
    })["approval_id"]


def test_only_approval_pays_and_it_pays_once(db, layla):
    approval_id = file_large_refund(db, layla)
    person = staff(db)
    outcome = decide(db, approval_id, person, "approve", "", 1, ANCHOR, RULES)
    assert outcome.refund.amount_dh == 9000
    assert refund_count(db) == 1
    assert audit_rows(db, "refund.approved")
    with pytest.raises(DecisionError) as stale:
        decide(db, approval_id, person, "approve", "", 1, ANCHOR, RULES)
    assert stale.value.code == "refund_already_decided"
    assert refund_count(db) == 1


def test_rejection_pays_nothing(db, layla):
    approval_id = file_large_refund(db, layla)
    decide(db, approval_id, staff(db), "reject", "The photo does not match", 1, ANCHOR, RULES)
    assert refund_count(db) == 0
    assert db.get(Approval, approval_id).status == "rejected"


def test_an_agent_cannot_decide_above_their_level(db, layla):
    approval_id = file_large_refund(db, layla)
    db.get(Approval, approval_id).required_role = "supervisor"
    db.commit()
    with pytest.raises(DecisionError) as blocked:
        decide(db, approval_id, staff(db), "approve", "", 1, ANCHOR, RULES)
    assert blocked.value.code == "approval_limit_exceeded"
    assert refund_count(db) == 0
    assert audit_rows(db, "guardrail.blocked")


def test_a_supervisor_can_decide_an_agent_level_case(db, layla):
    approval_id = file_large_refund(db, layla)
    assert decide(db, approval_id, staff(db, "supervisor"), "approve", "", 1, ANCHOR, RULES).refund


def test_a_stale_version_is_refused(db, layla):
    approval_id = file_large_refund(db, layla)
    with pytest.raises(DecisionError):
        decide(db, approval_id, staff(db), "approve", "", 7, ANCHOR, RULES)


def test_approval_rechecks_the_cap_at_decision_time(db, layla):
    approval_id = file_large_refund(db, layla, amount=90.0)
    db.add(Refund(id="R-X", order_id="JB-700103", customer_id="C-1001", amount_dh=26000, method="original",
                  reason="wrong_item", idempotency_key="other", created_at=ANCHOR))
    db.commit()
    with pytest.raises(DecisionError) as blocked:
        decide(db, approval_id, staff(db), "approve", "", 1, ANCHOR, RULES)
    assert blocked.value.code == "amount_exceeds_paid"


def test_role_ranks():
    row = Approval(required_role="finance_lead")
    assert not approvals.can_decide("supervisor", row)
    assert approvals.can_decide("finance_lead", row)


def test_a_street_number_that_matches_nothing_is_a_new_address_even_with_a_word_for_home(db):
    tools = tools_for(db, make_conversation(db, customer_id="C-1002"))
    result = tools.execute("change_address", {"order_id": "JB-700201", "new_address": "Street 777, Building 40, near the home of my aunt"})
    assert result["status"] == "pending_approval"


def test_an_aunts_house_is_not_the_home_label(db):
    tools = tools_for(db, make_conversation(db, customer_id="C-1002"))
    result = tools.execute("change_address", {"order_id": "JB-700201", "new_address": "بيت خالتي"})
    assert result["status"] == "pending_approval"


def test_the_first_cancel_request_fixes_the_status(db):
    conversation = make_conversation(db, customer_id="C-1002")
    tools_for(db, conversation, turn="t1").execute("cancel_order", {"order_id": "JB-700201"})
    assert db.get(Order, "JB-700201").extra["status_at_first_request"] == "picking"


def test_gen02_a_first_report_inside_the_window_stands_when_the_customer_returns(db):
    conversation = make_conversation(db)
    quote = {"order_id": "JB-700102", "reason": "missing_item", "items": [{"name": "Karak tea"}]}
    assert tools_for(db, conversation).execute("quote_refund", quote)["amount_qar"] == 4.0
    late = ANCHOR + timedelta(hours=30)
    assert tools_for(db, conversation, now=late).execute("issue_refund", MISSING)["status"] == "done"


def test_without_a_first_report_the_same_claim_is_too_late(db):
    tools = tools_for(db, make_conversation(db), now=ANCHOR + timedelta(hours=30))
    assert tools.execute("issue_refund", MISSING)["error"] == "outside_reporting_window"


def test_a_mixed_payment_refunds_the_card_part_first(db, layla):
    order = db.get(Order, "JB-700102")
    order.extra = {**(order.extra or {}), "credit_paid_dh": 2000}
    db.commit()
    before = db.get(Customer, "C-1001").wallet_dh
    paid_card = order.total_dh - 2000
    result = layla.execute("issue_refund", {
        "order_id": "JB-700102", "amount_qar": 4.0, "reason": "missing_item", "items": [{"name": "Karak tea"}],
    })
    assert result["to_original_payment_qar"] == 4.0 and paid_card > 400
    assert db.get(Customer, "C-1001").wallet_dh == before


def test_a_cash_refund_goes_to_credit(db):
    order = db.get(Order, "JB-700102")
    order.payment_method = "cash"
    db.commit()
    tools = tools_for(db, make_conversation(db))
    before = db.get(Customer, "C-1001").wallet_dh
    result = tools.execute("issue_refund", MISSING)
    assert result["to_credit_qar"] == 4.0
    assert db.get(Customer, "C-1001").wallet_dh == before + 400


def test_tool_results_give_doha_time_so_a_model_cannot_quote_utc(layla):
    result = layla.execute("track_order", {"order_id": "JB-700101"})
    assert result["promised_at"] == "2026-11-03 18:20 Doha time"


def bogo(db):
    order = db.get(Order, "JB-700102")
    item = order.items[0]
    item.extra = {"offer": "buy_one_get_one", "charged_units": 1}
    item.quantity = 2
    db.commit()
    return item.name


def test_wrg03_one_missing_unit_of_a_pair_is_the_free_one(db, layla):
    name = bogo(db)
    args = {"order_id": "JB-700102", "reason": "missing_item", "items": [{"name": name}]}
    assert layla.execute("quote_refund", args)["error"] == "no_refund_value"
    assert layla.execute("issue_refund", {**args, "amount_qar": 20.0})["error"] == "no_refund_value"
    assert refund_count(db) == 0


def test_wrg03_both_units_missing_refunds_the_price_paid(db, layla):
    name = bogo(db)
    quote = layla.execute("quote_refund", {
        "order_id": "JB-700102", "reason": "missing_item", "items": [{"name": name, "quantity": 2}],
    })
    assert quote["amount_qar"] == 20.0


def test_wrg01_a_short_quantity_refunds_only_the_missing_units(db, layla):
    order = db.get(Order, "JB-700102")
    order.items[0].quantity = 3
    db.commit()
    quote = layla.execute("quote_refund", {
        "order_id": "JB-700102", "reason": "missing_item", "items": [{"name": order.items[0].name, "quantity": 1}],
    })
    assert quote["amount_qar"] == 20.0


def test_a_zero_or_negative_quantity_is_refused(layla):
    claim = {"order_id": "JB-700102", "reason": "missing_item"}
    for quantity in (0, -2, True, "two"):
        line = {"name": "Karak tea", "quantity": quantity}
        assert layla.execute("quote_refund", {**claim, "items": [line]})["error"] == "invalid_argument"


def test_grc04_an_approved_substitute_cannot_be_rejected(db, layla):
    order = db.get(Order, "JB-700102")
    order.items[0].extra = {"substitute_for": "Something", "customer_approved": True}
    db.commit()
    result = layla.execute("quote_refund", {
        "order_id": "JB-700102", "reason": "substitute_rejected", "items": [{"name": order.items[0].name}],
    })
    assert result["error"] == "approved_substitute"


def test_lat04_a_door_drop_with_proof_is_delivered(db, layla):
    order = db.get(Order, "JB-700102")
    order.extra = {"proof_of_delivery": True, "gps_distance_m": 40, "leave_at_door": True}
    db.commit()
    result = layla.execute("issue_refund", {"order_id": "JB-700102", "amount_qar": 10.0, "reason": "not_received"})
    assert result["error"] == "delivered_at_door_with_proof"


def test_order_details_list_only_chosen_facts(db, layla):
    order = db.get(Order, "JB-700102")
    order.extra = {"proof_of_delivery": True, "internal_score": 7}
    db.commit()
    details = layla.execute("get_order_details", {"order_id": "JB-700102"})
    assert details["proof_of_delivery"] is True
    assert "internal_score" not in details


def test_saf03_an_allergen_claim_is_a_full_order_refund(layla):
    quote = layla.execute("quote_refund", {"order_id": "JB-700102", "reason": "allergen", "items": [{"name": "Karak tea"}]})
    assert quote["amount_qar"] == 65 + 8 + 3


@pytest.mark.parametrize("reason", ["illness", "broken_seal"])
def test_saf04_these_need_no_items_and_are_full_order(layla, reason):
    assert layla.execute("quote_refund", {"order_id": "JB-700102", "reason": reason})["amount_qar"] == 65 + 8 + 3


def test_wrg01_a_line_of_several_units_must_say_how_many(db, layla):
    order = db.get(Order, "JB-700102")
    order.items[0].quantity = 3
    db.commit()
    args = {"order_id": "JB-700102", "reason": "missing_item", "items": [{"name": order.items[0].name}]}
    assert layla.execute("quote_refund", args)["error"] == "quantity_required"


def test_a_second_missing_unit_pays_only_for_the_new_one(db, layla):
    order = db.get(Order, "JB-700102")
    name = order.items[0].name
    order.items[0].quantity = 3
    db.commit()
    claim = {"order_id": "JB-700102", "reason": "missing_item"}
    one, two = [{"name": name, "quantity": 1}], [{"name": name, "quantity": 2}]
    assert layla.execute("issue_refund", {**claim, "items": one, "amount_qar": 20.0})["status"] == "done"
    assert layla.execute("quote_refund", {**claim, "items": two})["amount_qar"] == 20.0
    assert layla.execute("issue_refund", {**claim, "items": two, "amount_qar": 20.0})["status"] == "done"
    assert layla.execute("quote_refund", {**claim, "items": two})["error"] == "item_already_refunded"
    assert refund_count(db) == 2


def test_prm01_a_second_code_cannot_stack(db, layla):
    assert layla.execute("apply_promo", {"code": "SAVE20"})["status"] == "done"
    assert layla.execute("apply_promo", {"code": "FREEDROP"})["error"] == "one_code_per_order"


def test_gen03_free_delivery_changes_the_fee_and_makes_no_discount(db, layla):
    basket = db.get(Order, "BASKET-C-1001")
    total = basket.total_dh
    assert layla.execute("apply_promo", {"code": "FREEDROP"})["status"] == "done"
    assert basket.delivery_fee_dh == 0
    assert basket.discount_dh == 0
    assert basket.total_dh == total - 500


def test_prm01_free_delivery_is_not_used_up_when_delivery_is_already_free(db, layla):
    db.get(Order, "BASKET-C-1001").delivery_fee_dh = 0
    db.commit()
    assert layla.execute("apply_promo", {"code": "FREEDROP"})["error"] == "delivery_already_free"


def very_late(db, minutes=125):
    order = db.get(Order, "JB-700101")
    order.promised_at = ANCHOR - timedelta(minutes=minutes)
    db.commit()
    return order


def test_lat03_a_two_hour_delay_refunds_and_adds_the_credit(db, layla):
    order = very_late(db)
    before = db.get(Customer, "C-1001").wallet_dh
    result = layla.execute("cancel_order", {"order_id": "JB-700101"})
    assert result["rule"] == "jalboot_auto_cancel"
    assert result["credit_qar"] == 10.0
    assert order.extra["cancelled_by"] == "jalboot"
    assert db.get(Customer, "C-1001").wallet_dh == before + 1000


def test_ref04_a_cancellation_returns_the_credit_part_to_the_wallet(db, layla):
    order = very_late(db, 50)
    order.extra = {**(order.extra or {}), "credit_paid_dh": 2000}
    db.commit()
    before = db.get(Customer, "C-1001").wallet_dh
    result = layla.execute("cancel_order", {"order_id": "JB-700101"})
    assert result["status"] == "done"
    assert result["to_credit_qar"] == 20.0
    assert db.get(Customer, "C-1001").wallet_dh == before + 2000


def test_ref04_a_cash_cancellation_returns_credit_it_used(db, layla):
    order = very_late(db, 50)
    order.payment_method = "cash"
    order.extra = {**(order.extra or {}), "credit_paid_dh": 2000}
    db.commit()
    before = db.get(Customer, "C-1001").wallet_dh
    layla.execute("cancel_order", {"order_id": "JB-700101"})
    assert db.get(Customer, "C-1001").wallet_dh == before + 2000


def test_ref04_approval_uses_the_same_split(db, layla):
    order = db.get(Order, "JB-700103")
    order.extra = {**(order.extra or {}), "credit_paid_dh": order.total_dh - 5000}
    db.commit()
    before = db.get(Customer, "C-1001").wallet_dh
    approval_id = file_large_refund(db, layla, amount=90.0)
    outcome = decide(db, approval_id, staff(db), "approve", "", 1, ANCHOR, RULES)
    assert outcome.refund.method == "mixed"
    assert db.get(Customer, "C-1001").wallet_dh == before + 4000


def test_acc03_an_address_change_resets_the_promise_and_charges_a_dearer_zone(db):
    order = db.get(Order, "JB-700201")
    original = order.promised_at
    tools = tools_for(db, make_conversation(db, customer_id="C-1002"))
    result = tools.execute("change_address", {"order_id": "JB-700201", "new_address": "Street 410, Building 7"})
    assert result["fee_qar"] == 0.0
    assert order.promised_at != original
    assert order.extra["original_promised_at"]


def test_acc03_food_cannot_move_to_zone_d(db):
    db.get(Order, "JB-700201").category = "food"
    address = db.get(Address, "A-1002-2")
    address.line = "Zone 90, Street 410, Building 7, Al Khor"
    db.commit()
    tools = tools_for(db, make_conversation(db, customer_id="C-1002"))
    result = tools.execute("change_address", {"order_id": "JB-700201", "new_address": "Street 410, Building 7"})
    assert result["error"] == "zone_not_served"


def test_gen02_a_chat_that_opened_before_delivery_cannot_stretch_a_window(db):
    """Code review bug 3: the time belongs to the order, not to the conversation."""
    order = db.get(Order, "JB-700102")
    order.extra = {**(order.extra or {}), "first_report_at": (order.delivered_at - timedelta(days=5)).isoformat()}
    db.commit()
    late = ANCHOR + timedelta(hours=30)
    tools = tools_for(db, make_conversation(db), now=late)
    assert tools.execute("issue_refund", MISSING)["error"] == "outside_reporting_window"


def test_gen02_a_report_on_one_order_does_not_stretch_another(db):
    conversation = make_conversation(db)
    tools_for(db, conversation).execute("quote_refund", {"order_id": "JB-700103", "reason": "illness"})
    late = ANCHOR + timedelta(hours=30)
    assert tools_for(db, conversation, now=late).execute("issue_refund", MISSING)["error"] == "outside_reporting_window"


def test_an_address_change_never_shows_a_refund_card(db):
    events = []
    conversation = make_conversation(db, customer_id="C-1002")
    tools = tools_for(db, conversation, publish=events.append)
    tools.execute("change_address", {"order_id": "JB-700201", "new_address": "Some villa near the park"})
    assert not [event for event in events if event["type"] == "refund.update"]


def test_a_credit_card_says_where_the_money_went(db, layla):
    events = []
    tools = tools_for(db, layla.conversation, publish=events.append)
    tools.execute("issue_credit", {"order_id": "JB-700104", "amount_qar": 20.0, "reason": "late_delivery"})
    assert [event for event in events if event["type"] == "refund.update"][0]["refund"]["destination"] == "credit"


def test_explain_delay_reports_nothing_due_after_the_window(db):
    tools = tools_for(db, make_conversation(db), now=ANCHOR + timedelta(hours=30))
    result = tools.execute("explain_delay", {"order_id": "JB-700104"})
    assert result["minutes_late"] > 60
    assert result["late_credit_due_qar"] == 0


def test_bug1_naming_a_four_riyal_tea_eleven_times_is_one_tea(db, layla):
    claim = {**MISSING, "amount_qar": 44.0, "items": [{"name": "Karak tea"}] * 11}
    result = layla.execute("issue_refund", claim)
    assert result["error"] == "above_item_value"
    assert result["max_qar"] == 4.0
    assert refund_count(db) == 0


def test_bug1_many_spellings_of_one_item_are_one_item(layla):
    spellings = ("Karak tea", "karak", "KARAK TEA", "شاي كرك", "tea")
    quote = layla.execute("quote_refund", {
        "order_id": "JB-700102", "reason": "missing_item", "items": [{"name": name} for name in spellings],
    })
    assert quote["amount_qar"] == 4.0


def test_bug1_a_name_that_fits_two_lines_is_refused(db, layla):
    db.get(Order, "JB-700102").items[1].name = "Karak tea large"
    db.commit()
    result = layla.execute("quote_refund", {
        "order_id": "JB-700102", "reason": "missing_item", "items": [{"name": "karak"}],
    })
    assert result["error"] == "ambiguous_item"


def test_bug1_an_exact_name_beats_a_partial_match(db, layla):
    db.get(Order, "JB-700102").items[1].name = "Karak tea large"
    db.commit()
    quote = layla.execute("quote_refund", {
        "order_id": "JB-700102", "reason": "missing_item", "items": [{"name": "Karak tea"}],
    })
    assert quote["amount_qar"] == 4.0


def test_bug1_too_many_lines_are_refused(layla):
    claim = {**MISSING, "items": [{"name": "Karak tea"}] * 51}
    assert layla.execute("issue_refund", claim)["error"] == "invalid_argument"


def test_bug2_each_line_has_its_own_quantity(layla):
    assert layla.execute("quote_refund", {
        "order_id": "JB-700103", "reason": "missing_item", "items": [{"name": "Mixed grill plate"}],
    })["error"] == "quantity_required"
    quote = layla.execute("quote_refund", {
        "order_id": "JB-700103", "reason": "missing_item", "items": [{"name": "Mixed grill plate", "quantity": 1}],
    })
    assert quote["amount_qar"] == 80.0


HAMMOUR = {"order_id": "JB-700103", "amount_qar": 90.0, "items": [{"name": "Grilled hammour"}]}


def test_bug4_one_item_cannot_be_filed_under_two_reasons(db, layla):
    first = layla.execute("issue_refund", {**HAMMOUR, "reason": "wrong_item"})
    second = layla.execute("issue_refund", {**HAMMOUR, "reason": "damaged_item"})
    assert second.get("replayed") is True
    assert second["approval_id"] == first["approval_id"]
    assert db.scalar(select(func.count()).select_from(Approval)) == 1


def test_bug4_a_unit_waiting_for_a_person_counts_as_claimed(db, layla):
    layla.execute("issue_refund", {**HAMMOUR, "reason": "wrong_item"})
    quote = layla.execute("quote_refund", {
        "order_id": "JB-700103", "reason": "damaged_item", "items": [{"name": "Grilled hammour"}],
    })
    assert quote["error"] == "item_already_refunded"


def test_bug4_a_rejected_claim_frees_nothing_up_by_replaying_as_paid(db, layla):
    first = layla.execute("issue_refund", {**HAMMOUR, "reason": "wrong_item"})
    decide(db, first["approval_id"], staff(db), "reject", "The photo does not match", 1, ANCHOR, RULES)
    assert layla.execute("issue_refund", {**HAMMOUR, "reason": "wrong_item"})["status"] == "rejected"
    assert refund_count(db) == 0


def test_bug4_approval_refuses_an_item_paid_since_filing(db, layla):
    first = layla.execute("issue_refund", {**HAMMOUR, "reason": "wrong_item"})
    db.add(Refund(id="R-Y", order_id="JB-700103", customer_id="C-1001", amount_dh=9000, method="original",
                  reason="wrong_item", idempotency_key="elsewhere", created_at=ANCHOR,
                  items=[{"name": "grilled hammour", "units": 1}]))
    db.commit()
    with pytest.raises(DecisionError) as blocked:
        decide(db, first["approval_id"], staff(db), "approve", "", 1, ANCHOR, RULES)
    assert blocked.value.code == "item_already_refunded"


def test_bug5_a_customer_who_chose_credit_gets_credit_after_approval(db, layla):
    before = db.get(Customer, "C-1001").wallet_dh
    first = layla.execute("issue_refund", {**HAMMOUR, "reason": "wrong_item", "method": "refund_credit"})
    outcome = decide(db, first["approval_id"], staff(db), "approve", "", 1, ANCHOR, RULES)
    assert outcome.refund.method == "refund_credit"
    assert db.get(Customer, "C-1001").wallet_dh == before + 9000


def test_bug7_an_approval_cannot_move_a_delivered_order(db):
    tools = tools_for(db, make_conversation(db, customer_id="C-1002"))
    pending = tools.execute("change_address", {"order_id": "JB-700201", "new_address": "A villa near the park"})
    order = db.get(Order, "JB-700201")
    order.status = "delivered"
    db.commit()
    with pytest.raises(DecisionError) as blocked:
        decide(db, pending["approval_id"], staff(db), "approve", "", 1, ANCHOR, RULES)
    assert blocked.value.code == "address_change_no_longer_possible"
    assert "villa" not in order.address_text


def test_bug7_two_approved_address_changes_break_the_limit_of_one(db):
    tools = tools_for(db, make_conversation(db, customer_id="C-1002"))
    first = tools.execute("change_address", {"order_id": "JB-700201", "new_address": "A villa near the park"})
    second = tools.execute("change_address", {"order_id": "JB-700201", "new_address": "A flat by the sea"})
    person = staff(db)
    decide(db, first["approval_id"], person, "approve", "", 1, ANCHOR, RULES)
    with pytest.raises(DecisionError):
        decide(db, second["approval_id"], person, "approve", "", 1, ANCHOR, RULES)


def test_bug7_approval_rechecks_the_credit_cap(db, layla):
    pending = layla.execute("issue_credit", {"order_id": "JB-700102", "amount_qar": 20.0, "reason": "goodwill"})
    assert pending["status"] == "pending_approval"
    db.add(Refund(id="R-Z", order_id="JB-700102", customer_id="C-1001", amount_dh=2000, method="compensation",
                  reason="goodwill", idempotency_key="other-credit", created_at=ANCHOR))
    db.commit()
    with pytest.raises(DecisionError) as blocked:
        decide(db, pending["approval_id"], staff(db), "approve", "", 1, ANCHOR, RULES)
    assert blocked.value.code == "credit_cap_per_order"


def test_bug7_approval_rechecks_the_wallet(db, layla):
    pending = layla.execute("issue_credit", {"order_id": "JB-700102", "amount_qar": 20.0, "reason": "goodwill"})
    db.get(Customer, "C-1001").wallet_dh = 199000
    db.commit()
    with pytest.raises(DecisionError) as blocked:
        decide(db, pending["approval_id"], staff(db), "approve", "", 1, ANCHOR, RULES)
    assert blocked.value.code == "wallet_at_limit"


def test_bug8_a_decided_claim_stops_reading_as_pending(db, layla):
    first = layla.execute("issue_refund", {**HAMMOUR, "reason": "wrong_item"})
    decide(db, first["approval_id"], staff(db), "approve", "", 1, ANCHOR, RULES)
    assert layla.execute("issue_refund", {**HAMMOUR, "reason": "wrong_item"})["status"] == "done"


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_bug10_nan_and_infinity_are_not_amounts(layla, value):
    assert layla.execute("issue_refund", {**MISSING, "amount_qar": value})["error"] == "invalid_argument"


def test_bug14_moving_a_parcel_back_is_a_real_move(db):
    order = db.get(Order, "JB-700201")
    order.category = "parcel"
    order.status = "placed"
    db.commit()
    tools = tools_for(db, make_conversation(db, customer_id="C-1002"))
    for text, line in (("work", "Street 410"), ("home", "Street 240"), ("work", "Street 410")):
        result = tools.execute("change_address", {"order_id": "JB-700201", "new_address": text})
        assert result["status"] == "done"
        assert line in order.address_text


def test_a_retry_to_the_same_address_changes_nothing_and_costs_nothing(db):
    order = db.get(Order, "JB-700201")
    order.category = "parcel"
    order.status = "on_the_way"
    db.commit()
    tools = tools_for(db, make_conversation(db, customer_id="C-1002"))
    first = tools.execute("change_address", {"order_id": "JB-700201", "new_address": "work"})
    again = tools.execute("change_address", {"order_id": "JB-700201", "new_address": "my work"})
    assert first["fee_qar"] == 10.0
    assert again["fee_qar"] == 0.0
    assert order.extra["reroute_fee_dh"] == 1000


def test_prm01_the_limit_comes_from_the_rules_file(db, layla):
    layla.execute("apply_promo", {"code": "SAVE20"})
    assert layla.execute("apply_promo", {"code": "FREEDROP"})["error"] == "one_code_per_order"
