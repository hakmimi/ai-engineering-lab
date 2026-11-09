"""Run one test: print the cost estimate, check the budget, call the API (only with --yes), save the run file.

    python -m ndaspeed.run --test 1 --dry-run                 # estimate only, nothing sent
    python -m ndaspeed.run --test 1 --model both --yes        # the real run
    python -m ndaspeed.run --test 2 --limit 1 --yes           # smoke run: one chat per pack
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
from datetime import datetime

from ndaflow import data
from ndaspeed import experiments
from ndaspeed.chat import ANSWER_TOKENS
from ndaspeed.config import MIN_OUTPUT_TOKENS, RUNS_DIR, SEED, TOPIC_CEILING_USD, make_client, model
from ndaspeed.cost import Budget, spent_in_runs
from ndaspeed.packs import PING, all_contracts, est_tokens, instructions, make_pack, stack_to
from shared.llm import PRICES

DEFAULTS = {"0": {"repeats": 10}, "1": {"small": 5, "large": 3}, "2": {"short_n": 10, "long_chats": 3},
            "3": {"reps": 10}, "4": {"chats": 3}}
TURNS = 17
ANSWER_OUT = ANSWER_TOKENS // 4  # planning guess for one answer's output (and its size in the history)


def test_kwargs(test: str, models: dict[str, str], repeats: int | None, limit: int | None) -> dict:
    """The counts a test runs with: its defaults, --repeats instead of every count, --limit as a cap."""
    def count(default: int) -> int:
        n = repeats or default
        return min(n, limit) if limit else n

    if test == "1":
        return {"rounds": {k: count(DEFAULTS["1"][k]) for k in models}}
    return {name: count(default) for name, default in DEFAULTS[test].items()}


def _chat_tokens(pack_tokens: int) -> tuple[int, int]:
    """Input and output tokens of one 17-turn chat, every turn priced as if nothing were cached."""
    base = est_tokens(instructions(None)) + pack_tokens
    return sum(base + t * (ANSWER_OUT + 30) for t in range(TURNS)), TURNS * ANSWER_OUT


def estimate_usd(test: str, models: dict[str, str], kwargs: dict) -> float:
    """An upper bound: every input token priced as uncached."""
    ping_in = est_tokens(instructions(None) + PING)

    def usd(m: str, tokens_in: int, tokens_out: int) -> float:
        return (tokens_in * PRICES[m]["input"] + tokens_out * PRICES[m]["output"]) / 1_000_000

    small = models.get("small") or next(iter(models.values()))
    if test == "0":
        n = kwargs["repeats"] + 1
        return usd(small, n * ping_in, n * MIN_OUTPUT_TOKENS)
    if test == "1":
        everything, sizes = all_contracts(), []
        for size in experiments.SIZES:
            try:
                sizes.append(make_pack("x", stack_to(everything, size)).est_tokens + ping_in)
            except ValueError:
                pass
        return sum(usd(m, ping_in + kwargs["rounds"][k] * sum(sizes), (1 + kwargs["rounds"][k] * len(sizes)) * MIN_OUTPUT_TOKENS)
                   for k, m in models.items())
    main = data.load_contracts("main")
    long_tokens = make_pack("long", main).est_tokens
    total = usd(small, ping_in, MIN_OUTPUT_TOKENS)  # warm-up
    if test == "2":
        short_tokens = int(statistics.mean(make_pack("s", [c]).est_tokens for c in main))
        for pack_tokens, chats in ((short_tokens, kwargs["short_n"]), (long_tokens, kwargs["long_chats"])):
            tin, tout = _chat_tokens(pack_tokens)
            total += 2 * chats * usd(small, tin, tout)
        return total
    if test == "3":
        one = est_tokens(instructions(None)) + long_tokens
        return total + kwargs["reps"] * usd(small, 3 * one, 2 * ANSWER_OUT + MIN_OUTPUT_TOKENS)
    if test == "4":
        tin, tout = _chat_tokens(long_tokens)
        return total + 2 * kwargs["chats"] * usd(small, tin, tout)
    raise ValueError(f"unknown test {test}")


def _run_test(test: str, client, models: dict[str, str], budget: Budget, kwargs: dict) -> dict:
    rng = random.Random(SEED)
    if test == "1":
        return experiments.test1(client, models, rng, budget, **kwargs)
    fn = {"0": experiments.test0, "2": experiments.test2, "3": experiments.test3, "4": experiments.test4}[test]
    return fn(client, models["small"], rng, budget, **kwargs)


def main(argv: list[str] | None = None, client=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--test", required=True, choices=["0", "1", "2", "3", "4"])
    p.add_argument("--model", choices=["small", "large", "both"], default="both", help="test 1 only")
    p.add_argument("--repeats", type=int, help="replaces every count of the test (rounds, chats, reps)")
    p.add_argument("--limit", type=int, help="caps every count (for smoke runs)")
    p.add_argument("--budget", type=float, default=3.0, help="USD; stops before a call that would pass it")
    p.add_argument("--dry-run", action="store_true", help="print the estimate, send nothing")
    p.add_argument("--yes", action="store_true", help="really call the API")
    args = p.parse_args(argv)

    keys = {"small": ["small"], "large": ["large"], "both": ["small", "large"]}[args.model] if args.test == "1" else ["small"]
    models = {k: model(k) for k in keys}
    kwargs = test_kwargs(args.test, models, args.repeats, args.limit)
    est = estimate_usd(args.test, models, kwargs)
    so_far = spent_in_runs(RUNS_DIR)
    print(f"Test {args.test} on {', '.join(models.values())} with {kwargs}")
    print(f"Cost estimate (upper bound): ${est:.2f} | spent so far: ${so_far:.2f} of ${TOPIC_CEILING_USD:.2f} "
          f"| budget for this command: ${args.budget:.2f}")
    if args.dry_run:
        return 0
    if not args.yes:
        print("Nothing sent. Add --yes to run.")
        return 0
    if so_far + est > TOPIC_CEILING_USD:
        print(f"Refused: ${so_far:.2f} spent + ${est:.2f} estimate would pass the topic ceiling of ${TOPIC_CEILING_USD:.2f}.")
        return 2

    run = _run_test(args.test, client or make_client(), models, Budget(args.budget), kwargs)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    path = RUNS_DIR / f"test{args.test}-{datetime.now():%Y%m%d-%H%M%S}.json"
    path.write_text(json.dumps(run, indent=1, ensure_ascii=False), encoding="utf-8")
    errors = sum(1 for r in run["records"] if r.get("timing", {}).get("error"))
    print(f"Saved {path.name}: {len(run['records'])} records, {errors} errors, spent ${run['spent_usd']:.4f}"
          + (" (stopped by the budget)" if run["stopped"] else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
