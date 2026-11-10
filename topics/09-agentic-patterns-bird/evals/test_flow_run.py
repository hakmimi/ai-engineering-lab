import json

import openai
import pytest

from agentflow import run as runmod
from flow_helpers import FakeLLM, make_dbs
from shared.llm import CallRecord
from sqlblame.warehouse import load_warehouse
from sqlloop.models import Question

QS = [Question(1, "shop", "How much did Ann spend?", "", "SELECT sum(total) FROM orders WHERE cid = 1", "simple"),
      Question(2, "shop", "How many customers?", "", "SELECT count(*) FROM Customer", "moderate")]


def writer(prompt):
    if "Ann" in prompt:
        return "<sql>SELECT sum(total) FROM orders WHERE cid = 1</sql>"
    return "<sql>SELECT count(*) FROM orders WHERE total > 5</sql>"  # 1, gold says 2: wrong


@pytest.fixture
def setup(tmp_path, monkeypatch):
    paths = make_dbs(tmp_path)
    path_of = lambda d: paths[d]
    monkeypatch.setattr(runmod, "load_set", lambda name: QS)
    monkeypatch.setattr(runmod, "load_cards", lambda: load_warehouse(["shop", "zoo"], path_of=path_of))
    monkeypatch.setattr(runmod, "db_path", path_of)
    monkeypatch.setattr(runmod, "require_api_key", lambda model: None)
    return tmp_path / "runs", monkeypatch


class FakeAPIError(openai.APIError):
    def __init__(self, msg):
        Exception.__init__(self, msg)


def saved(runs_dir):
    files = sorted(runs_dir.rglob("level-*.json"))
    return [json.loads(f.read_text(encoding="utf-8")) for f in files]


def test_dry_run_spends_nothing(setup):
    runs_dir, mp = setup
    mp.setattr(runmod, "llm_call", FakeLLM({}))
    assert runmod.main(["--level", "1", "--dry-run", "--runs-dir", str(runs_dir)]) == 0
    assert saved(runs_dir) == []


def test_over_budget_refuses(setup):
    runs_dir, mp = setup
    mp.setattr(runmod, "llm_call", FakeLLM({}))
    assert runmod.main(["--level", "5", "--yes", "--budget", "0.000001", "--runs-dir", str(runs_dir)]) == 2
    assert saved(runs_dir) == []


def test_full_run_saves_scores_and_consistency(setup):
    runs_dir, mp = setup
    mp.setattr(runmod, "llm_call", FakeLLM({"route": "<database>shop</database>", "write": writer}))
    assert runmod.main(["--level", "1", "--yes", "--repeats", "2", "--runs-dir", str(runs_dir)]) == 0
    (run,) = saved(runs_dir)
    assert (run["level"], run["set"], run["limit"], run["partial"]) == ("1", "main", None, False)
    assert len(run["repeats"]) == 2 and "cost_usd" in run
    r = run["repeats"][0]["results"]
    assert r["1"]["right"] is True and r["1"]["rows_hash"] and r["1"]["db"] == "shop"
    assert run["consistency"]["n"] == 2 and run["consistency"]["same"] == 1.0


def test_right_needs_the_right_database(setup):
    runs_dir, mp = setup
    # "SELECT 2" on zoo returns the gold rows (2), but zoo is not the question's database
    mp.setattr(runmod, "llm_call", FakeLLM({"route": "<database>zoo</database>", "write": "<sql>SELECT 2</sql>"}))
    assert runmod.main(["--level", "1", "--yes", "--repeats", "1", "--runs-dir", str(runs_dir)]) == 0
    r = saved(runs_dir)[0]["repeats"][0]["results"]["2"]
    assert r["db"] == "zoo" and r["final_error"] == "" and r["right"] is False


def test_api_error_is_recorded_not_scored(setup):
    runs_dir, mp = setup
    mp.setattr(runmod, "llm_call", FakeLLM({"route": FakeAPIError("connection down")}))
    assert runmod.main(["--level", "1", "--yes", "--repeats", "1", "--runs-dir", str(runs_dir)]) == 0
    run = saved(runs_dir)[0]
    assert run["repeats"][0]["scores"]["api_errors"] == 2 and run["repeats"][0]["scores"]["right"] is None
    assert "connection down" in run["repeats"][0]["results"]["1"]["error"]


