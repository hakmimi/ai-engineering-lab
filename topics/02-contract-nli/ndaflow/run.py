"""Run one level over a set of contracts and save a run file.

From the repo root (PowerShell):
    $env:PYTHONPATH = ".;topics/02-contract-nli"
    .venv\\Scripts\\python -m ndaflow.run --level 3 --repeats 3
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Callable

from ndaflow.data import SETS, load_answer_key, load_contracts, load_statements
from ndaflow.levels import Ctx, run_level0, run_level1, run_level2, run_level3
from ndaflow.models import Answer, Answers, Contract
from ndaflow.prompts import render_contract
from ndaflow.score import score
from shared.llm import PRICES, Tracker, cost_usd, default_model, load_env, require_api_key

RUNS_DIR = Path(__file__).resolve().parent.parent / "runs"

LEVELS: dict[str, Callable[[Contract, Ctx], Answers]] = {
    "0": run_level0,
    "1": run_level1,
    "2": run_level2,
    "3": run_level3,
    "0+": run_level0,
}

CALLS_PER_CONTRACT = {"0": 1, "0+": 1, "1": 2, "2": 18, "3": 35}  # 17 statements; level 3 = 2 per statement + route
PROMPT_CHARS = 4000  # instructions and statements on top of the contract
OUTPUT_TOKENS_PER_CALL = 1500  # rough: includes thinking, which is billed as output


def model_for(level: str) -> str:
    return default_model("large" if level == "0+" else "small")


def estimate_cost_usd(level: str, contracts: list[Contract], model: str, repeats: int) -> float:
    """Upper side: every call holds the whole contract (characters ÷ 4 as tokens), no caching discount."""
    price = PRICES[model]
    total = 0.0
    for c in contracts:
        input_tokens = (len(render_contract(c)) + PROMPT_CHARS) / 4
        total += CALLS_PER_CONTRACT[level] * (input_tokens * price["input"] + OUTPUT_TOKENS_PER_CALL * price["output"]) / 1_000_000
    return total * repeats


def _run_contract(fn, contract: Contract, base: Ctx) -> dict:
    ctx = Ctx(base.statements, base.model, Tracker())
    start = time.perf_counter()
    error = ""
    try:
        answers = fn(contract, ctx)
    except Exception as exc:  # the SDK already retried; record and move on
        error = f"{type(exc).__name__}: {exc}"
        answers = {s.sid: Answer("error") for s in base.statements}
    return {
        "answers": {sid: asdict(a) for sid, a in answers.items()},
        "error": error,
        "seconds": time.perf_counter() - start,
        "calls": [asdict(r) for r in ctx.tracker.records],
        "cost_usd": sum(cost_usd(r) for r in ctx.tracker.records),
    }


def as_answers(results: dict) -> dict[str, Answers]:
    """Run-file results back into Answers, for scoring."""
    return {doc: {sid: Answer(a["label"], a["evidence"]) for sid, a in r["answers"].items()} for doc, r in results.items()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one level over a set of contracts.")
    parser.add_argument("--level", required=True, choices=list(LEVELS))
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--limit", type=int, default=None, help="only the first N contracts")
    parser.add_argument("--budget", type=float, default=10.0, help="abort if the estimate is over this many USD")
    parser.add_argument("--workers", type=int, default=4, help="contracts processed at the same time")
    parser.add_argument("--yes", action="store_true", help="do not ask for confirmation")
    parser.add_argument("--dry-run", action="store_true", help="print the estimate and stop")
    parser.add_argument("--runs-dir", type=Path, default=RUNS_DIR)
    parser.add_argument("--set", default="main", choices=list(SETS), help="main (tuning allowed) or test (held out)")
    args = parser.parse_args(argv)

    load_env()  # before model_for(): CLAIMS_MODEL may be set only in .env
    model = model_for(args.level)
    require_api_key(model)
    all_contracts = load_contracts(args.set)
    contracts = all_contracts[: args.limit] if args.limit else all_contracts
    key = load_answer_key(args.set)
    runs_dir = args.runs_dir if args.set == "main" else args.runs_dir / args.set
    base = Ctx(load_statements(), model, Tracker())

    estimate = estimate_cost_usd(args.level, contracts, model, args.repeats)
    print(f"Level {args.level} on {model}, {args.set} set: {len(contracts)} contracts × {args.repeats} repeats. Estimated cost ${estimate:.2f}")
    if args.dry_run:
        return 0
    if estimate > args.budget:
        print(f"Over the ${args.budget:.2f} budget. Not running.")
        return 2
    if not args.yes and input("Run? [y/N] ").strip().lower() != "y":
        return 1

    fn = LEVELS[args.level]
    repeats = []
    for i in range(args.repeats):
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            outs = list(pool.map(lambda c: _run_contract(fn, c, base), contracts))
        results = {c.doc_id: o for c, o in zip(contracts, outs)}
        s = score(as_answers(results), key)
        repeats.append({"results": results, "scores": s.as_dict()})
        print(f"  repeat {i + 1}: label right {s.label_right:.0%}, F1 entailment {s.f1_entailment:.2f}, "
              f"F1 contradiction {s.f1_contradiction:.2f}, evidence found {s.evidence_recall:.0%}, errors {s.errors}")

    runs_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = runs_dir / f"level-{args.level}-{stamp}.json"
    run = {"level": args.level, "model": model, "set": args.set, "created": stamp, "contracts": len(contracts), "repeats": repeats}
    path.write_text(json.dumps(run, indent=1, ensure_ascii=False), encoding="utf-8")
    spent = sum(o["cost_usd"] for r in repeats for o in r["results"].values())
    print(f"Saved {path.name}. Spent ${spent:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
