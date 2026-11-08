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


# ---------------------------------------------------------------- level 2
from claimsflow.levels import parallel, run_level2  # noqa: E402
from claimsflow.rules import REQUIRED_DOCS  # noqa: E402
from evals.helpers import TRAVEL_CUSTOMER, claim_with_no_attachments  # noqa: E402


def test_parallel_keeps_order():
    assert parallel(lambda x: x * 2, [3, 1, 2]) == [6, 2, 4]


def test_level2_missing_doc_requests_documents(monkeypatch):
    fake_llm(monkeypatch, {
        "route": "<claim_type>car</claim_type>",
        "doc:assessor_report": "<status>missing</status><problem>No assessor report</problem>",
        "doc:": "<status>ok</status>",
    })
    r = run_level2(claim_for(CAR_CUSTOMER), ctx())
    assert r.decision == "request_documents" and r.doc_problems == ["assessor_report"] and r.amount == 0
    assert "No assessor report" in r.reason


def test_level2_one_doc_call_per_required_doc(monkeypatch):
    calls = fake_llm(monkeypatch, {
        "route": "<claim_type>travel_medical</claim_type>",
        "doc:": "<status>ok</status>",
        "decide": FULL_APPROVE_XML,
    })
    run_level2(claim_for(TRAVEL_CUSTOMER), ctx())
    doc_labels = sorted(c.label for c in calls if c.label.startswith("doc:"))
    assert doc_labels == sorted(f"doc:{d}" for d in REQUIRED_DOCS["travel_medical"])


def test_level2_docs_ok_then_decide_told_docs_verified(monkeypatch):
    calls = fake_llm(monkeypatch, {
        "route": "<claim_type>car</claim_type>",
        "doc:": "<status>ok</status>",
        "decide": FULL_APPROVE_XML,
    })
    r = run_level2(claim_for(CAR_CUSTOMER), ctx())
    assert r.decision == "approve_full"
    assert "already checked" in calls[-1].kwargs["cached_system"]


def test_level2_no_attachments_all_missing(monkeypatch):
    fake_llm(monkeypatch, {"route": "<claim_type>car</claim_type>", "doc:": "<status>missing</status><problem>Not attached</problem>"})
    r = run_level2(claim_with_no_attachments(CAR_CUSTOMER), ctx())
    assert r.doc_problems == REQUIRED_DOCS["car"]


def test_level2_unreadable_status_counts_as_problem(monkeypatch):
    fake_llm(monkeypatch, {"route": "<claim_type>car</claim_type>", "doc:drivers_license": "I am not sure.", "doc:": "<status>ok</status>"})
    r = run_level2(claim_for(CAR_CUSTOMER), ctx())
    assert r.doc_problems == ["drivers_license"]
