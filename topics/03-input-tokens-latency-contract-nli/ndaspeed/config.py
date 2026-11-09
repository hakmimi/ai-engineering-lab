"""Settings shared by every test in topic 3."""

from __future__ import annotations

from pathlib import Path

from shared.llm import default_model, load_env, require_api_key

SEED = 2026
MIN_OUTPUT_TOKENS = 16  # the smallest max_output_tokens the Responses API accepts
REASONING = {"effort": "low"}  # lowest effort we use; confirmed in the smoke run
TOPIC_DIR = Path(__file__).resolve().parent.parent
RUNS_DIR = TOPIC_DIR / "runs"
RESULTS = TOPIC_DIR / "results.md"
TOPIC_CEILING_USD = 10.0


def model(size: str) -> str:
    load_env()
    return default_model(size)


def make_client(size: str = "small"):
    """A real OpenAI client with no hidden retries: retries happen outside the clock (experiments.measure)."""
    import openai

    require_api_key(model(size))
    return openai.OpenAI(max_retries=0)
