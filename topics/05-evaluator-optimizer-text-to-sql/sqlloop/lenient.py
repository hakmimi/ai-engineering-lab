"""Re-check the final SQL of the latest runs with the lenient rule (extra or reordered columns forgiven).

    python -m sqlloop.lenient      # writes runs/lenient.json, which report.py adds as a column

BIRD's rule stays the main score. This only shows how many "wrong" answers were the right rows in another shape.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from sqlloop.data import db_path, load_set
from sqlloop.execute import lenient_same, run_sql
from sqlloop.levels import RUN_TIMEOUT_S
from sqlloop.report import _latest
from sqlloop.run import GOLD_TIMEOUT_S, RUNS_DIR

OUT = RUNS_DIR / "lenient.json"


def check_run(run: dict, questions: dict) -> list[float]:
    """Share of lenient-right answers per repeat (API errors left out, like the main score)."""
    gold, pred_cache, shares = {}, {}, []
    for rep in run["repeats"]:
        ok = right = 0
        for qid, o in rep["results"].items():
            if o.get("error"):
                continue
            ok += 1
            if o["right"]:
                right += 1
                continue
            q = questions[qid]
            db = db_path(q.db_id)
            if qid not in gold:
                gold[qid] = run_sql(db, q.gold_sql, timeout_s=GOLD_TIMEOUT_S).rows
            key = (q.db_id, o["final_sql"])
            if key not in pred_cache:
                pred_cache[key] = run_sql(db, o["final_sql"], timeout_s=RUN_TIMEOUT_S).rows
            if pred_cache[key] is not None and gold[qid] is not None and lenient_same(pred_cache[key], gold[qid]):
                right += 1
        shares.append(right / ok if ok else 0.0)
    return shares


def main() -> int:
    out = {}
    for name, sub in (("main", RUNS_DIR), ("test", RUNS_DIR / "test")):
        qs = {str(q.qid): q for q in load_set(name)}
        for level, run in _latest(sub).items():
            out[f"{name}/{level}/{run['created']}"] = check_run(run, qs)
            print(name, level, [f"{s:.0%}" for s in out[f"{name}/{level}/{run['created']}"]])
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
