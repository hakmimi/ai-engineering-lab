"""The five tests. Each returns a run dict: what was planned, every timed record, and what it cost.

Variants are interleaved inside each test, all calls are sequential, and the first call of every test is a
warm-up (it opens the connection) that is recorded but left out of all stats.
"""

from __future__ import annotations

import random
import time
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime

import openai

from ndaflow import data
from ndaspeed.chat import ANSWER_TOKENS, Turn, request_estimate_usd, run_chat
from ndaspeed.config import MIN_OUTPUT_TOKENS, REASONING, SEED
from ndaspeed.cost import Budget, BudgetExceeded, cost_of
from ndaspeed.packs import (
    PING, all_contracts, instructions, long_questions, make_pack, question_text, read_answer, short_questions, stack_to,
)
from ndaspeed.timer import Timing, nonce, timed_stream

SIZES = (20_000, 50_000, 100_000, 180_000)
MAX_RETRIES = 3
PING_TOKENS = 200  # room for low-effort reasoning plus "OK"; with 16, reasoning can use the cap and no text arrives


# ---------------------------------------------------------------- calls
def _retryable(t: Timing) -> bool:
    return t.status is None or t.status == 429 or t.status >= 500


def _with_retries(client, sleep, request: dict) -> tuple[Timing, list[Timing]]:
    """Retries happen here, outside the clock: each attempt is its own timed call."""
    failed: list[Timing] = []
    for attempt in range(MAX_RETRIES + 1):
        t = timed_stream(client, **request)
        if t.error and _retryable(t) and attempt < MAX_RETRIES:
            failed.append(t)
            sleep(5 * (attempt + 1))
            continue
        return t, failed
    raise AssertionError("unreachable")


def measure(client, budget: Budget, request: dict, sleep=time.sleep) -> tuple[Timing, list[Timing]]:
    """One timed call (the model comes from request["model"]), with budget check and retries outside the clock."""
    model = request["model"]
    budget.before(request_estimate_usd(request, model))
    t, failed = _with_retries(client, sleep, request)
    budget.add(sum(cost_of(x, model) for x in [*failed, t]))
    return t, failed


# ---------------------------------------------------------------- records
def _new_run(test: str, models: dict, plan: dict | None = None) -> dict:
    return {"test": test, "started": datetime.now().isoformat(timespec="seconds"), "seed": SEED, "models": models,
            "plan": plan or {}, "records": [], "spent_usd": 0.0, "stopped": None}


def _rec(run: dict, variant: str, model: str, timing: Timing, **keys) -> None:
    run["records"].append({"variant": variant, "model": model, **keys, "timing": asdict(timing)})


def _add_failed(run: dict, failed: list[Timing], model: str, **keys) -> None:
    for t in failed:
        _rec(run, "error", model, t, **keys)


def _ping_request(model: str, instr: str | None = None) -> dict:
    return {"model": model, "instructions": instr or instructions(None), "input": PING,
            "max_output_tokens": PING_TOKENS, "reasoning": REASONING, "store": False}


def _warmup(run, client, budget, model, sleep) -> None:
    t, failed = measure(client, budget, _ping_request(model), sleep)
    _rec(run, "warmup", model, t)
    _add_failed(run, failed, model)


def _turn_records(run: dict, turns: list[Turn], key: dict, model: str, variant: str, **keys) -> None:
    for t in turns:
        k = key[t.question.doc_id][t.question.sid]
        _rec(run, variant, model, t.timing, **keys, turn=t.index, doc_id=t.question.doc_id, sid=t.question.sid,
             label=t.answer.label, evidence=t.answer.evidence, key_label=k.label, key_evidence=k.evidence,
             fallback=t.fallback)


def _chat(run, client, model, chat_pack, questions, variant, rng, budget, chat_id, sleep, key, **keys) -> None:
    failed_all: list[Timing] = []

    def send(**request):
        t, failed = _with_retries(client, sleep, request)
        failed_all.extend(failed)
        return t

    try:
        turns = run_chat(client, model, chat_pack, questions, variant, rng, budget, chat_id, send=send)
    except BudgetExceeded as e:
        _turn_records(run, e.turns, key, model, variant, **keys)
        _add_failed(run, failed_all, model, **keys)
        raise
    _turn_records(run, turns, key, model, variant, **keys)
    _add_failed(run, failed_all, model, **keys)


