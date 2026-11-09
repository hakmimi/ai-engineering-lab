r"""Run one level over one set and save a run file.

From the topic folder (PowerShell):
    $env:PYTHONPATH = "..\..;."
    python -m tablefind.run --level 2 --set main --dry-run
    python -m tablefind.run --level 2 --set main --limit 5 --repeats 1     # smoke run
    python -m tablefind.run --level 2 --set main                           # 3 repeats
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from shared.llm import PRICES, Tracker, cost_usd, load_env, require_api_key
from shared.runs import DEFAULT_CEILING_USD, over_ceiling, save_run, spent_so_far
from tablefind.cards import card
from tablefind.data import SETS, Question, load_key, load_questions, load_tables
from tablefind.embed import EMBED_MODEL, EMBED_USD_PER_M, Embedder
from tablefind.levels import RERANK_MAX_TOKENS, SHORTLIST, Ctx, prepare, run_level
from tablefind.rerank import SYSTEM
from tablefind.score import score

TOPIC = Path(__file__).resolve().parent.parent
RUNS_DIR = TOPIC / "runs"
CACHE_DIR = TOPIC / "cache"
TOPIC_CEILING_USD = DEFAULT_CEILING_USD
LEVELS = ("0", "1", "2", "3")


def rerank_model() -> str:
    return os.environ.get("RERANK_MODEL", "gpt-6-luna")


def make_embedder() -> Embedder:
    return Embedder(CACHE_DIR)


def estimate_cost_usd(level: str, questions: list[Question], tables, model: str, repeats: int) -> float:
    """Upper side: characters ÷ 4 as tokens, output at the max_tokens cap (reasoning is billed), no cache discount,
    both card sets embedded as misses."""
    if level == "0":
        return 0.0
    with_desc = level == "3"
    cards = [card(t, with_desc) for t in tables]
    embed_chars = sum(len(card(t, d)) for t in tables for d in (False, True)) + sum(len(q.text) for q in questions)
    total = embed_chars / 4 * EMBED_USD_PER_M / 1_000_000
    if level in ("2", "3"):
        avg_card = sum(len(c) for c in cards) / len(cards)
        p = PRICES[model]
        for q in questions:
            tokens_in = (len(SYSTEM) + len(q.text) + SHORTLIST * avg_card) / 4
            total += repeats * (tokens_in * p["input"] + RERANK_MAX_TOKENS * p["output"]) / 1_000_000
    return total


def _failed(error: str) -> dict:
    return {"picks": [], "top20": None, "made_up": [], "filled": 0, "status": "failed", "error": error}


def _run_repeat(level: str, questions: list[Question], ctx: Ctx, budget_left: float, workers: int) -> tuple[dict, bool]:
    lock, stopped, spent = threading.Lock(), threading.Event(), [0.0]
    out: dict[str, dict] = {}

    def one(q: Question) -> None:
        with lock:
            if spent[0] >= budget_left:
                stopped.set()
                return
        qctx = Ctx(ctx.tables, ctx.embedder, ctx.model, Tracker(), ctx.index)
        start = time.perf_counter()
        try:
            ans = run_level(level, q, qctx)
        except Exception as exc:  # the SDK already retried: an outage, not a re-ranker mistake
            ans = _failed(f"{type(exc).__name__}: {exc}"[:300])
        cost = sum(cost_usd(r) for r in qctx.tracker.records)
        with lock:
            spent[0] += cost
        out[q.qid] = {"answer": ans, "seconds": time.perf_counter() - start, "cost_usd": cost,
                      "calls": len(qctx.tracker.records), "llm_seconds": sum(r.seconds for r in qctx.tracker.records)}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(one, questions))
    return out, stopped.is_set()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run one table-finding level over one set of questions.")
    ap.add_argument("--level", required=True, choices=LEVELS)
    ap.add_argument("--set", default="main", choices=SETS)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--limit", type=int, default=None, help="only the first N questions (smoke runs; the report ignores them)")
    ap.add_argument("--budget", type=float, default=1.0, help="stop starting new questions once this many USD are spent")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--runs-dir", type=Path, default=RUNS_DIR)
    a = ap.parse_args(argv)

    load_env()  # before rerank_model(): RERANK_MODEL may be set only in .env
    model = rerank_model() if a.level in ("2", "3") else "none"
    repeats = a.repeats if a.level in ("2", "3") else 1
    questions = load_questions(a.set)[: a.limit] if a.limit else load_questions(a.set)
    tables = load_tables()

    estimate = estimate_cost_usd(a.level, questions, tables, model if model != "none" else "gpt-6-luna", repeats)
    spent = spent_so_far(a.runs_dir)
    print(f"Level {a.level} ({model}), {a.set} set: {len(questions)} questions × {repeats} repeats, pool {len(tables)} tables. "
          f"Estimated cost ${estimate:.3f} (spent so far ${spent:.3f})")
    if a.dry_run:
        return 0
    if estimate > a.budget:
        print(f"The estimate is over --budget ${a.budget:.2f}: the run would stop part way and be thrown out. "
              f"Raise --budget or use --limit. Not running.")
        return 3
    if over_ceiling(spent, estimate, TOPIC_CEILING_USD):
        print(f"That would pass the ${TOPIC_CEILING_USD:.2f} topic ceiling. Not running.")
        return 2
    if a.level != "0":
        require_api_key("text-embedding")  # embeddings are OpenAI
        if model != "none":
            require_api_key(model)
    if not a.yes and input("Run? [y/N] ").strip().lower() != "y":
        return 1

    embedder = make_embedder() if a.level != "0" else None
    ctx = Ctx(tables, embedder, model, Tracker())
    prepare(ctx, embed=a.level != "0")
    if embedder is not None:
        embedder.embed([q.text for q in questions])  # before the threads: they then only read the cache
    total = embedder.cost_usd if embedder is not None else 0.0

    key = load_key(a.set)
    reps, partial = [], False
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    def save(is_partial: bool) -> Path:
        return save_run(a.runs_dir, a.set, a.level, {
            "model": model, "embed_model": EMBED_MODEL if a.level != "0" else "none", "limit": a.limit,
            "partial": is_partial, "n": len(questions), "cost_usd": total, "repeats": reps}, stamp=stamp)

    for i in range(repeats):
        if total >= a.budget:  # no money left for another repeat: never save an empty one
            partial = True
            print(f"  Budget of ${a.budget:.2f} reached before repeat {i + 1}. The run is marked partial.")
            break
        res, stopped = _run_repeat(a.level, questions, ctx, a.budget - total, a.workers)
        total += sum(r["cost_usd"] for r in res.values())
        answers = {q: r["answer"] for q, r in res.items()}
        reps.append({
            "answers": answers,
            "seconds": {q: r["seconds"] for q, r in res.items()},
            "cost_usd": {q: r["cost_usd"] for q, r in res.items()},
            "calls": {q: r["calls"] for q, r in res.items()},
            "llm_seconds": {q: r["llm_seconds"] for q, r in res.items()},
            "errors": {q: r["answer"]["error"] for q, r in res.items() if r["answer"].get("error")},
        })
        s = score(answers, {q: key[q] for q in answers})
        ceiling = f", top-20 ceiling {s.ceiling:.0%}, made up {s.made_up:.0%}" if s.ceiling is not None else ""
        print(f"  repeat {i + 1}: all found {s.all_found:.0%}, recall {s.recall:.0%}{ceiling}, "
              f"errors {s.errors}, API failures {s.failed}")
        save(True)  # after every repeat, so a crash never loses what was spent
        if stopped:
            partial = True
            print(f"  Budget of ${a.budget:.2f} reached: stopped. The run is marked partial.")
            break

    path = save(partial)
    print(f"Saved {path}. Spent ${total:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
