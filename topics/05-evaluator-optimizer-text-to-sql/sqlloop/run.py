"""Run one level over a set of questions and save a run file.

From the repo root (PowerShell):
    $env:PYTHONPATH = ".;topics/05-evaluator-optimizer-text-to-sql"
    .venv\Scripts\python -m sqlloop.run --level 1 --dry-run
    .venv\Scripts\python -m sqlloop.run --level 1 --repeats 3 --yes [--set test] [--smoke --limit 5]
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
from sqlloop.data import SETS, TOPIC_DIR, db_path, load_set
from sqlloop.execute import run_sql, same_result
from sqlloop.levels import MAX_ROUNDS, RUN_TIMEOUT_S, Ctx, solve
from sqlloop.models import Question
from sqlloop.schema import render_schema
from sqlloop.score import score

RUNS_DIR = TOPIC_DIR / "runs"
LEVELS = ("0", "1", "2", "3", "0+", "4", "5")
TOPIC_CEILING_USD = 10.0
GOLD_TIMEOUT_S = 30.0
MAX_CALLS = {"0": 1, "0+": 1, "1": 2 * MAX_ROUNDS, "2": MAX_ROUNDS, "3": 2 * MAX_ROUNDS, "4": 2 * MAX_ROUNDS, "5": 2 * MAX_ROUNDS}
PROMPT_CHARS = 2500  # instructions, question, history on top of the schema
OUTPUT_TOKENS_PER_CALL = 1500  # includes reasoning, billed as output


def model_for(level: str) -> str:
    return default_model("large" if level == "0+" else "small")


def grader_for(level: str) -> str | None:
    """The grading model: none at levels 0, 0+ and 2; the writer itself at 1 and 3; the large model at 4 and 5."""
    if level in ("4", "5"):
        return default_model("large")
    return model_for(level) if level in ("1", "3") else None


def estimate_cost_usd(level: str, questions: list[Question], model: str, repeats: int,
                      grader: str | None = None) -> float:
    """Upper side: every question uses the most calls, no caching discount, characters ÷ 4 as tokens.
    With a separate grader, half the calls are priced at the grader's rates."""
    total = 0.0
    calls = [(model, MAX_CALLS[level])] if not grader or grader == model else [(model, MAX_ROUNDS), (grader, MAX_ROUNDS)]
    for q in questions:
        tokens = (len(render_schema(db_path(q.db_id))) + PROMPT_CHARS) / 4
        for m, n in calls:
            p = PRICES[m]
            total += n * (tokens * p["input"] + OUTPUT_TOKENS_PER_CALL * p["output"]) / 1_000_000
    return total * repeats


SMOKE_MARGIN = 1.5  # measured cost per question × this, to stay on the safe side


def measured_estimate(level: str, n_questions: int, repeats: int, runs_dir: Path) -> float | None:
    """Cost from the latest smoke run of this level (as the design says: measured cost replaces the guess)."""
    files = sorted((runs_dir / "smoke").glob(f"level-{level}-*.json")) if (runs_dir / "smoke").exists() else []
    if not files:
        return None
    run = json.loads(files[-1].read_text(encoding="utf-8"))
    costs = [o.get("cost_usd", 0.0) for r in run["repeats"] for o in r["results"].values()]
    return (sum(costs) / len(costs)) * n_questions * repeats * SMOKE_MARGIN if costs else None


def spent_in_runs(runs_dir: Path) -> float:
    total = 0.0
    for path in runs_dir.rglob("level-*.json") if runs_dir.exists() else []:
        run = json.loads(path.read_text(encoding="utf-8"))
        total += sum(o.get("cost_usd", 0.0) for r in run.get("repeats", []) for o in r["results"].values())
    return total


@lru_cache(maxsize=None)
def _gold(db: str, sql: str):
    r = run_sql(db, sql, timeout_s=GOLD_TIMEOUT_S)
    if r.rows is None:
        raise RuntimeError(f"gold SQL failed: {r.error}")
    return r.rows


def _judge(q: Question, sql: str, cache: dict) -> tuple[bool, str]:
    if sql not in cache:
        db = str(db_path(q.db_id))
        r = run_sql(db, sql, timeout_s=RUN_TIMEOUT_S)
        cache[sql] = (r.rows is not None and same_result(r.rows, _gold(db, q.gold_sql)), r.error)
    return cache[sql]


