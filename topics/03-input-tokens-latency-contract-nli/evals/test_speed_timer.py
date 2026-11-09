import json

from ndaspeed.timer import nonce, timed_stream
from speed_helpers import FakeClient, completed, connection_error, ev, fake_clock, raises, status_error


def test_timer_records_first_text_total_and_usage():
    client = FakeClient([[ev("response.created"), ev("response.output_item.added"),
                          ev("response.output_text.delta", delta="ent"), ev("response.output_text.delta", delta="ail"),
                          completed("r1", input_tokens=1200, cached=1024, output=5)]])
    t = timed_stream(client, clock=fake_clock([0.0, 0.3, 0.5, 0.9, 1.0, 1.4]), model="m", input="hi")
    assert (t.first_event_s, t.first_output_s, t.first_text_s, t.total_s) == (0.3, 0.5, 0.9, 1.4)
    assert t.text == "entail" and t.response_id == "r1"
    assert (t.input_tokens, t.cached_tokens, t.output_tokens) == (1200, 1024, 5)
    assert t.request_bytes == len(json.dumps({"model": "m", "input": "hi"}).encode())
    assert t.error is None
    assert client.requests[0]["stream"] is True


def test_timer_reasoning_counts_as_output_not_text():
    client = FakeClient([[ev("response.created"), ev("response.reasoning_summary_text.delta", delta="hmm"),
                          ev("response.output_text.delta", delta="ok"), completed("r1", output=9, reasoning=7)]])
    t = timed_stream(client, clock=fake_clock([0.0, 0.1, 0.4, 0.8, 1.0]), model="m", input="hi")
    assert t.first_output_s == 0.4
    assert t.first_text_s == 0.8
    assert t.reasoning_tokens == 7


def test_timer_stream_without_text_leaves_first_text_none():
    client = FakeClient([[ev("response.created"), completed("r1")]])
    t = timed_stream(client, clock=fake_clock([0.0, 0.2, 0.6]), model="m", input="hi")
    assert t.first_text_s is None
    assert t.total_s == 0.6
    assert t.error is None


def test_timer_api_error_returns_timing_with_error_and_status():
    client = FakeClient([raises(status_error(429))])
    t = timed_stream(client, clock=fake_clock([0.0, 0.2]), model="m", input="hi")
    assert "RateLimitError" in t.error
    assert t.status == 429
    assert t.total_s is None


def test_timer_error_mid_stream_keeps_partial_times():
    client = FakeClient([[ev("response.created"), raises(connection_error())]])
    t = timed_stream(client, clock=fake_clock([0.0, 0.3, 0.5]), model="m", input="hi")
    assert t.first_event_s == 0.3
    assert "APIConnectionError" in t.error
    assert t.status is None
    assert t.total_s is None


def test_nonce_is_repeatable_with_a_seed_within_one_process():
    import random
    a, b = nonce(random.Random(1)), nonce(random.Random(1))
    assert a == b and a.startswith("run-id: ")


def test_nonce_differs_between_processes_with_the_same_seed(monkeypatch):
    # a re-run with the same seed must not reuse last run's "fresh" first lines: OpenAI kept them cached
    import random
    import ndaspeed.timer as timer
    a = nonce(random.Random(1))
    monkeypatch.setattr(timer, "_SALT", "other")
    assert nonce(random.Random(1)) != a


def test_timer_incomplete_reads_usage_and_reason():
    from types import SimpleNamespace
    done = completed("r1", input_tokens=180_000, output=16, reasoning=16)
    done.type = "response.incomplete"
    done.response.incomplete_details = SimpleNamespace(reason="max_output_tokens")
    client = FakeClient([[ev("response.created"), done]])
    t = timed_stream(client, clock=fake_clock([0.0, 0.2, 0.9]), model="m", input="hi")
    assert t.total_s == 0.9 and t.input_tokens == 180_000 and t.output_tokens == 16
    assert t.incomplete == "max_output_tokens"
    assert t.error is None and t.first_text_s is None


def test_timer_failed_event_is_error():
    from types import SimpleNamespace
    failed = completed("r1", input_tokens=500)
    failed.type = "response.failed"
    failed.response.error = SimpleNamespace(code="server_error", message="boom")
    t = timed_stream(FakeClient([[ev("response.created"), failed]]), clock=fake_clock([0.0, 0.1, 0.3]), model="m", input="x")
    assert "server_error" in t.error and t.status is None
    assert t.input_tokens == 500  # still billed


def test_timer_error_event_is_error():
    t = timed_stream(FakeClient([[ev("response.created"), ev("error", code="rate_limit", message="slow down")]]),
                     clock=fake_clock([0.0, 0.1, 0.2]), model="m", input="x")
    assert "rate_limit" in t.error
