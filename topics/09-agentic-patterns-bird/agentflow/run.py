"""Run one level over a set of questions and save a run file (runs/<set>/level-<L>-<stamp>.json).

From the repo root (PowerShell):
    $env:PYTHONPATH = ".;topics/05-evaluator-optimizer-text-to-sql;topics/07-text-to-sql-where-it-breaks;topics/09-agentic-patterns-bird"
    .venv\\Scripts\\python -m agentflow.run --level 2 --dry-run
    .venv\\Scripts\\python -m agentflow.run --level 2 --limit 5 --repeats 1 --yes     (smoke run, never reported)
    .venv\\Scripts\\python -m agentflow.run --level 2 --yes [--set test]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import threading
from pathlib import Path

import anthropic
import openai

from agentflow.levels import AGENT_MAX_STEPS, LEVELS, N_WRITERS, Ctx, solve
from agentflow.paths import RUNS_DIR
from agentflow.score import consistency, rows_hash, score_repeat
from shared.llm import PRICES, Tracker, cost_usd, default_model, llm_call, load_env, require_api_key
from shared.runs import DEFAULT_CEILING_USD, over_ceiling, save_run, spent_so_far
from sqlblame.warehouse import ALL_DBS, load_warehouse, render_cards
from sqlloop.data import SETS, db_path, load_set
from sqlloop.execute import run_sql, same_result
from sqlloop.models import Question
from sqlloop.schema import render_schema

SMOKE_MARGIN = 1.5  # measured cost per question x this, to stay on the safe side
RUN_TIMEOUT_S = 10.0
GOLD_TIMEOUT_S = 30.0
PROMPT_CHARS = 2500  # instructions and question on top of the schema or cards
OUTPUT_TOKENS_PER_CALL = 1500  # includes reasoning, billed as output
API_ERRORS = (openai.OpenAIError, anthropic.AnthropicError)  # anything else is our bug: the run stops
SKIPPED = "skipped: over budget"


def load_cards():
    return load_warehouse(list(ALL_DBS))


def _price(model: str, chars: float, calls: float = 1) -> float:
    p = PRICES[model]
    return calls * ((chars + PROMPT_CHARS) / 4 * p["input"] + OUTPUT_TOKENS_PER_CALL * p["output"]) / 1_000_000


def estimate_cost_usd(level: str, questions: list[Question], model: str, repeats: int, cards) -> float:
    """Upper side: characters / 4 as tokens, no caching discount, a long answer every call."""
    cards_chars = len(render_cards(cards))
    warehouse = sum(len(render_schema(db_path(d))) for d in sorted({c.db_id for c in cards}))
    total = 0.0
    for q in questions:
        db = len(render_schema(db_path(q.db_id)))
        route = _price(model, cards_chars)
        total += {
            "0": lambda: _price(model, warehouse),
            "1": lambda: route + _price(model, db),
            "1h": lambda: route + _price(model, db),
            "2": lambda: route + _price(model, db, N_WRITERS),
            "3": lambda: route + _price(model, db, 4),  # planner, 2 workers, combiner
            "4": lambda: route + _price(model, db, 4),  # about 2 rounds of writer + grader
            # the agent: 8 of its 10 steps, each re-reading the cards plus a history that grows to about
            # one described database and a few result previews
            "5": lambda: _price(model, cards_chars + 1.5 * db + 4000, 8),
        }[level]()
    return total * repeats


def measured_estimate(level: str, n_items: int, repeats: int, runs_dir: Path) -> float | None:
    """Cost per question from the newest smoke run (limit set) of this level, x n x repeats x margin."""
    best = None
    for path in runs_dir.rglob(f"level-{level}-*.json") if runs_dir.exists() else []:
        run = json.loads(path.read_text(encoding="utf-8"))
        if run.get("limit") is not None and (best is None or path.name > best[0]):
            best = (path.name, run)
    if best is None:
        return None
    run = best[1]
    per = run["cost_usd"] / (run["questions"] * max(1, len(run["repeats"])))
    return per * n_items * repeats * SMOKE_MARGIN


class Ledger:
    """Money spent in this command, shared by the worker threads; new questions stop once it passes the budget."""

    def __init__(self, budget: float):
        self.budget, self.total, self._lock = budget, 0.0, threading.Lock()

    def add(self, usd: float) -> None:
        with self._lock:
            self.total += usd

    def over(self) -> bool:
        with self._lock:
            return self.total > self.budget


def gold_rows(questions: list[Question]) -> tuple[dict, list[str]]:
    """Every gold query run once, before any model call: (qid -> rows, failures)."""
    rows, failed = {}, []
    for q in questions:
        r = run_sql(db_path(q.db_id), q.gold_sql, timeout_s=GOLD_TIMEOUT_S)
        if r.rows is None:
            failed.append(f"question {q.qid}: {r.error}")
        rows[str(q.qid)] = r.rows
    return rows, failed


def _empty(error: str) -> dict:
    return {"db": None, "sql": "", "stop": "", "handoff": False, "error": error, "final_error": "", "rows_hash": "",
            "n_rows": None, "right": False}


def _process(q: Question, level: str, model: str, cards, gold, ledger: Ledger) -> dict:
    if ledger.over():
        return _empty(SKIPPED) | {"seconds": 0.0, "calls": [], "cost_usd": 0.0}
    ctx = Ctx(model, Tracker(), llm=llm_call)
    start = time.perf_counter()
    try:
        out = solve(q, level, ctx, cards, path_of=db_path)
        seconds = time.perf_counter() - start  # the level only; running and scoring the final SQL is not counted
        out.update(error="", final_error="", rows_hash="", n_rows=None, right=False)
        if out["db"] and out["sql"]:
            r = run_sql(db_path(out["db"]), out["sql"], timeout_s=RUN_TIMEOUT_S)
            out["final_error"] = r.error
            if r.rows is not None:
                out["rows_hash"], out["n_rows"] = rows_hash(r.rows), r.n_rows
                out["right"] = out["db"] == q.db_id and same_result(r.rows, gold)
    except API_ERRORS as exc:  # the SDK already retried; record and move on
        out, seconds = _empty(f"{type(exc).__name__}: {exc}"), time.perf_counter() - start
    finally:
        ledger.add(sum(cost_usd(r) for r in ctx.tracker.records))
    out["seconds"] = seconds
    out["calls"] = [asdict(r) for r in ctx.tracker.records]
    out["cost_usd"] = sum(cost_usd(r) for r in ctx.tracker.records)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run one level over a set of questions.")
    ap.add_argument("--level", required=True, choices=LEVELS)
    ap.add_argument("--set", default="main", choices=SETS, help="main (tuning allowed) or test (held out)")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--limit", type=int, default=None, help="only the first N questions (a smoke run, never reported)")
    ap.add_argument("--budget", type=float, default=1.5, help="refuse if the estimate is over this many USD; "
                                                              "stop starting questions once this much is spent")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--runs-dir", type=Path, default=RUNS_DIR)
    args = ap.parse_args(argv)

    load_env()
    model = default_model("small")
    questions = load_set(args.set)[: args.limit] if args.limit else load_set(args.set)
    cards = load_cards()
    spent = spent_so_far(args.runs_dir)

    estimate, how = estimate_cost_usd(args.level, questions, model, args.repeats, cards), "upper-side guess"
    measured = None if args.limit else measured_estimate(args.level, len(questions), args.repeats, args.runs_dir)
    if measured is not None:
        estimate, how = measured, f"measured in the smoke run, x{SMOKE_MARGIN}"
    print(f"Level {args.level} on {model}, {args.set} set: {len(questions)} questions x {args.repeats} repeats. "
          f"Estimated ${estimate:.2f} ({how}); spent so far ${spent:.2f} of ${DEFAULT_CEILING_USD:.0f}")
    if args.dry_run:
        return 0
    if estimate > args.budget:
        print(f"Over the ${args.budget:.2f} budget. Not running.")
        return 2
    if over_ceiling(spent, estimate):
        print(f"Would pass the ${DEFAULT_CEILING_USD:.0f} topic ceiling. Not running.")
        return 2
    gold, failed = gold_rows(questions)
    if failed:
        print("Gold SQL failed, nothing run:\n  " + "\n  ".join(failed))
        return 3
    require_api_key(model)
    if not args.yes and input("Run? [y/N] ").strip().lower() != "y":
        return 1

    db_of = {str(q.qid): q.db_id for q in questions}
    ledger = Ledger(min(args.budget, DEFAULT_CEILING_USD - spent))
    repeats, partial, done = [], False, False
    try:
        for i in range(args.repeats):
            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                outs = list(pool.map(lambda q: _process(q, args.level, model, cards, gold[str(q.qid)], ledger), questions))
            results = {str(q.qid): o for q, o in zip(questions, outs)}
            s = score_repeat(results, db_of)
            repeats.append({"results": results, "scores": s})
            right = "-" if s["right"] is None else f"{s['right']:.0%}"
            print(f"  repeat {i + 1}: right {right}, api errors {s['api_errors']}, "
                  f"${sum(o['cost_usd'] for o in outs):.4f}")
            if any(o["error"] == SKIPPED for o in outs):
                print(f"Passed the ${ledger.budget:.2f} budget inside the repeat. Stopping; the run is marked partial.")
                partial = True
                break
            if i + 1 < args.repeats and ledger.total / (i + 1) * (i + 2) > ledger.budget:
                print(f"The next repeat would pass the ${ledger.budget:.2f} budget. Stopping; the run is marked partial.")
                partial = True
                break
        done = True
    finally:  # a crash still leaves a record of the money spent (marked partial, never reported)
        run = {"model": model, "limit": args.limit, "partial": partial or not done, "questions": len(questions),
               "cost_usd": ledger.total, "repeats": repeats, "consistency": consistency([r["results"] for r in repeats])}
        path = save_run(args.runs_dir, args.set, args.level, run)
        print(f"Saved {path}. Spent ${ledger.total:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