def test_limit_marks_a_smoke_run(setup):
    runs_dir, mp = setup
    mp.setattr(runmod, "llm_call", FakeLLM({"route": "<database>shop</database>", "write": writer}))
    assert runmod.main(["--level", "1", "--yes", "--limit", "1", "--repeats", "1", "--runs-dir", str(runs_dir)]) == 0
    run = saved(runs_dir)[0]
    assert run["limit"] == 1 and run["questions"] == 1


def test_measured_estimate_from_the_latest_smoke_run(tmp_path):
    d = tmp_path / "main"
    d.mkdir()
    (d / "level-2-20261110-100000.json").write_text(json.dumps({"limit": 5, "cost_usd": 0.01, "questions": 5,
                                                                 "repeats": [{}]}), encoding="utf-8")
    (d / "level-2-20261110-110000.json").write_text(json.dumps({"limit": None, "cost_usd": 9, "questions": 60,
                                                                 "repeats": [{}]}), encoding="utf-8")
    assert runmod.measured_estimate("2", 60, 3, tmp_path) == pytest.approx(0.01 / 5 * 60 * 3 * runmod.SMOKE_MARGIN)
    assert runmod.measured_estimate("3", 60, 3, tmp_path) is None


def test_a_bug_in_our_code_crashes_the_run_but_the_spend_is_saved(setup):
    runs_dir, mp = setup
    mp.setattr(runmod, "llm_call", FakeLLM({"route": "<database>shop</database>", "write": KeyError("bug")}))
    with pytest.raises(KeyError):
        runmod.main(["--level", "1", "--yes", "--repeats", "2", "--runs-dir", str(runs_dir)])
    (run,) = saved(runs_dir)
    assert run["partial"] is True and "cost_usd" in run


def test_a_failing_gold_query_stops_before_any_model_call(setup):
    runs_dir, mp = setup
    llm = FakeLLM({})
    mp.setattr(runmod, "llm_call", llm)
    mp.setattr(runmod, "load_set", lambda name: QS + [Question(3, "shop", "?", "", "SELECT nope FROM nowhere", "simple")])
    assert runmod.main(["--level", "1", "--yes", "--runs-dir", str(runs_dir)]) == 3
    assert llm.calls == [] and saved(runs_dir) == []


def costly(reply):
    """A fake model call that bills $0.006 (12,000 output tokens on gpt-6-luna)."""
    def llm(prompt, *, tracker=None, label="", **kw):
        tracker.add(CallRecord(label=label, model="gpt-6-luna", seconds=0.0, input_tokens=0, output_tokens=12000,
                               cache_write_tokens=0, cache_read_tokens=0))
        return reply(label)
    return llm


def test_budget_is_checked_inside_a_repeat(setup):
    runs_dir, mp = setup
    mp.setattr(runmod, "llm_call", costly(lambda label: "<database>shop</database>" if label == "route" else "<sql>SELECT 1</sql>"))
    assert runmod.main(["--level", "1", "--yes", "--repeats", "1", "--workers", "1", "--budget", "0.01",
                        "--runs-dir", str(runs_dir)]) == 0
    (run,) = saved(runs_dir)
    assert run["partial"] is True and run["cost_usd"] == pytest.approx(0.012)
    assert run["repeats"][0]["results"]["2"]["error"] == "skipped: over budget"


def test_seconds_time_the_level_not_the_scoring(setup):
    runs_dir, mp = setup
    mp.setattr(runmod, "llm_call", FakeLLM({"route": "<database>shop</database>", "write": writer}))
    calls = []
    real = runmod.run_sql
    def slow_run(*a, **k):
        import time
        calls.append(1)
        time.sleep(0.3)
        return real(*a, **k)
    mp.setattr(runmod, "run_sql", slow_run)
    assert runmod.main(["--level", "1", "--yes", "--repeats", "1", "--runs-dir", str(runs_dir)]) == 0
    r = saved(runs_dir)[0]["repeats"][0]["results"]
    assert calls and all(o["seconds"] < 0.25 for o in r.values())
