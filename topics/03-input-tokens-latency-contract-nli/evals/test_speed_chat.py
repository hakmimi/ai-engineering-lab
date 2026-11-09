import random

import pytest

from ndaflow.models import Contract
from ndaspeed.chat import ANSWER_TOKENS, run_chat
from ndaspeed.cost import Budget, BudgetExceeded
from ndaspeed.packs import Question, make_pack
from speed_helpers import FakeClient, answer_events, raises, status_error

PACK = make_pack("p", [Contract("1", "a.pdf", ["intro", "may share", "must return"]),
                       Contract("2", "b.pdf", ["title", "no reverse engineering"])])
QS = [Question("C01", "1", "nda-1", "s one"), Question("C02", "2", "nda-2", "s two"), Question("C01", "1", "nda-3", "s three")]


def _run(variant, client=None, budget=None):
    client = client or FakeClient()
    turns = run_chat(client, "gpt-6-luna", PACK, QS, variant, random.Random(5), budget or Budget(10.0), "chat-1")
    return client, turns


def test_cache_off_changes_first_line_every_turn():
    client, _ = _run("cache_off")
    first_lines = [r["instructions"].splitlines()[0] for r in client.requests]
    assert len(set(first_lines)) == 3 and all(l.startswith("run-id: ") for l in first_lines)
    assert all(r["store"] is False and "prompt_cache_key" not in r for r in client.requests)


def test_cache_on_keeps_instructions_and_pack_identical_across_turns():
    client, _ = _run("cache_on")
    assert len({r["instructions"] for r in client.requests}) == 1
    assert all(r["input"][0] == {"role": "user", "content": PACK.text} for r in client.requests)
    assert all(r["prompt_cache_key"] == "chat-1" and r["store"] is False for r in client.requests)
    assert all(r["max_output_tokens"] == ANSWER_TOKENS for r in client.requests)


def test_history_grows_with_previous_answers_in_order():
    client, turns = _run("cache_on")
    last = client.requests[2]["input"]
    assert [m["role"] for m in last] == ["user", "user", "assistant", "user", "assistant", "user"]
    assert last[1]["content"] == "Contract C01: s one" and last[2]["content"] == turns[0].timing.text
    assert last[-1]["content"] == "Contract C01: s three"


def test_thread_sends_only_new_question_after_turn_one():
    client, turns = _run("thread")
    assert client.requests[0]["store"] is True and "previous_response_id" not in client.requests[0]
    second = client.requests[1]
    assert second["input"] == [{"role": "user", "content": "Contract C02: s two"}]
    assert second["previous_response_id"] == "r1" and second["store"] is True
    assert second["instructions"] == client.requests[0]["instructions"]
    assert not any(t.fallback for t in turns)


def test_thread_falls_back_to_full_resend_on_error():
    ok = "<answer><label>entailment</label><evidence>1</evidence></answer>"
    client = FakeClient([answer_events("r1", ok), raises(status_error(404)), answer_events("r3", ok), answer_events("r4", ok)])
    client, turns = _run("thread", client)
    assert turns[1].fallback is True and turns[1].timing.error is None
    assert len(client.requests[2]["input"]) == 4 and "previous_response_id" not in client.requests[2]
    assert client.requests[3]["previous_response_id"] == "r3"


def test_unreadable_answer_is_error_and_chat_continues():
    client = FakeClient([answer_events("r1", "no idea")])
    _, turns = _run("cache_on", client)
    assert turns[0].answer.label == "error"
    assert turns[1].answer.label == "entailment" and turns[1].answer.evidence == [1]
    assert len(turns) == 3


def test_budget_exceeded_stops_before_the_call():
    client = FakeClient()
    with pytest.raises(BudgetExceeded) as e:
        _run("cache_off", client, Budget(0.0))
    assert client.requests == []
    assert e.value.turns == []
