"""Small helper around the OpenAI and Anthropic SDKs, shared by every topic.

The provider follows the model name: "claude-..." goes to Anthropic, anything else to OpenAI.
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

# USD per million tokens, standard tier list prices (checked 2026-11-08).
# Anthropic: cache writes use the 5-minute TTL (1.25x input). OpenAI: caching is automatic, no write premium.
PRICES: dict[str, dict[str, float]] = {
    "gpt-6-luna": {"input": 0.10, "output": 0.50, "cache_write": 0.10, "cache_read": 0.01},
    "gpt-6.1-sol": {"input": 2.00, "output": 10.00, "cache_write": 2.00, "cache_read": 0.10},
    "claude-haiku-5-5": {"input": 0.10, "output": 0.50, "cache_write": 0.125, "cache_read": 0.01},
    "claude-opus-5-5": {"input": 4.00, "output": 20.00, "cache_write": 5.00, "cache_read": 0.20},
}

DEFAULT_MODELS = {"small": "gpt-6-luna", "large": "gpt-6.1-sol"}
DEFAULT_MODEL = DEFAULT_MODELS["small"]


def default_model(size: str = "small") -> str:
    env = {"small": "CLAIMS_MODEL", "large": "CLAIMS_MODEL_LARGE"}[size]
    return os.environ.get(env, DEFAULT_MODELS[size])


def is_anthropic(model: str) -> bool:
    return model.startswith("claude")


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


def load_env() -> None:
    """Read the repo's .env (keys and CLAIMS_MODEL settings). Call before choosing a model."""
    load_dotenv(ENV_FILE)


def require_api_key(model: str | None = None) -> None:
    load_env()
    name = "ANTHROPIC_API_KEY" if is_anthropic(model or default_model()) else "OPENAI_API_KEY"
    if not os.environ.get(name, "").strip():
        raise RuntimeError(f"Missing {name}: add it to .env")


_clients: dict[str, object] = {}
_client_lock = threading.Lock()


def _default_client(model: str):
    provider = "anthropic" if is_anthropic(model) else "openai"
    with _client_lock:
        if provider not in _clients:
            require_api_key(model)
            if provider == "anthropic":
                import anthropic

                _clients[provider] = anthropic.Anthropic(max_retries=4)
            else:
                import openai

                _clients[provider] = openai.OpenAI(max_retries=4)
        return _clients[provider]


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
    model = model or default_model()
    client = client or _default_client(model)
    if not is_anthropic(model):
        return _openai_call(prompt, cached_system, system, model, label, tracker, max_tokens, client)

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


def _openai_call(prompt, cached_system, system, model, label, tracker, max_tokens, client) -> str:
    """OpenAI Responses API. Caching is automatic for a repeated prefix, so fixed text goes first."""
    instructions = "\n\n".join(t for t in (cached_system, system) if t)
    kwargs = {"model": model, "input": prompt, "max_output_tokens": max_tokens}
    if instructions:
        kwargs["instructions"] = instructions

    start = time.perf_counter()
    response = client.responses.create(**kwargs)
    seconds = time.perf_counter() - start

    if tracker is not None:
        u = response.usage
        details = getattr(u, "input_tokens_details", None)
        cached = (getattr(details, "cached_tokens", 0) or 0) if details else 0
        tracker.add(
            CallRecord(
                label=label,
                model=model,
                seconds=seconds,
                input_tokens=(u.input_tokens or 0) - cached,
                output_tokens=u.output_tokens or 0,
                cache_write_tokens=0,
                cache_read_tokens=cached,
            )
        )
    return response.output_text or ""


def extract_xml(text: str, tag: str) -> str:
    """Return the text between <tag> and </tag>, stripped; "" if the tag is missing."""
    match = re.search(rf"<{tag}>(.*?)</{tag}>", text, re.DOTALL)
    return match.group(1).strip() if match else ""
