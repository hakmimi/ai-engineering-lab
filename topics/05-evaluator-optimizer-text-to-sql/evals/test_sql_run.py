import json

import pytest

from sql_helpers import make_db
from sqlloop import run as runmod
from sqlloop.models import Question

QS = [Question(1, "t", "Alameda schools?", "", "SELECT name FROM school WHERE county = 'Alameda'", "simple"),
      Question(2, "t", "How many schools?", "", "SELECT COUNT(*) FROM school", "moderate")]


@pytest.fixture
def setup(tmp_path, monkeypatch):
    db = make_db(tmp_path / "t.sqlite")
    monkeypatch.setattr(runmod, "load_set", lambda name: QS)
    monkeypatch.setattr(runmod, "db_path", lambda db_id: db)
    monkeypatch.setattr(runmod, "require_api_key", lambda model: None)
    runmod._gold.cache_clear()
    return tmp_path


def fake_llm(answers):
    def llm(prompt, **kw):
        if "How many" in prompt:
            raise RuntimeError("APITimeoutError: boom")
        return answers
    return llm


def test_dry_run_prints_estimate_and_makes_no_calls(setup, monkeypatch, capsys):
    monkeypatch.setattr(runmod, "llm_call", lambda *a, **k: pytest.fail("called the model"))
    assert runmod.main(["--level", "1", "--dry-run", "--runs-dir", str(setup / "runs")]) == 0
    assert "Estimated cost $" in capsys.readouterr().out
    assert not (setup / "runs").exists()


def test_over_budget_aborts(setup, monkeypatch):
    monkeypatch.setattr(runmod, "estimate_cost_usd", lambda *a: 3.0)
    assert runmod.main(["--level", "1", "--budget", "1", "--yes", "--runs-dir", str(setup / "runs")]) == 2


def test_topic_ceiling_counts_earlier_runs(setup, monkeypatch):
    runs = setup / "runs" / "smoke"
    runs.mkdir(parents=True)
    (runs / "level-1-x.json").write_text(json.dumps({"repeats": [{"results": {"1": {"cost_usd": 9.99}}}]}), encoding="utf-8")
    monkeypatch.setattr(runmod, "estimate_cost_usd", lambda *a: 0.05)
    assert runmod.main(["--level", "1", "--yes", "--runs-dir", str(setup / "runs")]) == 2


def test_run_scores_against_gold_and_records_errors(setup, monkeypatch):
    good = "<sql>SELECT name FROM school WHERE county = 'Alameda' ORDER BY name DESC</sql>"
    monkeypatch.setattr(runmod, "llm_call", fake_llm(good))
    assert runmod.main(["--level", "0", "--repeats", "1", "--yes", "--runs-dir", str(setup / "runs"), "--workers", "1"]) == 0
    run = json.loads(next((setup / "runs").glob("level-0-*.json")).read_text(encoding="utf-8"))
    res = run["repeats"][0]["results"]
    assert res["1"]["right"] is True and res["1"]["rounds"][0]["right"] is True
    assert res["2"]["error"].startswith("RuntimeError") and res["2"]["right"] is False
    assert run["repeats"][0]["scores"]["api_errors"] == 1 and run["repeats"][0]["scores"]["right"] == 1


def test_wrong_sql_is_scored_wrong(setup, monkeypatch):
    monkeypatch.setattr(runmod, "llm_call", fake_llm("<sql>SELECT name FROM school</sql>"))
    runmod.main(["--level", "0", "--repeats", "1", "--yes", "--limit", "1", "--runs-dir", str(setup / "runs")])
    run = json.loads(next((setup / "runs").glob("level-0-*.json")).read_text(encoding="utf-8"))
    assert run["repeats"][0]["results"]["1"]["right"] is False


def test_smoke_and_test_runs_go_to_their_own_folders(setup, monkeypatch):
    monkeypatch.setattr(runmod, "llm_call", fake_llm("<sql>SELECT 1</sql>"))
    runmod.main(["--level", "0", "--repeats", "1", "--yes", "--limit", "1", "--smoke", "--runs-dir", str(setup / "runs")])
    runmod.main(["--level", "0", "--repeats", "1", "--yes", "--limit", "1", "--set", "test", "--runs-dir", str(setup / "runs")])
    assert list((setup / "runs" / "smoke").glob("level-0-*.json"))
    assert list((setup / "runs" / "test").glob("level-0-*.json"))


def test_teacher_levels_use_small_writer_and_large_grader():
    from shared.llm import default_model
    for lvl in ("4", "5"):
        assert runmod.model_for(lvl) == default_model("small")
        assert runmod.grader_for(lvl) == default_model("large")
    assert runmod.grader_for("1") == runmod.model_for("1")
    assert runmod.grader_for("0") is None


def _smoke_file(runs_dir, level, costs):
    (runs_dir / "smoke").mkdir(parents=True, exist_ok=True)
    res = {str(i): {"cost_usd": c, "rounds": []} for i, c in enumerate(costs)}
    (runs_dir / "smoke" / f"level-{level}-20260101-000000.json").write_text(
        json.dumps({"level": level, "repeats": [{"results": res}]}), encoding="utf-8")


def test_measured_estimate_uses_smoke_cost_with_margin(tmp_path):
    assert runmod.measured_estimate("4", 60, 3, tmp_path) is None
    _smoke_file(tmp_path, "4", [0.002, 0.004])  # $0.003 per question
    assert runmod.measured_estimate("4", 60, 3, tmp_path) == pytest.approx(0.003 * 60 * 3 * runmod.SMOKE_MARGIN)
    assert runmod.measured_estimate("5", 60, 3, tmp_path) is None


def test_real_run_uses_the_measured_estimate(setup, monkeypatch, capsys):
    monkeypatch.setattr(runmod, "llm_call", lambda *a, **k: pytest.fail("called the model"))
    _smoke_file(setup, "1", [0.001])
    runmod.main(["--level", "1", "--runs-dir", str(setup), "--dry-run"])
    assert "measured in the smoke run" in capsys.readouterr().out
