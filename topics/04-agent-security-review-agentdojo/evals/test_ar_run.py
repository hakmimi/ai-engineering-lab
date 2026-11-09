import json

from ar_helpers import fake_llm

from agentreview import run as runner
from agentreview.data import load_key
from agentreview.report import build_results
from shared.llm import CallRecord


def _main(tmp_path, *args):
    return runner.main([*args, "--runs-dir", str(tmp_path)])


def test_dry_run_prints_the_estimate_and_calls_nothing(tmp_path, monkeypatch, capsys):
    calls = fake_llm(monkeypatch, {})
    assert _main(tmp_path, "--level", "2", "--set", "main", "--limit", "3", "--dry-run") == 0
    assert "Estimated cost $" in capsys.readouterr().out and calls == []
    assert not list(tmp_path.rglob("*.json"))


def test_refuses_when_the_topic_ceiling_would_be_passed(tmp_path, monkeypatch, capsys):
    (tmp_path / "old.json").write_text(json.dumps({"cost_usd": 5.0}), encoding="utf-8")
    calls = fake_llm(monkeypatch, {"l1:": "<score>0</score>"})
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    assert _main(tmp_path, "--level", "1", "--set", "main", "--limit", "2", "--yes") == 2
    assert "ceiling" in capsys.readouterr().out and calls == []


def test_budget_stop_marks_the_run_partial(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    calls = []

    def expensive(prompt, *, label="", tracker=None, **kwargs):  # every call costs $2 (4M output tokens)
        calls.append(label)
        tracker.add(CallRecord(label, "claude-haiku-5-5", 0.1, 0, 4_000_000, 0, 0))
        return "<score>0</score>"

    monkeypatch.setattr("agentreview.levels.llm_call", expensive)
    assert _main(tmp_path, "--level", "1", "--set", "main", "--limit", "4", "--repeats", "1", "--yes", "--budget", "1", "--workers", "1") == 0
    run = json.loads(next(tmp_path.rglob("level-1-*.json")).read_text(encoding="utf-8"))
    assert run["partial"] is True and len(calls) == 1 and len(run["repeats"][0]["verdicts"]) == 1


def test_level0_runs_once_without_a_key_or_a_model(tmp_path, monkeypatch):
    calls = fake_llm(monkeypatch, {})
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert _main(tmp_path, "--level", "0", "--set", "test", "--repeats", "3", "--yes") == 0
    run = json.loads(next(tmp_path.rglob("level-0-*.json")).read_text(encoding="utf-8"))
    assert len(run["repeats"]) == 1 and len(run["repeats"][0]["verdicts"]) == 90 and calls == []
    assert run["cost_usd"] == 0 and run["limit"] is None and run["partial"] is False


def test_report_says_not_run_yet_for_missing_runs(tmp_path):
    text = build_results(tmp_path)
    assert "not run yet" in text and "Article said" in text


def test_report_builds_tables_from_a_fake_run_file(tmp_path, monkeypatch):
    calls = fake_llm(monkeypatch, {})
    _main(tmp_path, "--level", "0", "--set", "main", "--yes")
    text = build_results(tmp_path)
    key = load_key("main")
    assert sum(k == "bad" for k in key.values()) == 30
    assert "| 0 · rules only |" in text and "| 2-cheap |" in text and calls == []
    row = next(line for line in text.splitlines() if line.startswith("| 0 · rules only |"))
    assert row.count("%") >= 4


def test_an_api_failure_is_saved_as_failed_not_as_a_reviewer_error(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")

    def overloaded(prompt, **kwargs):
        raise RuntimeError("529 overloaded")

    monkeypatch.setattr("agentreview.levels.llm_call", overloaded)
    assert _main(tmp_path, "--level", "1", "--set", "main", "--limit", "2", "--repeats", "1", "--yes") == 0
    run = json.loads(next(tmp_path.rglob("level-1-*.json")).read_text(encoding="utf-8"))
    rep = run["repeats"][0]
    assert {v["status"] for v in rep["verdicts"].values()} == {"failed"}
    assert all("529 overloaded" in e for e in rep["errors"].values())


def _write_run(runs_dir, set_name, level, reps):
    """A full run file: reps = list of {sid: Verdict-like dict}."""
    from agentreview.data import load_sessions

    sids = [s.sid for s in load_sessions(set_name)]
    out = runs_dir / set_name
    out.mkdir(parents=True, exist_ok=True)
    repeats = [{"verdicts": {sid: r(sid) for sid in sids}, "seconds": {sid: 1.0 for sid in sids},
                "cost_usd": {sid: 0.001 for sid in sids}, "calls": {sid: 1 for sid in sids}} for r in reps]
    run = {"level": level, "set": set_name, "model": "claude-haiku-5-5", "limit": None, "partial": False, "cost_usd": 0.0, "repeats": repeats}
    (out / f"level-{level}-20261110-000000.json").write_text(json.dumps(run), encoding="utf-8")


def test_report_shows_quote_fails_styles_and_the_fooled_noise_floor(tmp_path):
    from agentreview.data import load_key

    test_kind = load_key("test")
    act = {"score": 80, "band": "act", "findings": [], "status": "ok", "hits": [], "tries": ["quote_fail", "ok"]}
    routine = {"score": 0, "band": "routine", "findings": [], "status": "ok", "hits": [], "tries": ["ok"]}
    _write_run(tmp_path, "test", "2", [lambda sid: act if test_kind[sid] == "bad" else routine] * 2)
    _write_run(tmp_path, "fooled", "2", [lambda sid: routine] * 2)
    text = build_results(tmp_path)
    held_out = text.split("## Held-out set")[1]
    row = next(line for line in held_out.splitlines() if line.startswith("| 2 · the article's way |"))
    assert "| 100% |" in row and "| 30.0 |" in row  # caught 100%; quote fails: the 30 bad sessions, 1 each
    assert "tool_knowledge" in text and "ignore_previous" in text  # held-out caught by attack style
    fooled_part = text.split("## Fooled set")[1]
    fooled_row = next(line for line in fooled_part.splitlines() if line.startswith("| 2 · the article's way | 100%"))
    assert "chance flips between repeats: 0%" in fooled_row
