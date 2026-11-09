import json

from sqlloop import report


def _run(level, right, cost=0.01):
    res = {"1": {"rounds": [{"right": right, "verdict": "PASS"}], "stop": "pass", "error": "", "right": right,
                 "first_right": right, "final_error": "", "seconds": 2.0, "calls": [], "cost_usd": cost}}
    return {"level": level, "model": "m", "set": "main", "created": "x", "questions": 1, "repeats": [{"results": res}]}


def test_without_runs_says_not_run(tmp_path):
    text = report.build(tmp_path, {"1": "simple"})
    assert "not run yet" in text.lower()


def test_one_row_per_level_latest_wins_smoke_ignored(tmp_path):
    (tmp_path / "smoke").mkdir()
    (tmp_path / "level-0-20260101-000000.json").write_text(json.dumps(_run("0", False)), encoding="utf-8")
    (tmp_path / "level-0-20260102-000000.json").write_text(json.dumps(_run("0", True)), encoding="utf-8")
    (tmp_path / "level-1-20260101-000000.json").write_text(json.dumps(_run("1", False)), encoding="utf-8")
    (tmp_path / "smoke" / "level-2-20260101-000000.json").write_text(json.dumps(_run("2", True)), encoding="utf-8")
    text = report.build(tmp_path, {"1": "simple"})
    rows = [l for l in text.splitlines() if l.startswith("| 0 ") or l.startswith("| 1 ") or l.startswith("| 2 ")]
    assert len([r for r in rows if r.startswith("| 0 ")]) == 2  # main table + difficulty table
    assert "100%" in [r for r in rows if r.startswith("| 0 ")][0]
    assert not any(r.startswith("| 2 ") for r in rows)


def test_main_fills_lenient_column_for_held_out_set(tmp_path, monkeypatch):
    from types import SimpleNamespace
    (tmp_path / "test").mkdir()
    (tmp_path / "level-0-20260101-000000.json").write_text(json.dumps(_run("0", True)), encoding="utf-8")
    (tmp_path / "test" / "level-0-20260101-000000.json").write_text(json.dumps(_run("0", True)), encoding="utf-8")
    (tmp_path / "lenient.json").write_text(json.dumps({"main/0/x": [0.25], "test/0/x": [0.75]}), encoding="utf-8")
    monkeypatch.setattr(report, "RUNS_DIR", tmp_path)
    monkeypatch.setattr(report, "RESULTS", tmp_path / "results.md")
    monkeypatch.setattr(report, "load_set", lambda name: [SimpleNamespace(qid=1, difficulty="simple")])
    monkeypatch.setattr(report, "spent_in_runs", lambda d: 0.0)
    report.main()
    main_part, test_part = (tmp_path / "results.md").read_text(encoding="utf-8").split("## Held-out")
    assert "25%" in main_part and "75%" not in main_part
    assert "75%" in test_part
