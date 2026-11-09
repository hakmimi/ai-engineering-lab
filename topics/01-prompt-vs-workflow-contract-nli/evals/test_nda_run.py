import json

import pytest

from ndaflow.data import load_contracts
from ndaflow.models import STATEMENT_IDS, Answer
from ndaflow.report import build_results
from ndaflow.run import LEVELS, estimate_cost_usd, main, model_for


def all_entailment(contract, ctx):
    return {sid: Answer("entailment", [0]) for sid in STATEMENT_IDS}


@pytest.fixture
def key_set(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test")


@pytest.fixture
def cheap(monkeypatch):
    monkeypatch.setattr("ndaflow.run.estimate_cost_usd", lambda *a, **k: 0.01)


def _run_file(folder):
    return json.loads(next(folder.glob("level-*.json")).read_text(encoding="utf-8"))


def test_models_per_level_without_env_settings(monkeypatch):
    monkeypatch.delenv("CLAIMS_MODEL", raising=False)
    monkeypatch.delenv("CLAIMS_MODEL_LARGE", raising=False)
    assert model_for("3") == "gpt-6-luna" and model_for("0+") == "gpt-6.1-sol"


def test_run_writes_17_answers_per_contract(monkeypatch, key_set, cheap, tmp_path):
    monkeypatch.setitem(LEVELS, "0", all_entailment)
    assert main(["--level", "0", "--limit", "2", "--repeats", "1", "--yes", "--runs-dir", str(tmp_path)]) == 0
    run = _run_file(tmp_path)
    assert (run["level"], run["set"], run["contracts"]) == ("0", "main", 2)
    results = run["repeats"][0]["results"]
    assert len(results) == 2
    one = next(iter(results.values()))
    assert list(one["answers"]) == STATEMENT_IDS and one["answers"]["nda-1"] == {"label": "entailment", "evidence": [0]}
    assert {"seconds", "calls", "cost_usd"} <= set(one)
    assert run["repeats"][0]["scores"]["n_pairs"] == 34


def test_test_set_runs_its_own_contracts_into_its_own_folder(monkeypatch, key_set, cheap, tmp_path):
    seen = []
    monkeypatch.setitem(LEVELS, "0", lambda c, ctx: seen.append(c.doc_id) or all_entailment(c, ctx))
    assert main(["--level", "0", "--set", "test", "--limit", "2", "--repeats", "1", "--yes", "--runs-dir", str(tmp_path)]) == 0
    assert seen and set(seen) <= {c.doc_id for c in load_contracts("test")}
    assert list((tmp_path / "test").glob("level-0-*.json")) and not list(tmp_path.glob("level-0-*.json"))


def test_an_exception_inside_a_contract_gives_17_errors_and_the_run_goes_on(monkeypatch, key_set, cheap, tmp_path):
    first = load_contracts("main")[0].doc_id

    def flaky(contract, ctx):
        if contract.doc_id == first:
            raise RuntimeError("overloaded")
        return all_entailment(contract, ctx)

    monkeypatch.setitem(LEVELS, "0", flaky)
    assert main(["--level", "0", "--limit", "3", "--repeats", "1", "--yes", "--runs-dir", str(tmp_path)]) == 0
    results = _run_file(tmp_path)["repeats"][0]["results"]
    assert len(results) == 3
    assert all(a["label"] == "error" for a in results[first]["answers"].values())
    assert "overloaded" in results[first]["error"]


def test_dry_run_prints_estimate_and_makes_no_calls(monkeypatch, key_set, tmp_path, capsys):
    monkeypatch.setitem(LEVELS, "0", lambda c, ctx: pytest.fail("no level call in a dry run"))
    assert main(["--level", "0", "--dry-run", "--runs-dir", str(tmp_path)]) == 0
    assert "Estimated cost" in capsys.readouterr().out
    assert not list(tmp_path.glob("*.json"))


def test_run_aborts_over_budget(monkeypatch, key_set, tmp_path):
    monkeypatch.setattr("ndaflow.run.estimate_cost_usd", lambda *a, **k: 12.0)
    assert main(["--level", "0", "--budget", "10", "--yes", "--runs-dir", str(tmp_path)]) == 2


def test_estimate_grows_with_calls_per_level():
    contracts = load_contracts("main")[:2]
    small = [estimate_cost_usd(lvl, contracts, "gpt-6-luna", 1) for lvl in ("0", "1", "2", "3")]
    assert small == sorted(small) and small[0] > 0
    assert estimate_cost_usd("0+", contracts, "gpt-6.1-sol", 1) > small[0]


def test_report_without_runs_says_not_run(tmp_path):
    text = build_results(tmp_path)
    assert "## Main set" in text and "## Test set (held out)" in text and "Not run yet" in text


def test_report_has_a_section_per_set_and_ignores_smoke_runs(monkeypatch, key_set, cheap, tmp_path):
    monkeypatch.setitem(LEVELS, "1", all_entailment)
    main(["--level", "1", "--set", "test", "--limit", "1", "--repeats", "1", "--yes", "--runs-dir", str(tmp_path)])
    main(["--level", "2", "--limit", "1", "--repeats", "1", "--yes", "--runs-dir", str(tmp_path / "smoke")])
    text = build_results(tmp_path)
    main_part, test_part = text.split("## Test set (held out)")
    assert "| 1 |" in test_part and "level-1-" in test_part
    assert "| 2 |" not in text  # the smoke run is never read


def test_report_scores_against_the_current_key(monkeypatch, key_set, cheap, tmp_path):
    from ndaflow import report

    monkeypatch.setitem(LEVELS, "0", all_entailment)
    main(["--level", "0", "--limit", "1", "--repeats", "1", "--yes", "--runs-dir", str(tmp_path)])
    first = load_contracts("main")[0].doc_id
    monkeypatch.setattr(report, "load_answer_key", lambda s: {first: {sid: Answer("entailment", [0]) for sid in STATEMENT_IDS}})
    assert "| 0 | gpt-6-luna | 100% | 1.00 | 0.00 | 100% | 100% |" in report.build_results(tmp_path).split("## Test set")[0]
