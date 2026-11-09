import pytest

from ndaflow.models import Answer
from ndaflow.score import score

KEY = {
    "D1": {"nda-1": Answer("entailment", [1, 2]), "nda-2": Answer("contradiction", [3])},
    "D2": {"nda-1": Answer("not_mentioned", []), "nda-2": Answer("entailment", [5])},
}
RESULTS = {
    "D1": {"nda-1": Answer("entailment", [1, 9]), "nda-2": Answer("error", [])},
    "D2": {"nda-1": Answer("entailment", [4]), "nda-2": Answer("entailment", [])},
}


def test_scores_counted_by_hand():
    s = score(RESULTS, KEY)
    assert s.n_pairs == 4
    assert s.label_right == 0.5  # D1/nda-1 and D2/nda-2
    assert s.f1_entailment == pytest.approx(0.8)  # tp 2, fp 1, fn 0
    assert s.f1_contradiction == 0.0  # tp 0, fn 1
    assert s.evidence_recall == 0.25  # 1 of the key's 4 evidence spans
    assert s.evidence_precision == pytest.approx(1 / 3)  # 1 of the 3 spans named
    assert s.errors == 1


def test_no_contradictions_gives_f1_zero_not_a_crash():
    key = {"D": {"nda-1": Answer("not_mentioned", [])}}
    s = score({"D": {"nda-1": Answer("not_mentioned", [])}}, key)
    assert s.label_right == 1.0
    assert s.f1_contradiction == 0.0 and s.f1_entailment == 0.0
    assert s.evidence_recall == 0.0 and s.evidence_precision == 0.0


def test_contracts_missing_from_the_results_are_skipped():
    s = score({"D1": RESULTS["D1"]}, KEY)
    assert s.n_pairs == 2
    assert s.as_dict()["errors"] == 1
