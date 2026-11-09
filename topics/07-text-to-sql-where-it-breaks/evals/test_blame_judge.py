import json

import pytest

from sqlblame import judge as judgemod
from sqlblame.judge import read_score
from sqlblame.signals import pick_threshold, signal_rates
from sqlloop.models import Question


def test_read_score():
    assert read_score("<thoughts>x</thoughts><score>0.8</score>") == 0.8
    assert read_score("<score>1.5</score>") is None
    assert read_score("<score>-0.1</score>") is None
    assert read_score("great") is None
    assert read_score("<score>about half</score>") is None


def test_pick_threshold_best_and_tie():
    pairs = [(0.95, True), (0.85, True), (0.45, False), (0.15, False)]
    assert pick_threshold(pairs) == 0.8  # 0.5 .. 0.8 all give 4/4; ties go to the higher threshold
    pairs = [(0.9, True), (0.6, False), (0.55, True), (0.1, False)]
    assert pick_threshold(pairs) == 0.9  # 0.2-0.5: 3/4, 0.6: 2/4, 0.7-0.9: 3/4 -> highest tie


def test_pick_threshold_ignores_unreadable():
    assert pick_threshold([(None, True), (0.9, True), (0.1, False)]) == 0.9


def test_signal_rates():
    rows = [
        {"right": True, "runs": True, "has_output": True, "similarity": 0.9},
        {"right": False, "runs": True, "has_output": True, "similarity": 0.8},
        {"right": False, "runs": True, "has_output": False, "similarity": 0.2},
        {"right": False, "runs": False, "has_output": False, "similarity": None},
    ]
    r = signal_rates(rows, threshold=0.5)
    assert r["runs"] == {"good_when_wrong": 2 / 3, "good_when_right": 1.0}
    assert r["has_output"] == {"good_when_wrong": 1 / 3, "good_when_right": 1.0}
    assert r["similarity"] == {"good_when_wrong": 1 / 2, "good_when_right": 1.0}
    assert r["judge_unreadable"] == 1


QS = [Question(1, "shop", "How much did Ann spend?", "", "SELECT sum(total) FROM orders WHERE cid = 1", "simple")]


def test_judge_calls_once_per_distinct_sql(tmp_path, monkeypatch):
    runs = tmp_path / "runs"
    runs.mkdir()
    out = {"sql": "SELECT 1", "error": "", "right": False}
    run = {"level": "A", "set": "main", "repeats": [{"results": {"1": out}}, {"results": {"1": dict(out)}}]}
    (runs / "level-A-20260101-000000.json").write_text(json.dumps(run), encoding="utf-8")
    calls = []

    def fake(prompt, **kw):
        calls.append(prompt)
        return "<score>0.3</score>"

    monkeypatch.setattr(judgemod, "load_set", lambda name: QS)
    monkeypatch.setattr(judgemod, "llm_call", fake)
    monkeypatch.setattr(judgemod, "require_api_key", lambda m: None)
    assert judgemod.main(["--set", "main", "--yes", "--runs-dir", str(runs)]) == 0
    assert len(calls) == 1 and "SELECT sum(total) FROM orders WHERE cid = 1" in calls[0] and "SELECT 1" in calls[0]
    saved = json.loads(next(runs.glob("judge-*.json")).read_text(encoding="utf-8"))
    assert saved["scores"] == {"A|0|1": 0.3, "A|1|1": 0.3} and saved["set"] == "main"


def test_judge_dry_run_spends_nothing(tmp_path, monkeypatch, capsys):
    runs = tmp_path / "runs"
    runs.mkdir()
    run = {"level": "B", "set": "main", "repeats": [{"results": {"1": {"sql": "SELECT 2", "error": ""}}}]}
    (runs / "level-B-20260101-000000.json").write_text(json.dumps(run), encoding="utf-8")
    monkeypatch.setattr(judgemod, "load_set", lambda name: QS)
    monkeypatch.setattr(judgemod, "llm_call", lambda *a, **k: pytest.fail("called the model"))
    monkeypatch.setattr(judgemod, "require_api_key", lambda m: None)
    assert judgemod.main(["--set", "main", "--dry-run", "--runs-dir", str(runs)]) == 0
    assert "Estimated cost $" in capsys.readouterr().out and not list(runs.glob("judge-*.json"))
