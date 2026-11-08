import json

import pytest

from claimsflow.data import load_claims
from claimsflow.models import Result
from claimsflow.report import build_report
from claimsflow.run import LEVELS, main
from claimsflow.score import score


def R(decision, amount, docs):
    return Result(decision, amount, docs, "", "car")


@pytest.fixture
def key_set(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("OPENAI_API_KEY", "test")


@pytest.fixture
def cheap(monkeypatch):
    monkeypatch.setattr("claimsflow.run.estimate_cost_usd", lambda *a, **k: 0.01)


def test_score_counts():
    key = {"a": R("approve_full", 100, []), "b": R("request_documents", 0, ["receipts"]), "c": R("decline", 0, [])}
    got = {"a": R("approve_full", 90, []), "b": R("request_documents", 0, ["receipts"]), "c": R("request_documents", 0, ["claim_form"])}
    s = score(got, key)
    assert (s.n, s.decision_right, s.amount_right, s.doc_caught, s.doc_false_alarms) == (3, 2 / 3, 2 / 3, 1.0, 0.5)


def test_score_doc_caught_needs_same_documents():
    key = {"a": R("request_documents", 0, ["receipts"])}
    got = {"a": R("request_documents", 0, ["claim_form"])}
    assert score(got, key).doc_caught == 0.0


def test_score_counts_errors():
    s = score({"a": R("error", 0, [])}, {"a": R("decline", 0, [])})
    assert s.errors == 1 and s.decision_right == 0.0


def test_run_aborts_over_budget(monkeypatch, key_set, tmp_path):
    monkeypatch.setattr("claimsflow.run.estimate_cost_usd", lambda *a, **k: 12.0)
    assert main(["--level", "0", "--budget", "10", "--yes", "--runs-dir", str(tmp_path)]) == 2
    assert not list(tmp_path.glob("*.json"))


def test_run_requires_key(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("shared.llm.load_dotenv", lambda *a, **k: None)
    monkeypatch.setitem(LEVELS, "0", lambda claim, ctx: pytest.fail("must stop before any level call"))
    with pytest.raises(RuntimeError, match="Missing (OPENAI|ANTHROPIC)_API_KEY"):
        main(["--level", "0", "--yes", "--runs-dir", str(tmp_path)])


def test_dry_run_prints_estimate_and_makes_no_calls(monkeypatch, key_set, tmp_path, capsys):
    monkeypatch.setitem(LEVELS, "0", lambda claim, ctx: pytest.fail("no level call in a dry run"))
    assert main(["--level", "0", "--dry-run", "--runs-dir", str(tmp_path)]) == 0
    assert "Estimated cost" in capsys.readouterr().out


def test_run_continues_after_claim_error(monkeypatch, key_set, cheap, tmp_path):
    first = load_claims()[0].claim_id

    def flaky(claim, ctx):
        if claim.claim_id == first:
            raise RuntimeError("overloaded")
        return Result("decline", 0, [], "x", "car")

    monkeypatch.setitem(LEVELS, "0", flaky)
    assert main(["--level", "0", "--limit", "3", "--repeats", "1", "--yes", "--runs-dir", str(tmp_path)]) == 0
    run = json.loads(next(tmp_path.glob("level-0-*.json")).read_text(encoding="utf-8"))
    results = run["repeats"][0]["results"]
    assert results[first]["decision"] == "error" and "overloaded" in results[first]["reason"]
    assert len(results) == 3


def test_report_without_runs_says_not_run(tmp_path):
    assert "Not run yet" in build_report(tmp_path)


def test_report_has_a_row_per_level(monkeypatch, key_set, cheap, tmp_path):
    monkeypatch.setitem(LEVELS, "1", lambda claim, ctx: Result("decline", 0, [], "x", "car"))
    main(["--level", "1", "--limit", "2", "--repeats", "2", "--yes", "--runs-dir", str(tmp_path)])
    report = build_report(tmp_path)
    assert "| 1 |" in report and "level-1-" in report


def test_run_on_hard_set_uses_hard_claims_and_own_folder(monkeypatch, key_set, cheap, tmp_path):
    seen = []
    monkeypatch.setitem(LEVELS, "0", lambda claim, ctx: seen.append(claim.claim_id) or Result("decline", 0, [], "x", "car"))
    assert main(["--level", "0", "--set", "hard", "--limit", "2", "--repeats", "1", "--yes", "--runs-dir", str(tmp_path)]) == 0
    assert seen and all(cid.startswith("H-") for cid in seen)
    assert list((tmp_path / "hard").glob("level-0-*.json")) and not list(tmp_path.glob("level-0-*.json"))


def test_report_has_a_section_per_set(monkeypatch, key_set, cheap, tmp_path):
    from claimsflow.report import build_results

    monkeypatch.setitem(LEVELS, "0", lambda claim, ctx: Result("decline", 0, [], "x", "car"))
    main(["--level", "0", "--set", "hard", "--limit", "1", "--repeats", "1", "--yes", "--runs-dir", str(tmp_path)])
    text = build_results(tmp_path)
    assert "## Main set" in text and "## Hard set" in text and "level-0-" in text.split("## Hard set")[1]
