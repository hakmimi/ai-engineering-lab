"""Small helper around the Anthropic SDK, shared by every topic.

llm_call() sends one prompt and returns the text answer. Every call can be
recorded in a Tracker (time, tokens, cost) so a topic can compare approaches.
"""

from __future__ import annotations

import os
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

# USD per million tokens (Claude API list prices). Cache writes use the 5-minute TTL (1.25x input).
PRICES: dict[str, dict[str, float]] = {
    "claude-haiku-5-5": {"input": 0.10, "output": 0.50, "cache_write": 0.125, "cache_read": 0.01},
    "claude-opus-5-5": {"input": 4.00, "output": 20.00, "cache_write": 5.00, "cache_read": 0.20},
}

DEFAULT_MODEL = "claude-haiku-5-5"


@dataclass
class CallRecord:
    label: str
    model: str
    seconds: float
    input_tokens: int
    output_tokens: int
    cache_write_tokens: int
    cache_read_tokens: int


def cost_usd(r: CallRecord) -> float:
    p = PRICES[r.model]
    return (
        r.input_tokens * p["input"]
        + r.output_tokens * p["output"]
        + r.cache_write_tokens * p["cache_write"]
        + r.cache_read_tokens * p["cache_read"]
    ) / 1_000_000


@dataclass
class Tracker:
    records: list[CallRecord] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def add(self, r: CallRecord) -> None:
        with self._lock:
            self.records.append(r)

    def calls(self) -> int:
        return len(self.records)

    def total_seconds(self) -> float:
        return sum(r.seconds for r in self.records)

    def total_cost_usd(self) -> float:
        return sum(cost_usd(r) for r in self.records)


def require_api_key() -> None:
    load_dotenv(ENV_FILE)
    if not os.environ.get("ANTHROPIC_API_KEY", "").strip():
        raise RuntimeError("Missing ANTHROPIC_API_KEY: add it to .env")


_client = None
_client_lock = threading.Lock()


def _default_client():
    global _client
    with _client_lock:
        if _client is None:
            import anthropic

            require_api_key()
            _client = anthropic.Anthropic(max_retries=4)
        return _client


def llm_call(
    prompt: str,
    *,
    cached_system: str = "",
    system: str = "",
    model: str | None = None,
    label: str = "",
    tracker: Tracker | None = None,
    max_tokens: int = 16000,
    client=None,
) -> str:
    """Send one user prompt and return the text of the answer.

    cached_system: fixed text (policies, instructions) sent first and marked for prompt caching.
    system: extra system text that is not cached.
    """
    model = model or os.environ.get("CLAIMS_MODEL", DEFAULT_MODEL)
    client = client or _default_client()

    kwargs = {"model": model, "max_tokens": max_tokens, "messages": [{"role": "user", "content": prompt}]}
    blocks = []
    if cached_system:
        blocks.append({"type": "text", "text": cached_system, "cache_control": {"type": "ephemeral"}})
    if system:
        blocks.append({"type": "text", "text": system})
    if blocks:
        kwargs["system"] = blocks

    start = time.perf_counter()
    response = client.messages.create(**kwargs)
    seconds = time.perf_counter() - start

    if tracker is not None:
        u = response.usage
        tracker.add(
            CallRecord(
                label=label,
                model=model,
                seconds=seconds,
                input_tokens=u.input_tokens or 0,
                output_tokens=u.output_tokens or 0,
                cache_write_tokens=getattr(u, "cache_creation_input_tokens", 0) or 0,
                cache_read_tokens=getattr(u, "cache_read_input_tokens", 0) or 0,
            )
        )
    return "".join(b.text for b in response.content if b.type == "text")


def extract_xml(text: str, tag: str) -> str:
    """Return the text between <tag> and </tag>, stripped; "" if the tag is missing."""
    match = re.search(rf"<{tag}>(.*?)</{tag}>", text, re.DOTALL)
    return match.group(1).strip() if match else ""
