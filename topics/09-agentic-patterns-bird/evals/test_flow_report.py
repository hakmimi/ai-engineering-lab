from agentflow.report import build_charts, build_results, level_row
from shared.runs import save_run


def scores(right, cost=0.001, seconds=2.0, **extra):
    base = {"n": 2, "api_errors": 0, "right": right, "right_db": 1.0, "no_answer": 0.0, "sql_errors": 0.0, "cost": cost,
            "seconds": seconds, "calls": 2.0, "handoff": 0.0, "right_rest": right, "agree": None, "n_sub": None,
            "rounds": None, "steps": None, "cap": 0.0}
    return base | extra


def fake_run(runs_dir, level, rights, **extra):
    save_run(runs_dir, "main", level, {"model": "m", "limit": None, "partial": False, "questions": 2, "cost_usd": 0.01,
                                       "repeats": [{"results": {}, "scores": scores(r, **extra)} for r in rights],
                                       "consistency": {"n": 2, "same": 0.5, "right_all": 0.5}})


def test_level_row_averages_over_repeats():
    run = {"repeats": [{"scores": scores(0.5)}, {"scores": scores(1.0, api_errors=1)}],
           "consistency": {"n": 2, "same": 1.0, "right_all": 0.5}}
    row = level_row("1", run)
    assert row.startswith("| 1 · routing | 75% | 50–100% | 100% | 50% | 2 | 100% |")
    assert row.rstrip().endswith("| 1 |")


def test_results_with_missing_levels_and_sets(tmp_path):
    fake_run(tmp_path, "1", [0.5, 0.5, 0.5])
    fake_run(tmp_path, "5", [0.0, 0.5, 1.0], steps=6.0, cap=0.1)
    text = build_results(tmp_path)
    assert "| 1 · routing | 50% |" in text and "| 5 · free agent | 50% |" in text
    assert "| 2 · parallel vote | not run |" in text
    assert "Held-out set" in text and "No full run yet" in text
    assert "6.0 steps" in text and "cap hit 10%" in text
    assert "Model: m." in text
    assert "moved by up to 100 points" in text  # level 5's repeats: 0% to 100%


def test_handoff_level_is_marked_as_helped(tmp_path):
    fake_run(tmp_path, "1h", [0.5])
    fake_run(tmp_path, "5", [0.5])
    assert "1h · routing + handoff (a person helps)" in build_results(tmp_path)


def test_smoke_runs_are_not_reported(tmp_path):
    save_run(tmp_path, "main", "1", {"model": "m", "limit": 5, "partial": False, "questions": 5, "cost_usd": 0.01,
                                     "repeats": [{"results": {}, "scores": scores(0.9)}], "consistency": {}})
    text = build_results(tmp_path)
    assert "90%" not in text and text.count("No full run yet") == 2


def test_charts_written(tmp_path):
    fake_run(tmp_path, "1", [0.5])
    written = build_charts(tmp_path, tmp_path / "charts")
    assert sorted(p.name for p in written) == ["cost.svg", "right-by-level.svg", "same-answer.svg", "seconds.svg"]
    assert "not run" in (tmp_path / "charts" / "right-by-level.svg").read_text(encoding="utf-8")


def test_no_charts_without_runs(tmp_path):
    assert build_charts(tmp_path, tmp_path / "charts") == []
