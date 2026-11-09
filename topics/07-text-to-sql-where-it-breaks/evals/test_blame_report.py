import json

from sqlblame.charts import build_charts
from sqlblame.report import build, gaps, signal_rows


def outcome(right, sql="SELECT 1", n_rows=1, picked=None):
    return {"right": right, "error": "", "final_error": "", "n_rows": n_rows, "sql": sql, "picked": picked,
            "made_up": [] if picked is not None else None, "agent_empty": False, "cost_usd": 0.001, "seconds": 2.0}


def write_run(folder, level, right_share, stamp="20260101-000000"):
    folder.mkdir(parents=True, exist_ok=True)
    results = {str(i): outcome(i < right_share * 10, picked=[["x", "t"]] if level == "C" else None) for i in range(10)}
    scores = {"n": 10, "api_errors": 0, "right": right_share, "runs": 1.0, "has_output": 1.0, "final_errors": 0,
              "by_difficulty": {"simple": right_share, "moderate": None, "challenging": None},
              "overlap": 0.9 if level == "C" else None, "all_found": 0.8 if level == "C" else None,
              "exact": 0.5 if level == "C" else None, "extra": 0.4 if level == "C" else None,
              "wrong_db": 0.0 if level == "C" else None, "made_up": 0 if level == "C" else None,
              "agent_empty": 0 if level == "C" else None, "right_all_found": 0.6 if level == "C" else None,
              "right_missing": 0.2 if level == "C" else None}
    run = {"level": level, "model": "gpt-6-luna", "set": "main", "repeats": [{"results": results, "scores": scores}]}
    (folder / f"level-{level}-{stamp}.json").write_text(json.dumps(run), encoding="utf-8")


def test_gaps_in_points():
    assert gaps({"A": 0.50, "B": 0.60, "C": 0.55}) == {"B − A": "+10", "B − C": "+5", "C − A": "+5"}
    assert gaps({"A": 0.50, "B": None, "C": 0.40})["B − A"] == "–"


def test_build_shows_levels_gaps_agent_and_missing(tmp_path):
    runs = tmp_path / "runs"
    write_run(runs, "A", 0.5)
    write_run(runs, "B", 0.6)
    write_run(runs, "C", 0.55, stamp="20260101-000001")
    write_run(runs, "C", 0.10)  # older file: ignored
    text = build(runs, "main", threshold=None)
    assert "| A · whole database | 50% |" in text and "| C · table agent, whole warehouse | 55% |" in text
    assert "B − A | +10" in text and "B − C | +5" in text
    assert "| 90% | 80% | 50% |" in text  # overlap, all found, exact
    held = build(runs, "test", threshold=None)
    assert "No runs yet" in held


def test_signal_rows_join_judge_scores(tmp_path):
    runs = tmp_path / "runs"
    write_run(runs, "A", 0.5)
    judge = {"scores": {f"A|0|{i}": (0.9 if i < 5 else 0.2) for i in range(10)}}
    (runs / "judge-20260101-000000.json").write_text(json.dumps(judge), encoding="utf-8")
    rows = signal_rows(runs, "main")
    assert len(rows) == 10 and rows[0]["similarity"] == 0.9 and rows[0]["right"] is True
    text = build(runs, "main", threshold=0.5)
    assert "threshold 0.5, picked on the main set" in text


def test_charts_written(tmp_path):
    runs = tmp_path / "runs"
    for lv, r in (("A", 0.5), ("B", 0.6), ("C", 0.55)):
        write_run(runs, lv, r)
    paths = build_charts(runs, tmp_path / "charts")
    assert {p.name for p in paths} >= {"right-by-level.svg", "table-agent.svg"}
    assert all(p.read_text(encoding="utf-8").startswith("<svg") for p in paths)