@contextmanager
def _guard(run: dict, budget: Budget):
    """Budget stop ends the test normally; anything else (Ctrl+C included) marks the run, attaches it, and re-raises
    so the runner can still save what was measured and spent."""
    try:
        yield
    except BudgetExceeded:
        run["stopped"] = "budget"
    except BaseException as e:
        run["stopped"] = f"error: {type(e).__name__}: {e}"
        run["spent_usd"] = budget.spent_usd
        e.partial_run = run
        raise


def _finish(run: dict, budget: Budget) -> dict:
    run["spent_usd"] = budget.spent_usd
    return run


def _alternate(i: int, a: str, b: str) -> tuple[str, str]:
    return (a, b) if i % 2 == 0 else (b, a)


# ---------------------------------------------------------------- tests
def test0(client, model: str, rng: random.Random, budget: Budget, repeats: int = 10, sleep=time.sleep) -> dict:
    """Network floor: a tiny prompt, the shortest reply."""
    run = _new_run("0", {"small": model})
    with _guard(run, budget):
        _warmup(run, client, budget, model, sleep)
        for i in range(repeats):
            t, failed = measure(client, budget, _ping_request(model), sleep)
            _add_failed(run, failed, model, rep=i)
            _rec(run, "floor", model, t, rep=i)
    return _finish(run, budget)


def test1(client, models: dict[str, str], rng: random.Random, budget: Budget,
          rounds: dict[str, int] | None = None, sizes=SIZES, sleep=time.sleep) -> dict:
    """Prompt size -> first word. Every request is cold (a new random first line). Models are mixed inside rounds."""
    rounds = rounds or {"small": 5, "large": 3}
    run = _new_run("1", models, {"sizes": list(sizes), "rounds": {k: rounds.get(k, 0) for k in models}})
    everything = all_contracts()
    packs = {}
    for size in sizes:
        try:
            packs[size] = make_pack(f"stack-{size}", stack_to(everything, size))
        except ValueError as e:
            run["records"].append({"variant": "cold", "size": size, "skipped": str(e)})
    run["plan"]["pack_docs"] = {str(s): [c.doc_id for c in p.contracts] for s, p in packs.items()}
    with _guard(run, budget):
        for model in models.values():
            _warmup(run, client, budget, model, sleep)
        for r in range(max(rounds.get(k, 0) for k in models)):
            pairs = [(k, size) for k in models if r < rounds.get(k, 0) for size in packs]
            rng.shuffle(pairs)
            for k, size in pairs:
                model = models[k]
                request = {**_ping_request(model, instructions(nonce(rng))),
                           "input": [{"role": "user", "content": packs[size].text}, {"role": "user", "content": PING}]}
                t, failed = measure(client, budget, request, sleep)
                _add_failed(run, failed, model, size=size, round=r)
                _rec(run, "cold", model, t, size=size, round=r)
    return _finish(run, budget)


def test2(client, model: str, rng: random.Random, budget: Budget, short_n: int = 10, long_chats: int = 3,
          sleep=time.sleep) -> dict:
    """17-turn chats, cache on vs off, on a 1-NDA pack and on the whole main-set pack."""
    statements, main, key = data.load_statements(), data.load_contracts("main"), data.load_answer_key("main")
    short_docs = rng.sample(main, short_n)
    long_pack = make_pack("long", main)
    long_qs = [long_questions(long_pack, statements, 17, rng) for _ in range(long_chats)]
    run = _new_run("2", {"small": model}, {
        "short_docs": [c.doc_id for c in short_docs],
        "long_questions": [[(q.code, q.doc_id, q.sid) for q in qs] for qs in long_qs]})
    with _guard(run, budget):
        _warmup(run, client, budget, model, sleep)
        for i, c in enumerate(short_docs):
            pack = make_pack(f"short-{c.doc_id}", [c])
            for v in _alternate(i, "cache_on", "cache_off"):
                _chat(run, client, model, pack, short_questions(pack, statements), v, rng, budget,
                      f"t2-short-{i}-{v}", sleep, key, pack="short", chat=i)
        for j, qs in enumerate(long_qs):
            for v in _alternate(j, "cache_on", "cache_off"):
                _chat(run, client, model, long_pack, qs, v, rng, budget, f"t2-long-{j}-{v}", sleep, key,
                      pack="long", chat=j)
    return _finish(run, budget)


