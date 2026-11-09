import json

import pytest

from blame_helpers import make_dbs
from sqlblame import run as runmod
from sqlblame.warehouse import load_warehouse
from sqlloop.models import Question

QS = [Question(1, "shop", "How much did Ann spend?", "", "SELECT sum(total) FROM orders WHERE cid = 1", "simple"),
      Question(2, "shop", "How many customers?", "", "SELECT count(*) FROM Customer", "moderate")]
GOLD = {"1": ["orders"], "2": ["Customer"]}


@pytest.fixture
def setup(tmp_path, monkeypatch):
    paths = make_dbs(tmp_path)
    path_of = lambda d: paths[d]
    monkeypatch.setattr(runmod, "load_set", lambda name: QS)
    monkeypatch.setattr(runmod, "load_gold", lambda: GOLD)
    monkeypatch.setattr(runmod, "load_cards", lambda: load_warehouse(["shop", "zoo"], path_of=path_of))
    monkeypatch.setattr(runmod, "db_path", path_of)
    monkeypatch.setattr(runmod, "require_api_key", lambda model: None)
    runmod._gold_rows.cache_clear()
    return tmp_path / "runs"


def answers(by_question):
    def llm(prompt, *, label="", **kw):
        if label == "agent":
            return "<tables>shop.orders</tables>"
        for key, a in by_question.items():
            if key in prompt:
                if isinstance(a, Exception):
                    raise a
                return a
        raise AssertionError(prompt)
    return llm


def test_dry_run_spends_nothing(setup, monkeypatch, capsys):
    monkeypatch.setattr(runmod, "llm_call", lambda *a, **k: pytest.fail("called the model"))
    assert runmod.main(["--level", "C", "--dry-run", "--runs-dir", str(setup)]) == 0
    assert "Estimated cost $" in capsys.readouterr().out and not setup.exists()


def test_over_budget_does_not_run(setup, monkeypatch):
    monkeypatch.setattr(runmod, "estimate_cost_usd", lambda *a, **k: 3.0)
    assert runmod.main(["--level", "A", "--budget", "1", "--yes", "--runs-dir", str(setup)]) == 2


def test_ceiling_counts_judge_files(setup, monkeypatch):
    (setup / "smoke").mkdir(parents=True)
    (setup / "smoke" / "judge-x.json").write_text(json.dumps({"cost_usd": 9.99, "scores": {}}), encoding="utf-8")
    monkeypatch.setattr(runmod, "estimate_cost_usd", lambda *a, **k: 0.05)
    assert runmod.spent_in_runs(setup) == pytest.approx(9.99)
    assert runmod.main(["--level", "A", "--yes", "--runs-dir", str(setup)]) == 2


def test_run_file_records_n_rows_and_error(setup, monkeypatch):
    monkeypatch.setattr(runmod, "llm_call", answers({
        "Ann": "<sql>SELECT sum(total) FROM orders WHERE cid = 1</sql>",
        "customers": "<sql>SELECT nope FROM Customer</sql>"}))
    assert runmod.main(["--level", "C", "--repeats", "1", "--yes", "--workers", "1", "--runs-dir", str(setup)]) == 0
    run = json.loads(next(setup.glob("level-C-*.json")).read_text(encoding="utf-8"))
    res = run["repeats"][0]["results"]
    assert res["1"]["right"] is True and res["1"]["n_rows"] == 1 and res["1"]["final_error"] == ""
    assert res["1"]["picked"] == [["shop", "orders"]] and res["1"]["sql"]
    assert res["2"]["right"] is False and "nope" in res["2"]["final_error"] and res["2"]["n_rows"] is None
    assert run["repeats"][0]["scores"]["overlap"] == 0.5 and run["model"] and run["set"] == "main"


def test_api_error_counted_not_scored(setup, monkeypatch):
    monkeypatch.setattr(runmod, "llm_call", answers({
        "Ann": "<sql>SELECT sum(total) FROM orders WHERE cid = 1</sql>",
        "customers": RuntimeError("APITimeoutError: boom")}))
    assert runmod.main(["--level", "A", "--repeats", "1", "--yes", "--workers", "1", "--runs-dir", str(setup)]) == 0
    s = json.loads(next(setup.glob("level-A-*.json")).read_text(encoding="utf-8"))["repeats"][0]["scores"]
    assert s["api_errors"] == 1 and s["right"] == 1.0


def test_measured_estimate_uses_smoke_cost_with_margin(setup):
    (setup / "smoke").mkdir(parents=True)
    run = {"repeats": [{"results": {"1": {"cost_usd": 0.001}, "2": {"cost_usd": 0.003}}}]}
    (setup / "smoke" / "level-B-1.json").write_text(json.dumps(run), encoding="utf-8")
    assert runmod.measured_estimate("level-B", 10, 3, setup) == pytest.approx(0.002 * 10 * 3 * 1.5)
    assert runmod.measured_estimate("level-A", 10, 3, setup) is None
