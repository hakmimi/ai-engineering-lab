r"""Level 5 (Pinterest's way): an LLM writes a summary of every table once; search and re-rank then use the summaries.

The prompt is Pinterest's own (Querybook, querybook/server/lib/ai_assistant/prompts/table_summary_prompt.py),
word for word. Pinterest also gives sample queries; we have no query logs, so that section says "(none available)".
The schema we give is level 3's description card, so level 5 has the same information as level 3, rewritten.

    $env:PYTHONPATH = "../..;."
    python -m tablefind.summarize --dry-run
    python -m tablefind.summarize --limit 10 --yes      # smoke run
    python -m tablefind.summarize --yes                 # all 971, then writes data/summaries.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from shared.llm import PRICES, Tracker, cost_usd, llm_call, load_env, require_api_key
from shared.runs import over_ceiling, save_run, spent_so_far
from tablefind.cards import card
from tablefind.data import DATA, Table, load_tables

TOPIC = Path(__file__).resolve().parent.parent
CACHE_DIR = TOPIC / "cache"
RUNS_DIR = TOPIC / "runs"
MAX_TOKENS = 2000

SUMMARY_PROMPT = """
You are a data analyst that can help summarize SQL tables.

Summarize below table by the given context.

===Table Schema
{table_schema}

===Sample Queries
{sample_queries}

===Response guideline
 - You shall write the summary based only on provided information.
 - Note that above sampled queries are only small sample of queries and thus not all possible use of tables are represented, and only some columns in the table are used.
 - Do not use any adjective to describe the table. For example, the importance of the table, its comprehensiveness or if it is crucial, or who may be using it. For example, you can say that a table contains certain types of data, but you cannot say that the table contains a 'wealth' of data, or that it is 'comprehensive'.
 - Do not mention about the sampled query. Only talk objectively about the type of data the table contains and its possible utilities.
 - Please also include some potential usecases of the table, e.g. what kind of questions can be answered by the table, what kind of analysis can be done by the table, etc.
"""


def summary_prompt(t: Table) -> str:
    return SUMMARY_PROMPT.format(table_schema=card(t, with_desc=True), sample_queries="(none available)")


def _key(model: str, prompt: str) -> str:
    return hashlib.sha256(f"{model}\n{prompt}".encode("utf-8")).hexdigest()


def summarize_all(tables: list[Table], model: str, cache_dir: Path, budget: float, workers: int = 8,
                  llm=None) -> tuple[dict[str, str], float]:
    """Summaries by table id (cache first), and the money spent on cache misses. Failed calls are left out."""
    llm = llm or llm_call
    path = cache_dir / f"summaries-{model}.jsonl"
    cache: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                cache[row["k"]] = row["s"]
    lock, spent, out = threading.Lock(), [0.0], {}

    def one(t: Table) -> None:
        prompt = summary_prompt(t)
        k = _key(model, prompt)
        if k in cache:
            out[t.id] = cache[k]
            return
        with lock:
            if spent[0] >= budget:
                return
        tracker = Tracker()
        try:
            text = llm(prompt, label=f"sum:{t.id}", model=model, tracker=tracker, max_tokens=MAX_TOKENS).strip()
        except Exception:  # an outage: leave it out, a later run fills it in
            text = ""
        with lock:
            spent[0] += sum(cost_usd(r) for r in tracker.records)
            if text:
                out[t.id] = text
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps({"k": k, "id": t.id, "s": text}, ensure_ascii=False) + "\n")

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(one, tables))
    return {t.id: out[t.id] for t in tables if t.id in out}, spent[0]


def estimate_cost_usd(tables: list[Table], model: str) -> float:
    """Upper side: characters ÷ 4 in, output at the max_tokens cap."""
    p = PRICES[model]
    return sum((len(summary_prompt(t)) / 4 * p["input"] + MAX_TOKENS * p["output"]) / 1_000_000 for t in tables)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Write an LLM summary of every table (level 5).")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--budget", type=float, default=1.5)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    load_env()
    from tablefind.run import TOPIC_CEILING_USD, rerank_model  # same model as the re-ranker
    model = rerank_model()
    tables = load_tables()[: a.limit] if a.limit else load_tables()
    estimate, spent = estimate_cost_usd(tables, model), spent_so_far(RUNS_DIR)
    print(f"Summaries for {len(tables)} tables on {model}. Estimated cost ${estimate:.3f} (upper side; spent so far ${spent:.3f})")
    if a.dry_run:
        return 0
    if over_ceiling(spent, min(estimate, a.budget), TOPIC_CEILING_USD):
        print("That would pass the topic ceiling. Not running.")
        return 2
    require_api_key(model)
    if not a.yes and input("Run? [y/N] ").strip().lower() != "y":
        return 1
    summaries, cost = summarize_all(tables, model, CACHE_DIR, a.budget, a.workers)
    save_run(RUNS_DIR, "summaries", "s", {"model": model, "limit": a.limit, "partial": len(summaries) < len(tables),
                                         "n": len(tables), "done": len(summaries), "cost_usd": cost})
    print(f"{len(summaries)} of {len(tables)} summaries. Spent ${cost:.4f}")
    if not a.limit and len(summaries) == len(tables):
        (DATA / "summaries.json").write_text(json.dumps(summaries, indent=1, ensure_ascii=False), encoding="utf-8")
        print("Wrote data/summaries.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
