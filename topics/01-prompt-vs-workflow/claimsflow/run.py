"""Run one level over the test claims and save a run file.

From the repo root:
    .venv\\Scripts\\python -m claimsflow.run --level 3 --repeats 3
(pytest's pythonpath covers tests; for the CLI set PYTHONPATH to the repo root and the topic folder, see results.md)
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

from claimsflow import prompts
from claimsflow.data import load_answer_key, load_claims, load_customers, load_wordings
from claimsflow.levels import Ctx, run_level0, run_level1, run_level2, run_level3
from claimsflow.models import Claim, Result
from claimsflow.rules import CLAIM_TYPES, REQUIRED_DOCS
from claimsflow.score import score
from shared.llm import PRICES, Tracker, cost_usd, default_model, require_api_key

RUNS_DIR = Path(__file__).resolve().parent.parent / "runs"

LEVELS: dict[str, Callable[[Claim, Ctx], Result]] = {
    "0": run_level0,
    "1": run_level1,
    "2": run_level2,
    "3": run_level3,
    "0+": run_level0,
}

OUTPUT_TOKENS_PER_CALL = 1500  # rough: includes thinking, which is billed as output


def model_for(level: str) -> str:
    return default_model("large" if level == "0+" else "small")


def estimate_cost_usd(level: str, claims: list[Claim], ctx: Ctx, repeats: int) -> float:
    """Upper-side estimate: characters ÷ 4 as tokens, no caching discount."""
    price = PRICES[ctx.model]
    docs = max(len(d) for d in REQUIRED_DOCS.values())
    calls = {"0": 1, "0+": 1, "1": 2, "2": 2 + docs, "3": 5 + docs}[level]
    system_chars = len(prompts.level0_system(ctx.wordings, CLAIM_TYPES)) if level in ("0", "0+") else 6000
    total = 0.0
    for claim in claims:
        input_tokens = (system_chars + len(prompts.render_claim(claim)) + 1000) / 4
        total += calls * (input_tokens * price["input"] + OUTPUT_TOKENS_PER_CALL * price["output"]) / 1_000_000
    return total * repeats


def _run_claim(fn, claim: Claim, base: Ctx) -> dict:
    ctx = Ctx(base.customers, base.wordings, base.model, Tracker())
    start = time.perf_counter()
    try:
        result = fn(claim, ctx)
    except Exception as exc:  # the SDK already retried; record and move on
        result = Result("error", 0, [], f"{type(exc).__name__}: {exc}", None)
    seconds = time.perf_counter() - start
    out = asdict(result)
    out.update(
        seconds=seconds,
        calls=[asdict(r) for r in ctx.tracker.records],
        cost_usd=sum(cost_usd(r) for r in ctx.tracker.records),
    )
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one level over the test claims.")
    parser.add_argument("--level", required=True, choices=list(LEVELS))
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--limit", type=int, default=None, help="only the first N claims")
    parser.add_argument("--budget", type=float, default=10.0, help="abort if the estimate is over this many USD")
    parser.add_argument("--workers", type=int, default=4, help="claims processed at the same time")
    parser.add_argument("--yes", action="store_true", help="do not ask for confirmation")
    parser.add_argument("--dry-run", action="store_true", help="print the estimate and stop")
    parser.add_argument("--runs-dir", type=Path, default=RUNS_DIR)
    args = parser.parse_args(argv)

    require_api_key(model_for(args.level))
    claims = load_claims()[: args.limit] if args.limit else load_claims()
    key = load_answer_key()
    base = Ctx(load_customers(), load_wordings(), model_for(args.level), Tracker())

    estimate = estimate_cost_usd(args.level, claims, base, args.repeats)
    print(f"Level {args.level} on {base.model}: {len(claims)} claims × {args.repeats} repeats. Estimated cost ${estimate:.2f}")
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
            outs = list(pool.map(lambda c: _run_claim(fn, c, base), claims))
        results = {c.claim_id: o for c, o in zip(claims, outs)}
        as_results = {cid: Result(o["decision"], o["amount"], o["doc_problems"], o["reason"], o["claim_type"]) for cid, o in results.items()}
        scores = score(as_results, key)
        repeats.append({"results": results, "scores": scores.as_dict()})
        print(f"  repeat {i + 1}: decision right {scores.decision_right:.0%}, amount right {scores.amount_right:.0%}, errors {scores.errors}")

    args.runs_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = args.runs_dir / f"level-{args.level}-{stamp}.json"
    run = {"level": args.level, "model": base.model, "created": stamp, "claims": len(claims), "repeats": repeats}
    path.write_text(json.dumps(run, indent=1, ensure_ascii=False), encoding="utf-8")
    spent = sum(o["cost_usd"] for r in repeats for o in r["results"].values())
    print(f"Saved {path.name}. Spent ${spent:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
