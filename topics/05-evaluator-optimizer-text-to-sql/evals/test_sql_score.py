import pytest

from sqlloop.score import score


def rnd(right, verdict=None):
    return {"sql": "S", "error": "", "n_rows": 1, "verdict": verdict, "feedback": "", "right": right}


def out(rounds, stop="pass", error=""):
    return {"rounds": rounds, "stop": stop, "error": error, "right": rounds[-1]["right"] if rounds else False,
            "first_right": rounds[0]["right"] if rounds else False, "final_error": ""}


DIFF = {"a": "simple", "b": "simple", "c": "moderate", "d": "challenging", "e": "moderate"}


def test_scores_counted_by_hand():
    outs = {
        "a": out([rnd(True, "PASS")]),                                  # right first try, trusted
        "b": out([rnd(False, "PASS")]),                                 # fooled
        "c": out([rnd(False, "FAIL"), rnd(True, "PASS")]),              # fixed
        "d": out([rnd(True, "NEEDS_IMPROVEMENT"), rnd(False, "PASS")]), # broken: false alarm, then fooled
        "e": out([rnd(False, "FAIL")] * 3, stop="cap"),                 # cap hit
    }
    s = score(outs, DIFF)
    assert s["n"] == 5 and s["right"] == pytest.approx(2 / 5)
    assert s["first_right"] == pytest.approx(2 / 5)
    assert s["fixed"] == 1 and s["broken"] == 1
    # graded rounds: wrong ones = b, c1, d2, e1, e2, e3 -> 6, of which PASS = b, d2
    assert s["pass_on_wrong"] == pytest.approx(2 / 6)
    # graded right rounds: a, c2, d1 -> 3, of which not PASS = d1
    assert s["false_alarm"] == pytest.approx(1 / 3)
    # final PASS answers: a, b, c, d -> right a, c
    assert s["pass_right"] == pytest.approx(2 / 4)
    assert s["rounds"] == pytest.approx((1 + 1 + 2 + 2 + 3) / 5)
    assert s["cap_hit"] == pytest.approx(1 / 5)
    assert s["by_difficulty"]["simple"] == pytest.approx(1 / 2)
    assert s["by_difficulty"]["challenging"] == 0


def test_api_errors_are_left_out_and_counted():
    outs = {"a": out([rnd(True)], stop="one_shot"), "b": out([], stop="error", error="APITimeoutError")}
    s = score(outs, DIFF)
    assert s["n"] == 1 and s["api_errors"] == 1 and s["right"] == 1


def test_ungraded_levels_have_no_grader_rates():
    s = score({"a": out([rnd(True)], stop="one_shot")}, DIFF)
    assert s["pass_on_wrong"] is None and s["false_alarm"] is None and s["pass_right"] is None
