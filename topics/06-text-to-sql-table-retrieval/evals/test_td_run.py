import json

import pytest

from shared.llm import CallRecord
from tablefind import data, levels, run
from tablefind.build_data import build
from td_helpers import make_raw
from test_td_levels import FakeEmbedder


@pytest.fixture
def setup(tmp_path, monkeypatch):
    out = tmp_path / "data"
    build(make_raw(tmp_path), out)
    monkeypatch.setattr(data, "DATA", out)
    monkeypatch.setattr(run, "make_embedder", lambda: FakeEmbedder())
    monkeypatch.setattr(run, "require_api_key", lambda model: None)
    runs = tmp_path / "runs"
    set_name = "main" if data.load_questions("main") else "test"
    return runs, set_name


def _files(runs):
    return sorted(runs.rglob("*.json")) if runs.exists() else []


def test_dry_run_writes_nothing(setup, capsys):
    runs, s = setup
    assert run.main(["--level", "2", "--set", s, "--dry-run", "--runs-dir", str(runs)]) == 0
    assert _files(runs) == []
    assert "Estimated cost $" in capsys.readouterr().out


def test_ceiling_blocks_run(setup):
    runs, s = setup
    (runs / "main").mkdir(parents=True)
    (runs / "main" / "old.json").write_text(json.dumps({"cost_usd": run.TOPIC_CEILING_USD}), encoding="utf-8")
    assert run.main(["--level", "2", "--set", s, "--yes", "--runs-dir", str(runs)]) == 2
    assert len(_files(runs)) == 1


def test_api_exception_is_failed_not_scored(setup, monkeypatch):
    runs, s = setup

    def boom(prompt, **kw):
        raise RuntimeError("APIConnectionError: timed out")

    monkeypatch.setattr(levels, "llm_call", boom)
    assert run.main(["--level", "2", "--set", s, "--repeats", "1", "--yes", "--runs-dir", str(runs)]) == 0
    saved = json.loads(_files(runs)[0].read_text(encoding="utf-8"))
    rep = saved["repeats"][0]
    assert {a["status"] for a in rep["answers"].values()} == {"failed"}
    assert all("timed out" in e for e in rep["errors"].values())
    assert saved["level"] == "2" and saved["limit"] is None and saved["partial"] is False


def test_budget_stop_marks_partial(setup, monkeypatch):
    runs, s = setup

    def pricey(prompt, **kw):
        kw["tracker"].add(CallRecord(kw["label"], kw["model"], 0.1, 10_000_000, 0, 0, 0))  # $1.00 on gpt-6-luna
        return "<tables>\nalpha_large.projects\n</tables>"

    monkeypatch.setattr(levels, "llm_call", pricey)
    args = ["--level", "2", "--set", s, "--repeats", "3", "--budget", "0.5", "--workers", "1", "--yes", "--runs-dir", str(runs)]
    assert run.main(args) == 0
    saved = json.loads(_files(runs)[0].read_text(encoding="utf-8"))
    assert saved["partial"] is True and len(saved["repeats"]) == 1
    assert len(saved["repeats"][0]["answers"]) == 1


def test_level0_needs_no_key_and_costs_nothing(setup, monkeypatch):
    runs, s = setup
    monkeypatch.setattr(run, "require_api_key", lambda model: (_ for _ in ()).throw(AssertionError("no key needed")))
    assert run.main(["--level", "0", "--set", s, "--yes", "--runs-dir", str(runs)]) == 0
    saved = json.loads(_files(runs)[0].read_text(encoding="utf-8"))
    assert saved["cost_usd"] == 0 and len(saved["repeats"]) == 1


def test_estimate_over_budget_refuses_before_spending(setup, monkeypatch):
    runs, s = setup
    monkeypatch.setattr(run, "estimate_cost_usd", lambda *a, **k: 1.2)
    assert run.main(["--level", "3", "--set", s, "--yes", "--budget", "1.0", "--runs-dir", str(runs)]) == 3
    assert _files(runs) == []


def test_estimate_prices_output_at_max_tokens():
    from tablefind.data import Question
    from tablefind.levels import RERANK_MAX_TOKENS
    q = [Question("m-1", "x")]
    t = [type("T", (), {"columns": (), "db": "a", "name": "b", "id": "a.b"})()]
    est = run.estimate_cost_usd("2", q, t, "gpt-6-luna", 1)
    assert est >= RERANK_MAX_TOKENS * 0.50 / 1_000_000


def test_run_file_saved_after_each_repeat_and_llm_seconds_kept(setup, monkeypatch):
    runs, s = setup
    calls = {"n": 0}

    def flaky(prompt, **kw):
        calls["n"] += 1
        kw["tracker"].add(CallRecord(kw["label"], kw["model"], 0.25, 1000, 10, 0, 0))
        if calls["n"] > len(data.load_questions(s)):  # repeat 2 dies hard
            raise KeyboardInterrupt
        return "<tables>\nalpha_large.projects\n</tables>"

    monkeypatch.setattr(levels, "llm_call", flaky)
    with pytest.raises(KeyboardInterrupt):
        run.main(["--level", "2", "--set", s, "--repeats", "3", "--workers", "1", "--yes", "--runs-dir", str(runs)])
    saved = json.loads(_files(runs)[0].read_text(encoding="utf-8"))
    assert saved["partial"] is True and len(saved["repeats"]) == 1 and saved["cost_usd"] > 0
    assert set(saved["repeats"][0]["llm_seconds"].values()) == {0.25}
