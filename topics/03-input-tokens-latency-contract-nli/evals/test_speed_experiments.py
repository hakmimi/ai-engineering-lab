import random

import pytest

from ndaflow import data
from ndaflow.models import Answer, Contract, Statement
from ndaspeed import experiments as ex
from ndaspeed.cost import Budget
from speed_helpers import FakeClient, answer_events, connection_error, raises, status_error

OK = "<answer><label>entailment</label><evidence>1</evidence></answer>"
CONTRACTS = [Contract(str(i), f"{i}.pdf", ["title", "the receiving party may share " + "x" * 200, "end"]) for i in range(30)]
STATEMENTS = [Statement(f"nda-{i}", f"s{i}", f"statement {i}") for i in range(1, 18)]


@pytest.fixture(autouse=True)
def tiny_data(monkeypatch):
    monkeypatch.setattr(data, "load_contracts", lambda set_name: CONTRACTS[:20] if set_name == "main" else CONTRACTS[20:])
    monkeypatch.setattr(data, "load_statements", lambda: STATEMENTS)
    monkeypatch.setattr(data, "load_answer_key", lambda set_name: {
        c.doc_id: {s.sid: Answer("entailment", [1]) for s in STATEMENTS} for c in CONTRACTS})


def _measured(run):
    return [r for r in run["records"] if r["variant"] not in ("warmup", "prewarm_call", "error") and "skipped" not in r]


def test_measure_retries_429_outside_clock_and_keeps_failed_attempt():
    client = FakeClient([raises(status_error(429)), [raises(connection_error())], answer_events("r3", OK)])
    slept = []
    t, failed = ex.measure(client, Budget(1.0), {"model": "gpt-6-luna", "input": "hi"}, sleep=slept.append)
    assert t.error is None and t.response_id == "r3"
    assert [f.status for f in failed] == [429, None]
    assert slept == [5, 10]


def test_measure_does_not_retry_400():
    client = FakeClient([raises(status_error(400))])
    t, failed = ex.measure(client, Budget(1.0), {"model": "gpt-6-luna", "input": "hi"}, sleep=lambda s: None)
    assert t.status == 400 and failed == [] and len(client.requests) == 1


def test_first_record_of_each_test_is_warmup():
    for run in (ex.test0(FakeClient(), "gpt-6-luna", random.Random(1), Budget(1.0), repeats=2),
                ex.test4(FakeClient(), "gpt-6-luna", random.Random(1), Budget(1.0), chats=1)):
        assert run["records"][0]["variant"] == "warmup"
        assert run["stopped"] is None and run["seed"] == 2026


def test_test1_mixes_models_and_sizes_and_large_stops_after_its_rounds():
    client = FakeClient()
    run = ex.test1(client, {"small": "gpt-6-luna", "large": "gpt-6.1-sol"}, random.Random(1), Budget(5.0),
                   sizes=(50, 100, 200, 400))
    m = _measured(run)
    assert len(m) == 4 * 5 + 4 * 3
    assert sum(r["model"] == "gpt-6.1-sol" for r in m) == 12
    assert {r["round"] for r in m if r["model"] == "gpt-6.1-sol"} == {0, 1, 2}
    first_round = [(r["model"], r["size"]) for r in m[:8]]
    assert len(set(first_round)) == 8  # both models, every size, in round 0
    stream_reqs = [r for r in client.requests if r.get("input") != ex.PING and isinstance(r.get("input"), list)]
    assert len({r["instructions"].splitlines()[0] for r in stream_reqs}) == len(stream_reqs)  # every request cold


def test_test1_records_skipped_size_and_continues():
    run = ex.test1(FakeClient(), {"small": "gpt-6-luna"}, random.Random(1), Budget(5.0), rounds={"small": 1},
                   sizes=(50, 10**9))
    skipped = [r for r in run["records"] if "skipped" in r]
    assert len(skipped) == 1 and skipped[0]["size"] == 10**9
    assert [r["size"] for r in _measured(run)] == [50]


def test_test2_alternates_variant_order_by_chat():
    run = ex.test2(FakeClient(), "gpt-6-luna", random.Random(1), Budget(5.0), short_n=2, long_chats=2)
    for pack in ("short", "long"):
        firsts = {}
        for r in _measured(run):
            if r["pack"] == pack:
                firsts.setdefault(r["chat"], r["variant"])
        assert firsts == {0: "cache_on", 1: "cache_off"}
    m = _measured(run)
    assert len(m) == 2 * 2 * 17 * 2
    assert all(r["key_label"] == "entailment" and r["label"] == "entailment" for r in m)


def test_test3_prewarm_is_not_streamed_and_shares_prefix_with_question():
    client = FakeClient()
    slept = []
    run = ex.test3(client, "gpt-6-luna", random.Random(1), Budget(5.0), reps=1, sleep=slept.append)
    warm = [r for r in client.requests if not r.get("stream")]
    assert len(warm) == 1 and warm[0]["max_output_tokens"] == 16
    i = client.requests.index(warm[0])
    question = client.requests[i + 1]
    assert question["stream"] is True
    assert question["instructions"] == warm[0]["instructions"] and question["input"][0] == warm[0]["input"][0]
    assert question["prompt_cache_key"] == warm[0]["prompt_cache_key"]
    assert 2 in slept
    assert sorted(r["variant"] for r in _measured(run)) == ["cold", "prewarm"]


def test_budget_stop_returns_partial_run_marked_budget():
    run = ex.test2(FakeClient(), "gpt-6-luna", random.Random(1), Budget(0.0001), short_n=2, long_chats=1)
    assert run["stopped"] == "budget"
    assert run["spent_usd"] <= 0.0001


def test_pings_leave_room_for_text_but_prewarm_stays_minimal():
    client = FakeClient()
    ex.test0(client, "gpt-6-luna", random.Random(1), Budget(1.0), repeats=1)
    assert all(r["max_output_tokens"] == ex.PING_TOKENS for r in client.requests)
    assert ex.PING_TOKENS > 16


def test_interrupt_marks_partial_run_and_reraises():
    client = FakeClient([answer_events("r1", "OK"), answer_events("r2", "OK"), raises(KeyboardInterrupt())])
    with pytest.raises(KeyboardInterrupt) as e:
        ex.test0(client, "gpt-6-luna", random.Random(1), Budget(1.0), repeats=3)
    run = e.value.partial_run
    assert run["stopped"].startswith("error: KeyboardInterrupt") and len(run["records"]) == 2 and run["spent_usd"] > 0
