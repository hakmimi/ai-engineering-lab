"""Uber's 'qualitative query similarity': an LLM scores 0-1 how close each final SQL is to the golden SQL.

It runs after the levels, on the SQL already stored in the run files, and never feeds back into an answer.

    python -m sqlblame.judge --set main --dry-run
    python -m sqlblame.judge --set main --yes [--smoke --limit 5]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from shared.llm import PRICES, Tracker, cost_usd, default_model, extract_xml, llm_call, load_env, require_api_key
from sqlblame.levels import LEVELS
from sqlblame.paths import RUNS_DIR
from sqlblame.run import (OUTPUT_TOKENS_PER_CALL, PROMPT_CHARS, SMOKE_MARGIN, TOPIC_CEILING_USD, guard,
                          measured_estimate, out_dir_for, spent_in_runs)
from sqlloop.data import SETS, load_set

JUDGE_PROMPT = """\
Compare a predicted SQLite query with the golden query written for the same question.

Question: {question}
Hint from the person asking: {evidence}

Golden query:
<golden>{gold}</golden>

Predicted query:
<predicted>{sql}</predicted>

How similar in intent is the predicted query to the golden one? Different but equivalent ways of writing it count as
similar. 1 means it does the same thing, 0 means it answers something else.
Think it through in <thoughts></thoughts>, then give one number from 0 to 1 in <score></score>.
"""


def read_score(text: str) -> float | None:
    raw = extract_xml(text, "score").strip()
    if not re.fullmatch(r"[0-9]*\.?[0-9]+", raw):
        return None
    v = float(raw)
    return v if 0.0 <= v <= 1.0 else None


def latest_runs(runs_dir: Path, set_name: str, smoke: bool) -> dict[str, dict]:
    folder = out_dir_for(runs_dir, set_name, smoke)
    runs = {}
    for level in LEVELS:
        files = sorted(folder.glob(f"level-{level}-*.json"))
        if files:
            runs[level] = json.loads(files[-1].read_text(encoding="utf-8"))
    return runs


def items_to_judge(runs: dict[str, dict], qids: set[str]) -> dict[str, tuple[str, str]]:
    """key "level|repeat|qid" -> (qid, sql), for every answer that has SQL and no API error."""
    items = {}
    for level, run in runs.items():
        for i, rep in enumerate(run["repeats"]):
            for qid, o in rep["results"].items():
                if qid in qids and not o.get("error") and o.get("sql"):
                    items[f"{level}|{i}|{qid}"] = (qid, o["sql"])
    return items


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Score every final SQL against the golden SQL (Uber's similarity).")
    ap.add_argument("--set", default="main", choices=SETS)
    ap.add_argument("--limit", type=int, default=None, help="only the first N questions")
    ap.add_argument("--budget", type=float, default=2.0)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--runs-dir", type=Path, default=RUNS_DIR)
    args = ap.parse_args(argv)

    load_env()
    model = default_model("small")
    require_api_key(model)
    questions = load_set(args.set)[: args.limit] if args.limit else load_set(args.set)
    by_qid = {str(q.qid): q for q in questions}
    items = items_to_judge(latest_runs(args.runs_dir, args.set, args.smoke), set(by_qid))
    distinct = sorted(set(items.values()))
    if not distinct:
        print("No run files with SQL to judge.")
        return 1

    p = PRICES[model]
    estimate, how = sum(((PROMPT_CHARS + len(s) + len(by_qid[q].gold_sql)) / 4 * p["input"]
                         + OUTPUT_TOKENS_PER_CALL * p["output"]) / 1_000_000 for q, s in distinct), "upper-side guess"
    measured = None if args.smoke else measured_estimate("judge", len(distinct), 1, args.runs_dir)
    if measured is not None:
        estimate, how = measured, f"measured in the smoke run, x{SMOKE_MARGIN}"
    print(f"Judge on {model}, {args.set} set: {len(items)} answers, {len(distinct)} distinct queries. "
          f"Estimated cost ${estimate:.2f}, {how} (spent so far ${spent_in_runs(args.runs_dir):.2f} of ${TOPIC_CEILING_USD:.0f})")
    stop = guard(estimate, args.budget, args.runs_dir, args.dry_run, args.yes)
    if stop is not None:
        return stop

    tracker = Tracker()

    def one(pair):
        qid, sql = pair
        q = by_qid[qid]
        try:
            text = llm_call(JUDGE_PROMPT.format(question=q.question, evidence=q.evidence or "(none)", gold=q.gold_sql,
                                                sql=sql), model=model, label="judge", tracker=tracker)
            return read_score(text)
        except Exception:  # an API failure leaves the score unreadable; it is counted, not guessed
            return None

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        scores = dict(zip(distinct, pool.map(one, distinct)))
    out = {"set": args.set, "model": model, "created": datetime.now().strftime("%Y%m%d-%H%M%S"),
           "scores": {k: scores[v] for k, v in items.items()},
           "calls": len(tracker.records), "cost_usd": sum(cost_usd(r) for r in tracker.records)}
    folder = out_dir_for(args.runs_dir, args.set, args.smoke)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"judge-{out['created']}.json"
    path.write_text(json.dumps(out, indent=1), encoding="utf-8")
    unreadable = sum(v is None for v in scores.values())
    print(f"Saved {path}. {len(distinct)} judged, {unreadable} unreadable. Spent ${out['cost_usd']:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
