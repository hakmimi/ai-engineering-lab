import json

import pytest

from ndaspeed import run as runner
from speed_helpers import FakeClient


@pytest.fixture
def runs_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "RUNS_DIR", tmp_path)
    return tmp_path


def test_dry_run_prints_estimate_and_makes_no_call(runs_dir, capsys):
    client = FakeClient()
    assert runner.main(["--test", "0", "--dry-run"], client=client) == 0
    assert client.requests == []
    out = capsys.readouterr().out
    assert "estimate" in out.lower() and "$" in out
    assert list(runs_dir.iterdir()) == []


def test_without_yes_makes_no_call(runs_dir, capsys):
    client = FakeClient()
    assert runner.main(["--test", "0"], client=client) == 0
    assert client.requests == []
    assert "--yes" in capsys.readouterr().out


def test_refuses_over_topic_ceiling(runs_dir, capsys):
    (runs_dir / "test2-old.json").write_text(json.dumps({"spent_usd": 9.99}))
    client = FakeClient()
    assert runner.main(["--test", "2", "--yes"], client=client) == 2
    assert client.requests == []


def test_run_writes_run_file_with_spent_usd(runs_dir):
    client = FakeClient()
    assert runner.main(["--test", "0", "--repeats", "2", "--yes"], client=client) == 0
    files = list(runs_dir.glob("test0-*.json"))
    assert len(files) == 1
    run = json.loads(files[0].read_text(encoding="utf-8"))
    assert run["test"] == "0" and run["spent_usd"] > 0
    assert len(client.requests) == 3  # warm-up + 2


def test_limit_caps_rounds_and_chats():
    assert runner.test_kwargs("1", {"small": "a", "large": "b"}, repeats=None, limit=1) == {"rounds": {"small": 1, "large": 1}}
    assert runner.test_kwargs("2", {"small": "a"}, repeats=None, limit=1) == {"short_n": 1, "long_chats": 1}
    assert runner.test_kwargs("3", {"small": "a"}, repeats=None, limit=None) == {"reps": 10}


def test_estimate_test1_large_model_is_about_2_1_usd():
    kwargs = runner.test_kwargs("1", {"large": "gpt-6.1-sol"}, repeats=None, limit=None)
    est = runner.estimate_usd("1", {"large": "gpt-6.1-sol"}, kwargs)
    assert 2.0 <= est <= 2.4  # 3 rounds x ~352K tokens x $2 per million (the warm-up is a tiny ping)


def test_partial_run_is_saved_when_interrupted(runs_dir):
    from speed_helpers import answer_events, raises
    client = FakeClient([answer_events("r1", "OK"), raises(KeyboardInterrupt())])
    with pytest.raises(KeyboardInterrupt):
        runner.main(["--test", "0", "--repeats", "3", "--yes"], client=client)
    run = json.loads(next(runs_dir.glob("test0-*.json")).read_text(encoding="utf-8"))
    assert run["stopped"].startswith("error: KeyboardInterrupt") and run["spent_usd"] > 0


def test_command_budget_is_capped_by_what_is_left_of_the_ceiling(runs_dir, monkeypatch):
    (runs_dir / "test2-old.json").write_text(json.dumps({"spent_usd": 9.0}))
    seen = {}

    def fake_test0(client, model, rng, budget, **kw):
        seen["limit"] = budget.limit_usd
        return {"test": "0", "records": [], "spent_usd": 0.0, "stopped": None}

    monkeypatch.setattr(runner.experiments, "test0", fake_test0)
    assert runner.main(["--test", "0", "--yes", "--budget", "3"], client=FakeClient()) == 0
    assert seen["limit"] == pytest.approx(1.0)
