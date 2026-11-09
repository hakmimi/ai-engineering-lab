import pytest

from sqlblame.score import score


def o(right, picked=None, error="", final_error="", n_rows=1, made_up=None, agent_empty=False):
    return {"right": right, "error": error, "final_error": final_error, "n_rows": n_rows, "picked": picked,
            "made_up": made_up if made_up is not None else ([] if picked is not None else None),
            "agent_empty": agent_empty}


GOLD = {"1": ["a", "b"], "2": ["c"], "3": ["d"], "4": ["e"], "5": ["f"]}
DB = {"1": "x", "2": "x", "3": "y", "4": "y", "5": "y"}
DIFF = {"1": "simple", "2": "simple", "3": "moderate", "4": "challenging", "5": "simple"}


def test_level_c_table_metrics():
    outs = {
        "1": o(False, picked=[["x", "a"]]),                       # half found
        "2": o(True, picked=[["x", "c"], ["x", "z"]]),            # found + 1 extra
        "3": o(True, picked=[["y", "d"]]),                        # exact
        "4": o(False, picked=[["x", "e"]], made_up=["y.ghost"], final_error="no such table: e", n_rows=None),  # wrong db
        "5": o(False, error="APIError: down"),
    }
    s = score(outs, DIFF, GOLD, DB)
    assert s["n"] == 4 and s["api_errors"] == 1
    assert s["right"] == 0.5
    assert s["overlap"] == pytest.approx((0.5 + 1 + 1 + 0) / 4)
    assert s["all_found"] == 0.5 and s["exact"] == 0.25
    assert s["extra"] == pytest.approx((0 + 1 + 0 + 1) / 4)
    assert s["wrong_db"] == 0.25 and s["made_up"] == 1 and s["agent_empty"] == 0
    assert s["right_all_found"] == 1.0 and s["right_missing"] == 0.0
    assert s["runs"] == 0.75 and s["has_output"] == 0.75 and s["final_errors"] == 1
    assert s["by_difficulty"] == {"simple": 0.5, "moderate": 1.0, "challenging": 0.0}


def test_levels_without_agent_have_no_table_metrics():
    s = score({"1": o(True), "2": o(False, n_rows=0)}, DIFF, GOLD, DB)
    assert s["right"] == 0.5 and s["has_output"] == 0.5
    for k in ("overlap", "all_found", "exact", "extra", "wrong_db", "right_all_found", "right_missing"):
        assert s[k] is None
    assert s["made_up"] is None and s["agent_empty"] is None