def _process(q: Question, level: str, model: str) -> dict:
    grader = grader_for(level)
    ctx = Ctx(model, grader if grader != model else None, Tracker(), llm=llm_call)
    start = time.perf_counter()
    try:
        out = solve(q, level, ctx, db_path(q.db_id))
        cache: dict = {}
        for rnd in out["rounds"]:
            rnd["right"], rnd["run_error"] = _judge(q, rnd["sql"], cache)
        out.update(error="", right=out["rounds"][-1]["right"], first_right=out["rounds"][0]["right"],
                   final_error=out["rounds"][-1]["run_error"])
    except Exception as exc:  # the SDK already retried; record and move on
        out = {"rounds": [], "final_sql": "", "stop": "error", "error": f"{type(exc).__name__}: {exc}",
               "right": False, "first_right": False, "final_error": ""}
    out["seconds"] = time.perf_counter() - start
    out["calls"] = [asdict(r) for r in ctx.tracker.records]
    out["cost_usd"] = sum(cost_usd(r) for r in ctx.tracker.records)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run one level over a set of questions.")
    ap.add_argument("--level", required=True, choices=LEVELS)
    ap.add_argument("--set", default="main", choices=SETS, help="main (tuning allowed) or test (held out)")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--limit", type=int, default=None, help="only the first N questions")
    ap.add_argument("--budget", type=float, default=5.0, help="abort if the estimate is over this many USD")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--smoke", action="store_true", help="save under runs/smoke (never reported)")
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--runs-dir", type=Path, default=RUNS_DIR)
    args = ap.parse_args(argv)

    load_env()
    model = model_for(args.level)
    require_api_key(model)
    grader = grader_for(args.level)
    if grader:
        require_api_key(grader)
    questions = load_set(args.set)[: args.limit] if args.limit else load_set(args.set)
    out_dir = args.runs_dir / "smoke" if args.smoke else (args.runs_dir if args.set == "main" else args.runs_dir / args.set)

    estimate = estimate_cost_usd(args.level, questions, model, args.repeats, grader)
    measured = None if args.smoke else measured_estimate(args.level, len(questions), args.repeats, args.runs_dir)
    how = "upper-side guess"
    if measured is not None:
        estimate, how = measured, f"measured in the smoke run, ×{SMOKE_MARGIN}"
    spent = spent_in_runs(args.runs_dir)
    print(f"Level {args.level} on {model}" + (f", graded by {grader}" if grader and grader != model else "") + f", {args.set} set: {len(questions)} questions × {args.repeats} repeats. "
          f"Estimated cost ${estimate:.2f}, {how} (spent so far ${spent:.2f} of ${TOPIC_CEILING_USD:.0f})")
    if args.dry_run:
        return 0
    if estimate > args.budget:
        print(f"Over the ${args.budget:.2f} budget. Not running.")
        return 2
    if spent + estimate > TOPIC_CEILING_USD:
        print(f"Would pass the ${TOPIC_CEILING_USD:.0f} topic ceiling. Not running.")
        return 2
    if not args.yes and input("Run? [y/N] ").strip().lower() != "y":
        return 1

    difficulty = {str(q.qid): q.difficulty for q in questions}
    repeats = []
    for i in range(args.repeats):
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            outs = list(pool.map(lambda q: _process(q, args.level, model), questions))
        results = {str(q.qid): o for q, o in zip(questions, outs)}
        s = score(results, difficulty)
        repeats.append({"results": results, "scores": s})
        cost = sum(o["cost_usd"] for o in outs)
        print(f"  repeat {i + 1}: right {s['right']:.0%} (first try {s['first_right']:.0%}), fixed {s['fixed']}, "
              f"broken {s['broken']}, rounds {s['rounds']:.2f}, api errors {s['api_errors']}, ${cost:.4f}")

    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = out_dir / f"level-{args.level}-{stamp}.json"
    run = {"level": args.level, "model": model, "grader_model": grader, "set": args.set, "created": stamp, "questions": len(questions), "repeats": repeats}
    path.write_text(json.dumps(run, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"Saved {path.relative_to(args.runs_dir.parent) if args.runs_dir.parent in path.parents else path}. "
          f"Spent ${sum(o['cost_usd'] for r in repeats for o in r['results'].values()):.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