def test3(client, model: str, rng: random.Random, budget: Budget, reps: int = 10, sleep=time.sleep) -> dict:
    """First question cold vs after a warm-up request with the same prompt start. A fresh pack start every time."""
    statements, main, key = data.load_statements(), data.load_contracts("main"), data.load_answer_key("main")
    pack = make_pack("long", main)
    pack_msg = {"role": "user", "content": pack.text}
    questions = [long_questions(pack, statements, 1, rng)[0] for _ in range(reps)]
    run = _new_run("3", {"small": model}, {"questions": [(q.code, q.doc_id, q.sid) for q in questions]})
    with _guard(run, budget):
        _warmup(run, client, budget, model, sleep)
        for rep, q in enumerate(questions):
            for v in _alternate(rep, "cold", "prewarm"):
                instr, cache_key = instructions(nonce(rng)), f"t3-{rep}-{v}"
                if v == "prewarm":
                    _prewarm(run, client, budget, model, {
                        **_ping_request(model, instr), "input": [pack_msg, {"role": "user", "content": PING}],
                        "max_output_tokens": MIN_OUTPUT_TOKENS, "prompt_cache_key": cache_key}, rep)
                    sleep(2)
                request = {"model": model, "instructions": instr, "max_output_tokens": ANSWER_TOKENS,
                           "reasoning": REASONING, "store": False, "prompt_cache_key": cache_key,
                           "input": [pack_msg, {"role": "user", "content": question_text(q)}]}
                t, failed = measure(client, budget, request, sleep)
                _add_failed(run, failed, model, rep=rep)
                a = read_answer(t.text, pack.contract(q.code)) if not t.error else None
                k = key[q.doc_id][q.sid]
                _rec(run, v, model, t, rep=rep, doc_id=q.doc_id, sid=q.sid, label=a.label if a else "error",
                     evidence=a.evidence if a else [], key_label=k.label, key_evidence=k.evidence)
    return _finish(run, budget)


def _prewarm(run, client, budget, model, request: dict, rep: int) -> None:
    """Not streamed: it only fills the cache. Its cost, cached tokens and any error are recorded."""
    budget.before(request_estimate_usd(request, model))
    started = time.perf_counter()
    t = Timing(None, None, None, None, 0)
    try:
        resp = client.responses.create(**request)
        t.total_s = time.perf_counter() - started
        u = resp.usage
        if u is not None:
            t.input_tokens, t.output_tokens = u.input_tokens or 0, u.output_tokens or 0
            t.cached_tokens = (u.input_tokens_details.cached_tokens or 0) if u.input_tokens_details else 0
        t.response_id = resp.id or ""
    except openai.APIError as e:
        t.error, t.status = f"{type(e).__name__}: {e}", getattr(e, "status_code", None)
    budget.add(cost_of(t, model))
    _rec(run, "prewarm_call", model, t, rep=rep)


def test4(client, model: str, rng: random.Random, budget: Budget, chats: int = 3, sleep=time.sleep) -> dict:
    """Long-pack chats: whole conversation re-sent (cache on) vs previous_response_id (thread)."""
    statements, main, key = data.load_statements(), data.load_contracts("main"), data.load_answer_key("main")
    pack = make_pack("long", main)
    qs_all = [long_questions(pack, statements, 17, rng) for _ in range(chats)]
    run = _new_run("4", {"small": model}, {"questions": [[(q.code, q.doc_id, q.sid) for q in qs] for qs in qs_all]})
    with _guard(run, budget):
        _warmup(run, client, budget, model, sleep)
        for j, qs in enumerate(qs_all):
            for v in _alternate(j, "cache_on", "thread"):
                _chat(run, client, model, pack, qs, v, rng, budget, f"t4-{j}-{v}", sleep, key, pack="long", chat=j)
    return _finish(run, budget)
