"""One streamed Responses API call, timed event by event (in the spirit of the article's timed_stream())."""

from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass

import openai


@dataclass
class Timing:
    first_event_s: float | None
    first_output_s: float | None  # first output of any kind, reasoning included
    first_text_s: float | None  # first answer text: our "first word" (TTFT)
    total_s: float | None  # completed event: our total time
    request_bytes: int
    input_tokens: int = 0  # all input tokens, cached ones included
    cached_tokens: int = 0
    output_tokens: int = 0  # reasoning tokens included
    reasoning_tokens: int = 0
    response_id: str = ""
    text: str = ""
    error: str | None = None
    status: int | None = None


def nonce(rng: random.Random) -> str:
    return f"run-id: {rng.getrandbits(64):016x}"


def _is_output(event_type: str) -> bool:
    return event_type == "response.output_item.added" or event_type.endswith(".delta")


def timed_stream(client, *, clock=time.perf_counter, **request) -> Timing:
    """Send one streamed request and time it. Never raises on an API error: the Timing carries it."""
    t = Timing(None, None, None, None, len(json.dumps(request, ensure_ascii=False).encode("utf-8")))
    parts: list[str] = []
    start = clock()
    try:
        for event in client.responses.create(stream=True, **request):
            now = clock() - start
            if t.first_event_s is None:
                t.first_event_s = now
            if t.first_output_s is None and _is_output(event.type):
                t.first_output_s = now
            if event.type == "response.output_text.delta":
                if t.first_text_s is None:
                    t.first_text_s = now
                parts.append(event.delta)
            elif event.type == "response.completed":
                t.total_s = now
                _read_usage(t, event.response)
    except openai.APIError as e:
        t.error = f"{type(e).__name__}: {e}"
        t.status = getattr(e, "status_code", None)
    t.text = "".join(parts)
    return t


def _read_usage(t: Timing, response) -> None:
    t.response_id = response.id or ""
    u = response.usage
    if u is None:
        return
    t.input_tokens = u.input_tokens or 0
    t.cached_tokens = (getattr(u.input_tokens_details, "cached_tokens", 0) or 0) if u.input_tokens_details else 0
    t.output_tokens = u.output_tokens or 0
    t.reasoning_tokens = (getattr(u.output_tokens_details, "reasoning_tokens", 0) or 0) if u.output_tokens_details else 0
