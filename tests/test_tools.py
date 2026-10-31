"""The rules that must hold no matter what a model asks for.

These tests call the tool layer directly, the way a compromised model would. Nothing
here depends on a prompt.
"""

import pytest
from sqlalchemy import func, select

from jalboot import audit
from jalboot.db.models import Approval, AuditEvent, Customer, Order, Refund, StaffUser, Ticket
from jalboot.security.passwords import hash_password
from jalboot.tools import approvals
from jalboot.tools.approvals import DecisionError, decide
from tests.conftest import ANCHOR, RULES, make_conversation, tools_for

MISSING = dict(order_id="JB-700102", amount_qar=4.0, reason="missing_item", items=["Karak tea"])


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
        "order_id": "JB-700202", "amount_qar": 5.0, "reason": "missing_item", "items": ["Lentil soup"],
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
    result = layla.execute("issue_refund", {**MISSING, "items": ["karak"]})
    assert result.get("replayed") is True
    assert refund_count(db) == 1


def test_arabic_item_names_match(layla):
    result = layla.execute("issue_refund", {**MISSING, "items": ["شاي كرك"]})
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
    assert layla.execute("issue_refund", {**MISSING, "items": ["Gold watch"]})["error"] == "item_not_in_order"


def test_quote_uses_the_seventy_percent_rule_and_reveals_no_limits(layla):
    quote = layla.execute("quote_refund", {
        "order_id": "JB-700103", "reason": "wrong_item", "items": ["Mixed grill plate", "Grilled hammour"],
    })
    assert quote["amount_qar"] == 250 + 8 + 3
    assert set(quote) == {"ok", "order_id", "reason", "amount_qar"}


def test_above_the_limit_files_an_approval_and_pays_nothing(db, layla):
    result = layla.execute("issue_refund", {
        "order_id": "JB-700103", "amount_qar": 90.0, "reason": "wrong_item", "items": ["Grilled hammour"],
    })
    assert result["status"] == "pending_approval"
    assert refund_count(db) == 0
    approval = db.get(Approval, result["approval_id"])
    assert approval.status == "pending"
    assert approval.amount_dh == 9000
    assert audit_rows(db, "refund.proposed")


def test_repeating_a_request_above_the_limit_files_one_approval(db, layla):
    args = {"order_id": "JB-700103", "amount_qar": 90.0, "reason": "wrong_item", "items": ["Grilled hammour"]}
    layla.execute("issue_refund", args)
    assert layla.execute("issue_refund", args).get("replayed") is True
    assert db.scalar(select(func.count()).select_from(Approval)) == 1


def test_pharmacy_refunds_go_to_a_person_and_ask_for_a_handoff(db):
    tools = tools_for(db, make_conversation(db, customer_id="C-1002"))
    result = tools.execute("issue_refund", {
        "order_id": "JB-700204", "amount_qar": 45.0, "reason": "wrong_item", "items": ["Vitamin D3"],
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
    })["error"] == "above_late_credit_due"
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
    assert layla.execute("apply_promo", {"code": "SAVE20"})["error"] == "code_already_used"
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
        "order_id": "JB-700103", "amount_qar": amount, "reason": "wrong_item", "items": ["Grilled hammour"],
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
