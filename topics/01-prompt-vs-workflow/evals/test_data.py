from claimsflow.data import load_answer_key, load_claims, load_customers, load_wordings
from claimsflow.rules import CLAIM_TYPES, DECISIONS, REQUIRED_DOCS, compute_payout, find_policy


def test_counts():
    assert len(load_claims()) == 30
    assert len(load_answer_key()) == 30


def test_wordings_for_each_line():
    assert set(load_wordings()) == {"car", "home", "travel"}


def test_every_claim_has_a_key_and_valid_values():
    key = load_answer_key()
    for c in load_claims():
        r = key[c.claim_id]
        assert r.decision in DECISIONS, c.claim_id
        assert r.claim_type in CLAIM_TYPES or r.decision == "hand_to_person", c.claim_id
        assert all(d in REQUIRED_DOCS[r.claim_type] for d in r.doc_problems), c.claim_id
        assert (r.decision == "request_documents") == bool(r.doc_problems), c.claim_id
        if not r.decision.startswith("approve"):
            assert r.amount == 0, c.claim_id


def test_every_claim_customer_exists():
    customers = load_customers()
    assert all(c.customer_id in customers for c in load_claims())


def test_answer_key_amounts_match_payout_rules():
    customers, claims = load_customers(), {c.claim_id: c for c in load_claims()}
    for cid, r in load_answer_key().items():
        if r.decision.startswith("approve"):
            policy = find_policy(customers[claims[cid].customer_id], r.claim_type)
            assert compute_payout(policy, r.figures) == (r.amount, r.decision), cid


def test_worked_examples_present():
    amounts = {r.amount for r in load_answer_key().values()}
    assert {10500, 7000, 5000} <= amounts


def test_mix_of_decisions():
    decisions = {r.decision for r in load_answer_key().values()}
    assert decisions == {"approve_full", "approve_partial", "decline", "request_documents", "hand_to_person"}


def test_no_matching_policy_case_exists():
    customers, key = load_customers(), load_answer_key()
    hits = [
        c.claim_id
        for c in load_claims()
        if key[c.claim_id].claim_type and find_policy(customers[c.customer_id], key[c.claim_id].claim_type) is None
    ]
    assert hits and all(key[h].decision == "decline" for h in hits)
