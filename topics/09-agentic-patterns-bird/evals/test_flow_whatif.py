from agentflow.whatif import prefix_whatif, run_with_db_name
from flow_helpers import make_dbs


def test_a_database_prefix_runs_when_the_database_is_attached_under_its_name(tmp_path):
    paths = make_dbs(tmp_path)
    r = run_with_db_name(paths["shop"], "shop", "SELECT total FROM shop.orders WHERE cid = 1")
    assert sorted(r.rows) == [(3.0,), (9.5,)] and r.error == ""


def test_the_attached_copy_is_read_only(tmp_path):
    paths = make_dbs(tmp_path)
    r = run_with_db_name(paths["shop"], "shop", "DELETE FROM shop.orders")
    assert r.rows is None and "readonly" in r.error.replace(" ", "").lower()


def _res(qid_db, sql, final_error="", right=False, error=""):
    return {"db": qid_db, "sql": sql, "final_error": final_error, "right": right, "error": error}


def test_prefix_whatif_reruns_only_prefix_failures(tmp_path):
    paths = make_dbs(tmp_path)
    gold = {"1": [(9.5,), (3.0,)], "2": [(1,)], "3": [("Kim",)]}
    db_of = {"1": "shop", "2": "shop", "3": "zoo"}
    run = {"repeats": [
        {"results": {
            "1": _res("shop", "SELECT total FROM shop.orders WHERE cid = 1", "no such table: shop.orders"),  # fixed
            "2": _res("shop", "SELECT 1", right=True),  # already right, untouched
            "3": _res("zoo", "SELECT name FROM zoo.animal", "no such column: name"),  # another error: not rerun
        }},
        {"results": {
            "1": _res("shop", "SELECT oid FROM shop.orders", "no such table: shop.orders"),  # runs, still wrong
            "2": _res(None, "", error="APIError: down"),  # API error: left out
            "3": _res("zoo", "SELECT name FROM zoo.keeper", "no such table: zoo.keeper"),  # fixed
        }},
    ]}
    w = prefix_whatif(run, gold, db_of, path_of=lambda d: paths[d])
    assert w["prefix_failures"] == 3 and w["fixed"] == 2
    assert w["right"] == (2 / 3 + 1 / 2) / 2  # per repeat, API errors left out, then averaged
    assert w["same"] == 0.0  # q1: other rows in repeat 2; q3: an error, then rows; q2 left out (API error)


def test_prefix_whatif_same_answer_counts_the_rerun_rows(tmp_path):
    paths = make_dbs(tmp_path)
    fail = _res("shop", "SELECT total FROM shop.orders", "no such table: shop.orders")
    ran = _res("shop", "SELECT total FROM orders") | {"rows_hash": None}
    from agentflow.score import rows_hash
    ran["rows_hash"] = rows_hash([(9.5,), (3.0,)])
    run = {"repeats": [{"results": {"1": fail}}, {"results": {"1": ran}}]}
    w = prefix_whatif(run, {"1": [(9.5,), (3.0,)]}, {"1": "shop"}, path_of=lambda d: paths[d])
    assert w["same"] == 1.0
