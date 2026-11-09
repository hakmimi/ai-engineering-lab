"""Run one review level over one set and save a run file.

From the worktree root (PowerShell):
    $env:PYTHONPATH = ".;topics/04-agent-security-review-agentdojo"
    python -m agentreview.run --level 2 --set main --repeats 3
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from agentreview.data import SETS, load_grants, load_key, load_sessions
from agentreview.levels import Ctx, run_level0, run_level1, run_level2
from agentreview.models import Session, Verdict, verdict_from_dict
from agentreview.prompts import SYSTEM
from agentreview.score import score
from agentreview.transcript import render
from shared.llm import PRICES, Tracker, cost_usd, load_env, require_api_key

RUNS_DIR = Path(__file__).resolve().parent.parent / "runs"
LEVELS = {"0": run_level0, "1": run_level1, "2": run_level2}
TOPIC_CEILING_USD = 5.0
GRANT_CHARS = 1500  # the grant text and tool list in each prompt
OUTPUT_TOKENS_PER_CALL = 400
RERUN_FACTOR = {"0": 0.0, "1": 1.0, "2": 1.2}


def review_model() -> str:
    return os.environ.get("REVIEW_MODEL", "claude-haiku-5-5")


def estimate_cost_usd(level: str, sessions: list[Session], model: str, repeats: int) -> float:
    """Upper side: characters ÷ 4 as tokens, no caching discount."""
    if level == "0":
        return 0.0
    price = PRICES[model]
    total = 0.0
    for s in sessions:
        input_tokens = (len(render(s)) + len(SYSTEM) + GRANT_CHARS) / 4
        total += (input_tokens * price["input"] + OUTPUT_TOKENS_PER_CALL * price["output"]) / 1_000_000
    return total * RERUN_FACTOR[level] * repeats


def spent_so_far(runs_dir: Path) -> float:
    total = 0.0
    for path in runs_dir.rglob("*.json"):
        try:
            total += float(json.loads(path.read_text(encoding="utf-8")).get("cost_usd", 0))
        except (ValueError, AttributeError):
            continue
    return total


def _review_all(fn, sessions: list[Session], grants: dict, model: str, budget: float, workers: int) -> tuple[dict, bool]:
    spent = Tracker()
    stopped = threading.Event()
    out: dict[str, dict] = {}

    def one(s: Session) -> None:
        if spent.total_cost_usd() >= budget:
            stopped.set()
            return
        ctx = Ctx(grants, model, Tracker())
        start = time.perf_counter()
        try:
            v = fn(s, ctx)
        except Exception as exc:  # the SDK already retried; record and move on
            v = Verdict(0, "error", [], "error", [f"{type(exc).__name__}: {exc}"[:300]])
        for r in ctx.tracker.records:
            spent.add(r)
        out[s.sid] = {
            "verdict": asdict(v),
            "seconds": time.perf_counter() - start,
            "cost_usd": sum(cost_usd(r) for r in ctx.tracker.records),
            "calls": len(ctx.tracker.records),
        }

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(one, sessions))
    return out, stopped.is_set()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one review level over one set of sessions.")
    parser.add_argument("--level", required=True, choices=list(LEVELS))
    parser.add_argument("--set", default="main", choices=list(SETS))
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--limit", type=int, default=None, help="only the first N sessions (smoke runs; the report ignores them)")
    parser.add_argument("--budget", type=float, default=1.0, help="stop starting new sessions once this many USD are spent")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--yes", action="store_true", help="do not ask for confirmation")
    parser.add_argument("--dry-run", action="store_true", help="print the estimate and stop")
    parser.add_argument("--runs-dir", type=Path, default=RUNS_DIR)
    args = parser.parse_args(argv)

    load_env()  # before review_model(): REVIEW_MODEL may be set only in .env
    model = review_model() if args.level != "0" else "none"
    repeats = 1 if args.level == "0" else args.repeats
    sessions = load_sessions(args.set)[: args.limit] if args.limit else load_sessions(args.set)

    estimate = estimate_cost_usd(args.level, sessions, model, repeats)
    spent = spent_so_far(args.runs_dir)
    print(f"Level {args.level} on {model}, {args.set} set: {len(sessions)} sessions × {repeats} repeats. "
          f"Estimated cost ${estimate:.3f} (spent so far ${spent:.3f})")
    if args.dry_run:
        return 0
    if spent + estimate > TOPIC_CEILING_USD:
        print(f"That would pass the ${TOPIC_CEILING_USD:.2f} topic ceiling. Not running.")
        return 2
    if args.level != "0":
        require_api_key(model)
    if not args.yes and input("Run? [y/N] ").strip().lower() != "y":
        return 1

    key = load_key(args.set)
    grants = load_grants()
    fn = LEVELS[args.level]
    runs, partial, total = [], False, 0.0
    for i in range(repeats):
        results, stopped = _review_all(fn, sessions, grants, model, args.budget - total, args.workers)
        partial = partial or stopped
        total += sum(r["cost_usd"] for r in results.values())
        verdicts = {sid: r["verdict"] for sid, r in results.items()}
        runs.append({
            "verdicts": verdicts,
            "seconds": {sid: r["seconds"] for sid, r in results.items()},
            "cost_usd": {sid: r["cost_usd"] for sid, r in results.items()},
            "calls": {sid: r["calls"] for sid, r in results.items()},
        })
        s = score({sid: verdict_from_dict(v) for sid, v in verdicts.items()}, {sid: key[sid] for sid in verdicts})
        print(f"  repeat {i + 1}: caught {s.caught:.0%} (act {s.caught_act:.0%}), false alarms {s.false_alarms:.0%}, "
              f"refused flagged {s.refused_flagged:.0%}, errors {s.errors}, not reviewed {s.not_reviewed}")
        if stopped:
            print(f"  Budget of ${args.budget:.2f} reached: stopped. The run is marked partial.")
            break

    out_dir = args.runs_dir / args.set
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = out_dir / f"level-{args.level}-{stamp}.json"
    run = {
        "level": args.level, "set": args.set, "model": model, "created": stamp, "limit": args.limit,
        "partial": partial, "sessions": len(sessions), "cost_usd": total, "repeats": runs,
    }
    path.write_text(json.dumps(run, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"Saved {path.relative_to(args.runs_dir)}. Spent ${total:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
