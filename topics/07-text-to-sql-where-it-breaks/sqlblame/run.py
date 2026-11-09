"""Run one level over a set of questions and save a run file.

From the repo root (PowerShell):
    $env:PYTHONPATH = ".;topics/05-evaluator-optimizer-text-to-sql;topics/07-text-to-sql-where-it-breaks"
    .venv\\Scripts\\python -m sqlblame.run --level C --dry-run
    .venv\\Scripts\\python -m sqlblame.run --level C --repeats 3 --yes [--set test] [--smoke --limit 5]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from shared.llm import PRICES, Tracker, cost_usd, default_model, llm_call, load_env, require_api_key
from sqlblame.gold_tables import load_gold
from sqlblame.levels import LEVELS, Ctx, solve
from sqlblame.paths import RUNS_DIR
from sqlblame.score import score
from sqlblame.warehouse import ALL_DBS, load_warehouse, render_cards, render_tables
from sqlloop.data import SETS, db_path, load_set
from sqlloop.execute import run_sql, same_result
from sqlloop.models import Question
from sqlloop.schema import render_schema

TOPIC_CEILING_USD = 10.0
SMOKE_MARGIN = 1.5  # measured cost per item x this, to stay on the safe side
RUN_TIMEOUT_S = 10.0
GOLD_TIMEOUT_S = 30.0
PROMPT_CHARS = 2000  # instructions and question on top of the schema or cards
OUTPUT_TOKENS_PER_CALL = 1500  # includes reasoning, billed as output


def load_cards():
    return load_warehouse(list(ALL_DBS))


def _price(model: str, chars: float) -> float:
    p = PRICES[model]
    return ((chars + PROMPT_CHARS) / 4 * p["input"] + OUTPUT_TOKENS_PER_CALL * p["output"]) / 1_000_000


def estimate_cost_usd(level: str, questions: list[Question], model: str, repeats: int, gold: dict, cards) -> float:
    """Upper side: characters / 4 as tokens, no caching discount, a long answer every call."""
    total = 0.0
    for q in questions:
        whole = len(render_schema(db_path(q.db_id)))
        if level == "A":
            total += _price(model, whole)
        elif level == "B":
            total += _price(model, len(render_tables([(q.db_id, t) for t in gold[str(q.qid)]], path_of=db_path)))
        else:  # the agent reads every card, then the writer gets about a database's worth of schema
            total += _price(model, len(render_cards(cards))) + _price(model, whole)
    return total * repeats


def measured_estimate(kind: str, n_items: int, repeats: int, runs_dir: Path) -> float | None:
    """Cost from the latest smoke file of this kind ("level-A" ... or "judge"): per item x n x repeats x margin."""
    smoke = runs_dir / "smoke"
    files = sorted(smoke.glob(f"{kind}-*.json")) if smoke.exists() else []
    if not files:
        return None
    run = json.loads(files[-1].read_text(encoding="utf-8"))
    if "repeats" in run:
        costs = [o.get("cost_usd", 0.0) for r in run["repeats"] for o in r["results"].values()]
        per = sum(costs) / len(costs) if costs else None
    else:
        per = run["cost_usd"] / len(run["scores"]) if run.get("scores") else None
    return None if per is None else per * n_items * repeats * SMOKE_MARGIN


def spent_in_runs(runs_dir: Path) -> float:
    total = 0.0
    if not runs_dir.exists():
        return total
    for path in runs_dir.rglob("level-*.json"):
        run = json.loads(path.read_text(encoding="utf-8"))
        total += sum(o.get("cost_usd", 0.0) for r in run.get("repeats", []) for o in r["results"].values())
    for path in runs_dir.rglob("judge-*.json"):
        total += json.loads(path.read_text(encoding="utf-8")).get("cost_usd", 0.0)
    return total


@lru_cache(maxsize=None)
def _gold_rows(db: str, sql: str):
    r = run_sql(db, sql, timeout_s=GOLD_TIMEOUT_S)
    if r.rows is None:
        raise RuntimeError(f"gold SQL failed: {r.error}")
    return r.rows


def _process(q: Question, level: str, model: str, gold: list[str], cards) -> dict:
    ctx = Ctx(model, Tracker(), llm=llm_call)
    start = time.perf_counter()
    try:
        out = solve(q, level, ctx, gold, cards, path_of=db_path)
        db = str(db_path(q.db_id))
        r = run_sql(db, out["sql"], timeout_s=RUN_TIMEOUT_S)
        out.update(error="", final_error=r.error, n_rows=r.n_rows if r.rows is not None else None,
                   right=r.rows is not None and same_result(r.rows, _gold_rows(db, q.gold_sql)))
    except Exception as exc:  # the SDK already retried; record and move on
        out = {"sql": "", "given_tables": [], "picked": None, "made_up": None, "agent_empty": False,
               "error": f"{type(exc).__name__}: {exc}", "final_error": "", "n_rows": None, "right": False}
    out["seconds"] = time.perf_counter() - start
    out["calls"] = [asdict(r) for r in ctx.tracker.records]
    out["cost_usd"] = sum(cost_usd(r) for r in ctx.tracker.records)
    return out


def guard(estimate: float, budget: float, runs_dir: Path, dry_run: bool, yes: bool) -> int | None:
    """Shared by the runner and the judge: None means go ahead, otherwise the exit code."""
    if dry_run:
        return 0
    if estimate > budget:
        print(f"Over the ${budget:.2f} budget. Not running.")
        return 2
    if spent_in_runs(runs_dir) + estimate > TOPIC_CEILING_USD:
        print(f"Would pass the ${TOPIC_CEILING_USD:.0f} topic ceiling. Not running.")
        return 2
    if not yes and input("Run? [y/N] ").strip().lower() != "y":
        return 1
    return None


def out_dir_for(runs_dir: Path, set_name: str, smoke: bool) -> Path:
    return runs_dir / "smoke" if smoke else (runs_dir if set_name == "main" else runs_dir / set_name)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run one level over a set of questions.")
    ap.add_argument("--level", required=True, choices=LEVELS)
    ap.add_argument("--set", default="main", choices=SETS, help="main (tuning allowed) or test (held out)")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--limit", type=int, default=None, help="only the first N questions")
    ap.add_argument("--budget", type=float, default=3.0, help="abort if the estimate is over this many USD")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--smoke", action="store_true", help="save under runs/smoke (never reported)")
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--runs-dir", type=Path, default=RUNS_DIR)
    args = ap.parse_args(argv)

    load_env()
    model = default_model("small")
    require_api_key(model)
    questions = load_set(args.set)[: args.limit] if args.limit else load_set(args.set)
    gold, cards = load_gold(), load_cards()

    estimate, how = estimate_cost_usd(args.level, questions, model, args.repeats, gold, cards), "upper-side guess"
    measured = None if args.smoke else measured_estimate(f"level-{args.level}", len(questions), args.repeats, args.runs_dir)
    if measured is not None:
        estimate, how = measured, f"measured in the smoke run, x{SMOKE_MARGIN}"
    print(f"Level {args.level} on {model}, {args.set} set: {len(questions)} questions x {args.repeats} repeats. "
          f"Estimated cost ${estimate:.2f}, {how} (spent so far ${spent_in_runs(args.runs_dir):.2f} of ${TOPIC_CEILING_USD:.0f})")
    stop = guard(estimate, args.budget, args.runs_dir, args.dry_run, args.yes)
    if stop is not None:
        return stop

    difficulty = {str(q.qid): q.difficulty for q in questions}
    db_of = {str(q.qid): q.db_id for q in questions}
    repeats = []
    for i in range(args.repeats):
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            outs = list(pool.map(lambda q: _process(q, args.level, model, gold[str(q.qid)], cards), questions))
        results = {str(q.qid): o for q, o in zip(questions, outs)}
        s = score(results, difficulty, gold, db_of)
        repeats.append({"results": results, "scores": s})
        extra = f", all tables found {s['all_found']:.0%}" if s["all_found"] is not None else ""
        print(f"  repeat {i + 1}: right {s['right']:.0%}{extra}, api errors {s['api_errors']}, "
              f"${sum(o['cost_usd'] for o in outs):.4f}")

    out_dir = out_dir_for(args.runs_dir, args.set, args.smoke)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = out_dir / f"level-{args.level}-{stamp}.json"
    run = {"level": args.level, "model": model, "set": args.set, "created": stamp, "questions": len(questions),
           "repeats": repeats}
    path.write_text(json.dumps(run, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"Saved {path}. Spent ${sum(o['cost_usd'] for r in repeats for o in r['results'].values()):.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
