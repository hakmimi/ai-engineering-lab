import pytest

from tablefind.score import by_gold_size, score

KEY = {"q1": {"a", "b"}, "q2": {"c"}, "q3": {"d", "e", "f"}}


def _a(picks, top20=None, made_up=(), status="ok"):
    return {"picks": list(picks), "top20": top20, "made_up": list(made_up), "filled": 0, "status": status}


def test_all_found_needs_every_gold_table():
    s = score({"q1": _a(["a", "x"]), "q2": _a(["c"]), "q3": _a(["d", "e", "f"])}, KEY)
    assert s.n == 3 and s.all_found == pytest.approx(2 / 3)


def test_recall_is_per_question_mean():
    s = score({"q1": _a(["a"]), "q2": _a([]), "q3": _a(["d", "e", "f"])}, KEY)
    assert s.recall == pytest.approx((0.5 + 0 + 1) / 3)


def test_failed_excluded_error_counts_as_miss():
    s = score({"q1": _a(["a", "b"]), "q2": _a([], status="error"), "q3": _a([], status="failed")}, KEY)
    assert (s.n, s.errors, s.failed) == (2, 1, 1)
    assert s.all_found == 0.5


def test_ceiling_uses_top20_and_made_up_share():
    s = score({"q1": _a(["a"], top20=["a", "b"], made_up=["zz"]), "q2": _a(["c"], top20=["c"]),
               "q3": _a(["d"], top20=["d", "e"])}, KEY)
    assert s.ceiling == pytest.approx(2 / 3)
    assert s.made_up == pytest.approx(1 / 3)
    plain = score({"q1": _a(["a", "b"])}, KEY)
    assert plain.ceiling is None and plain.made_up is None


def test_by_gold_size_buckets():
    out = by_gold_size({"q1": _a(["a", "b"]), "q2": _a([]), "q3": _a(["d", "e", "f"])}, KEY)
    assert out == {"1": 0.0, "2": 1.0, "3+": 1.0}
