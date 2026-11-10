from agentflow.score import consistency, outcome_key, rows_hash, score_repeat


def o(right=False, db="shop", sql="SELECT 1", final_error="", rows="h1", error="", **extra):
    return {"right": right, "db": db, "sql": sql, "final_error": final_error, "rows_hash": rows, "error": error,
            "cost_usd": 0.001, "seconds": 2.0, "calls": [{}, {}], "handoff": False, "stop": "ok", **extra}


def test_rows_hash_ignores_order_and_duplicates():
    assert rows_hash([(1, "a"), (2, "b")]) == rows_hash([(2, "b"), (1, "a"), (1, "a")])
    assert rows_hash([(1,)]) != rows_hash([(2,)])


def test_outcome_key():
    assert outcome_key(o(db=None, sql="")) == "no answer"
    assert outcome_key(o(sql="")) == "no answer"
    assert outcome_key(o(final_error="no such column")) == "sql error"
    assert outcome_key(o(rows="abc")) == "shop:abc"


def test_score_repeat_basic_rates_and_api_errors_left_out():
    res = {"1": o(right=True), "2": o(db="zoo"), "3": o(db=None, sql=""), "4": o(error="RateLimitError: x")}
    s = score_repeat(res, {"1": "shop", "2": "shop", "3": "shop", "4": "shop"})
    assert (s["n"], s["api_errors"]) == (3, 1)
    assert s["right"] == 1 / 3 and s["right_db"] == 1 / 3 and s["no_answer"] == 1 / 3
    assert s["cost"] == 0.001 and s["seconds"] == 2.0 and s["calls"] == 2.0


def test_median_seconds_ignore_one_slow_api_call():
    res = {"1": o(seconds=1.0), "2": o(seconds=2.0), "3": o(seconds=400.0)}
    assert score_repeat(res, dict.fromkeys(res, "shop"))["seconds_median"] == 2.0


def test_score_repeat_handoff_and_level_extras():
    res = {"1": o(right=True, handoff=True), "2": o(right=True), "3": o(), "4": o(stop="cap", steps=10, db=None, sql=""),
           "5": o(steps=4)}
    s = score_repeat(res, dict.fromkeys(res, "shop"))
    assert s["handoff"] == 0.2 and s["right_rest"] == 0.25
    assert s["right_db"] == 3 / 4  # handoffs left out: the human picked; question 4 has no database
    assert s["steps"] == 7.0 and s["cap"] == 0.2
    assert s["agree"] is None and s["n_sub"] is None and s["rounds"] is None


def test_consistency_same_and_right_all():
    r1 = {"1": o(right=True, rows="a"), "2": o(rows="b"), "3": o(rows="c")}
    r2 = {"1": o(right=True, rows="a"), "2": o(rows="x"), "3": o(rows="c")}
    r3 = {"1": o(right=True, rows="a"), "2": o(rows="b"), "3": o(rows="c")}
    c = consistency([r1, r2, r3])
    assert c == {"n": 3, "same": 2 / 3, "right_all": 1 / 3}


def test_consistency_leaves_out_questions_with_an_api_error():
    r1 = {"1": o(right=True), "2": o()}
    r2 = {"1": o(error="APIError"), "2": o()}
    assert consistency([r1, r2]) == {"n": 1, "same": 1.0, "right_all": 0.0}


def test_consistency_needs_two_repeats():
    assert consistency([{"1": o()}]) == {"n": 0, "same": None, "right_all": None}
