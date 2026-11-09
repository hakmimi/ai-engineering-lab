import json

from sql_helpers import make_db
from sqlloop import build_data, data
from sqlloop.models import Question

DBS = [f"db{i:02d}" for i in range(11)]


def _items():
    items, qid = [], 0
    for db in DBS:
        for diff, n in (("simple", 4), ("moderate", 6), ("challenging", 3)):
            for _ in range(n):
                items.append({"question_id": qid, "db_id": db, "question": f"q{qid}?", "evidence": "",
                              "SQL": "SELECT 1", "difficulty": diff})
                qid += 1
    return items


def test_split_is_6_and_5_repeatable_and_disjoint():
    a, b = build_data.split_dbs(DBS, seed=2026)
    assert len(a) == 6 and len(b) == 5
    assert not set(a) & set(b) and set(a) | set(b) == set(DBS)
    assert (a, b) == build_data.split_dbs(list(reversed(DBS)), seed=2026)


def test_draw_takes_counts_per_difficulty_from_its_dbs_only():
    a, _ = build_data.split_dbs(DBS, seed=2026)
    picked, log = build_data.draw(_items(), a, {"simple": 5, "moderate": 8, "challenging": 3}, seed=1, gold_ok=lambda it: (True, ""))
    assert [it["difficulty"] for it in picked].count("moderate") == 8
    assert len(picked) == 16 and {it["db_id"] for it in picked} <= set(a)
    assert log == []
    again, _ = build_data.draw(_items(), a, {"simple": 5, "moderate": 8, "challenging": 3}, seed=1, gold_ok=lambda it: (True, ""))
    assert [it["question_id"] for it in again] == [it["question_id"] for it in picked]


def test_failing_gold_is_replaced_and_logged():
    a, _ = build_data.split_dbs(DBS, seed=2026)
    first, _ = build_data.draw(_items(), a, {"simple": 2, "moderate": 0, "challenging": 0}, seed=1, gold_ok=lambda it: (True, ""))
    bad = first[0]["question_id"]
    picked, log = build_data.draw(_items(), a, {"simple": 2, "moderate": 0, "challenging": 0}, seed=1,
                                  gold_ok=lambda it: (it["question_id"] != bad, "timeout after 30 s"))
    assert len(picked) == 2 and bad not in [it["question_id"] for it in picked]
    assert log == [{"question_id": bad, "db_id": first[0]["db_id"], "reason": "timeout after 30 s"}]


def test_gold_check_runs_the_sql(tmp_path):
    db = make_db(tmp_path / "t.sqlite")
    assert build_data.gold_check(db, "SELECT name FROM school")[0]
    ok, why = build_data.gold_check(db, "SELECT nope FROM school")
    assert not ok and "no such column" in why


def test_load_set_reads_questions(tmp_path, monkeypatch):
    monkeypatch.setattr(data, "DATA_DIR", tmp_path)
    (tmp_path / "main.json").write_text(json.dumps([{"qid": 7, "db_id": "x", "question": "q?", "evidence": "e",
                                                    "gold_sql": "SELECT 1", "difficulty": "simple"}]), encoding="utf-8")
    assert data.load_set("main") == [Question(7, "x", "q?", "e", "SELECT 1", "simple")]
    assert data.db_path("x").name == "x.sqlite"
