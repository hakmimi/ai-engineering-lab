"""Test helpers for topic 3: a fake OpenAI client that replays scripted stream events. No network."""

from __future__ import annotations

from types import SimpleNamespace

import httpx2
import openai


def ev(type: str, **fields) -> SimpleNamespace:
    return SimpleNamespace(type=type, **fields)


def completed(id: str, input_tokens: int = 0, cached: int = 0, output: int = 0, reasoning: int = 0) -> SimpleNamespace:
    usage = SimpleNamespace(
        input_tokens=input_tokens,
        input_tokens_details=SimpleNamespace(cached_tokens=cached),
        output_tokens=output,
        output_tokens_details=SimpleNamespace(reasoning_tokens=reasoning),
    )
    return ev("response.completed", response=SimpleNamespace(id=id, usage=usage))


def answer_events(id: str, text: str, input_tokens: int = 100, cached: int = 0, output: int = 10) -> list:
    return [ev("response.created"), ev("response.output_item.added"), ev("response.output_text.delta", delta=text),
            completed(id, input_tokens, cached, output)]


def status_error(status: int) -> openai.APIStatusError:
    request = httpx2.Request("POST", "https://api.example.com/v1/responses")
    response = httpx2.Response(status, request=request)
    cls = {429: openai.RateLimitError, 400: openai.BadRequestError, 404: openai.NotFoundError}.get(status, openai.InternalServerError)
    return cls(f"status {status}", response=response, body=None)


def connection_error() -> openai.APIConnectionError:
    return openai.APIConnectionError(request=httpx2.Request("POST", "https://api.example.com/v1/responses"))


class _Raise:
    """A script item: raise this exception when reached (before the stream, or mid-stream)."""

    def __init__(self, exc: Exception):
        self.exc = exc


def raises(exc: Exception) -> _Raise:
    return _Raise(exc)


class _Responses:
    def __init__(self, owner: "FakeClient"):
        self.owner = owner

    def create(self, **kw):
        self.owner.requests.append(kw)
        script = self.owner.scripts.pop(0) if self.owner.scripts else self.owner.default(len(self.owner.requests))
        if isinstance(script, _Raise):
            raise script.exc
        if not kw.get("stream"):
            events = [e for e in script if not isinstance(e, _Raise)]
            done = next((e for e in events if e.type == "response.completed"), None)
            return done.response if done else SimpleNamespace(id="", usage=None)
        return _stream(script)


def _stream(script):
    for item in script:
        if isinstance(item, _Raise):
            raise item.exc
        yield item


class FakeClient:
    """scripts: one entry per expected call, each a list of events (may contain raises(...)) or raises(...).
    When scripts run out, default(n) builds the n-th answer."""

    def __init__(self, scripts=None, default=None):
        self.scripts = list(scripts or [])
        self.requests: list[dict] = []
        self.default = default or (lambda n: answer_events(
            f"r{n}", "<answer><label>entailment</label><evidence>1</evidence></answer>"))
        self.responses = _Responses(self)


def fake_clock(times):
    it = iter(times)
    last = [0.0]

    def clock():
        try:
            last[0] = next(it)
        except StopIteration:
            pass
        return last[0]

    return clock
