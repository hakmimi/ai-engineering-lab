"""One multi-turn chat about a contract pack, sent three ways:

cache_on  - the whole conversation re-sent each turn, same prompt start, prompt_cache_key per chat
cache_off - the whole conversation re-sent each turn, a new random first line every turn (no cache match)
thread    - like cache_on, but from turn 2 only the new question is sent, with previous_response_id
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from typing import Callable

from ndaflow.models import Answer
from ndaspeed.config import REASONING
from ndaspeed.cost import Budget, BudgetExceeded, cost_of
from ndaspeed.packs import Pack, Question, est_tokens, instructions, question_text, read_answer
from ndaspeed.timer import Timing, nonce, timed_stream
from shared.llm import PRICES

VARIANTS = ("cache_on", "cache_off", "thread")
ANSWER_TOKENS = 2000
NO_ANSWER = "(no answer)"  # kept in the history when a turn failed: an empty assistant message can be refused


@dataclass
class Turn:
    index: int
    question: Question
    timing: Timing
    answer: Answer
    fallback: bool = False


def request_estimate_usd(request: dict, model: str) -> float:
    """Every character of the request priced as uncached input (an upper bound for the budget stop)."""
    return est_tokens(json.dumps(request, ensure_ascii=False)) * PRICES[model]["input"] / 1_000_000


def run_chat(client, model: str, pack: Pack, questions: list[Question], variant: str, rng: random.Random,
             budget: Budget, chat_id: str, send: Callable[..., Timing] | None = None) -> list[Turn]:
    """send(**request) -> Timing; defaults to one timed_stream call (experiments pass one that retries outside the clock).
    On BudgetExceeded the turns done so far ride on the exception as .turns."""
    if variant not in VARIANTS:
        raise ValueError(f"unknown variant {variant}")
    send = send or (lambda **req: timed_stream(client, **req))
    pack_msg = {"role": "user", "content": pack.text}
    chat_nonce = nonce(rng)
    history: list[dict] = []
    turns: list[Turn] = []
    prev_id: str | None = None

    def call(request: dict) -> Timing:
        budget.before(request_estimate_usd(request, model))
        timing = send(**request)
        budget.add(cost_of(timing, model))
        return timing

    try:
        for i, q in enumerate(questions):
            q_msg = {"role": "user", "content": question_text(q)}
            base = {"model": model, "max_output_tokens": ANSWER_TOKENS, "reasoning": REASONING,
                    "instructions": instructions(nonce(rng) if variant == "cache_off" else chat_nonce)}
            full = {**base, "input": [pack_msg, *history, q_msg]}
            if variant == "cache_off":
                full["store"] = False
            else:
                full["prompt_cache_key"] = chat_id
                full["store"] = variant == "thread"

            fallback = False
            if variant == "thread" and prev_id:
                timing = call({**base, "input": [q_msg], "previous_response_id": prev_id, "store": True,
                               "prompt_cache_key": chat_id})
                if timing.error:
                    timing, fallback = call(full), True
            else:
                timing = call(full)

            answer = Answer("error") if timing.error else read_answer(timing.text, pack.contract(q.code))
            turns.append(Turn(i, q, timing, answer, fallback))
            history += [q_msg, {"role": "assistant", "content": timing.text or NO_ANSWER}]
            prev_id = timing.response_id if not timing.error else None
    except BudgetExceeded as e:
        e.turns = turns
        raise
    return turns
