from evals.helpers import (
    CAR_CUSTOMER,
    CUSTOMER_WITHOUT_HOME,
    FULL_APPROVE_XML,
    FULL_APPROVE_XML_WITH_TYPE,
    claim_for,
    ctx,
    fake_llm,
)

from claimsflow.levels import normalize_type, parse_result, run_level0, run_level1


# ---------------------------------------------------------------- parsing
def test_normalize_type_handles_case_and_unknown():
    assert normalize_type(" Car ") == "car"
    assert normalize_type("water damage") == "water_damage"
    assert normalize_type("Travel-Cancellation") == "travel_cancellation"
    assert normalize_type("other") is None
    assert normalize_type("home") is None


def test_parse_result_messy_amount():
    r = parse_result(
        "<decision>approve_full</decision><amount>10,500 ₪</amount><doc_problems>none</doc_problems><reason>ok</reason>", "car"
    )
    assert (r.decision, r.amount, r.doc_problems) == ("approve_full", 10500, [])


def test_parse_result_doc_problem_list():
    r = parse_result(
        "<decision>request_documents</decision><amount>0</amount><doc_problems>assessor_report, drivers_license</doc_problems><reason>x</reason>",
        "car",
    )
    assert r.doc_problems == ["assessor_report", "drivers_license"]


def test_parse_result_missing_decision_is_error():
    assert parse_result("<amount>5</amount>", "car").decision == "error"


def test_parse_result_unknown_decision_is_error():
    assert parse_result("<decision>maybe</decision><amount>0</amount>", "car").decision == "error"


# ---------------------------------------------------------------- level 0
def test_level0_single_call(monkeypatch):
    calls = fake_llm(monkeypatch, {"level0": FULL_APPROVE_XML_WITH_TYPE})
    r = run_level0(claim_for(CAR_CUSTOMER), ctx())
    assert [c.label for c in calls] == ["level0"]
    assert (r.decision, r.amount, r.claim_type) == ("approve_full", 10500, "car")


def test_level0_sees_all_three_wordings_in_cached_system(monkeypatch):
    calls = fake_llm(monkeypatch, {"level0": FULL_APPROVE_XML_WITH_TYPE})
    run_level0(claim_for(CAR_CUSTOMER), ctx())
    cached = calls[0].kwargs["cached_system"]
    assert "CAR-2026" in cached and "HOME-2026" in cached and "TRAVEL-2026" in cached


# ---------------------------------------------------------------- level 1
def test_level1_unknown_label_hands_to_person(monkeypatch):
    fake_llm(monkeypatch, {"route": "<claim_type>boat</claim_type>"})
    assert run_level1(claim_for(CAR_CUSTOMER), ctx()).decision == "hand_to_person"


def test_level1_no_matching_policy_declines(monkeypatch):
    fake_llm(monkeypatch, {"route": "<claim_type>water_damage</claim_type>"})
    r = run_level1(claim_for(CUSTOMER_WITHOUT_HOME), ctx())
    assert r.decision == "decline" and r.reason == "No matching policy" and r.claim_type == "water_damage"


def test_level1_calls_route_then_decide(monkeypatch):
    calls = fake_llm(monkeypatch, {"route": "<claim_type>car</claim_type>", "decide": FULL_APPROVE_XML})
    r = run_level1(claim_for(CAR_CUSTOMER), ctx())
    assert [c.label for c in calls] == ["route", "decide"]
    assert r.claim_type == "car"


def test_level1_decide_sees_only_its_own_wording(monkeypatch):
    calls = fake_llm(monkeypatch, {"route": "<claim_type>car</claim_type>", "decide": FULL_APPROVE_XML})
    run_level1(claim_for(CAR_CUSTOMER), ctx())
    cached = calls[1].kwargs["cached_system"]
    assert "CAR-2026" in cached and "HOME-2026" not in cached and "TRAVEL-2026" not in cached
