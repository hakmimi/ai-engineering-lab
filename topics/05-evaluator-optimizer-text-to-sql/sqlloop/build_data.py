"""One-off: draw the main and held-out sets from BIRD Mini-Dev (SQLite).

    python -m sqlloop.build_data            # reads data/raw/, writes data/main.json, test.json, build_log.json

Databases are split 6 / 5 with a fixed seed; each set is drawn by difficulty from its own databases.
A gold query that errors or runs past 30 s is skipped and the next one is taken (logged).
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path
from typing import Callable

from sqlloop import data
from sqlloop.execute import run_sql

SEED = 2026
COUNTS = {"simple": 18, "moderate": 30, "challenging": 12}
GOLD_TIMEOUT_S = 30.0


def split_dbs(db_ids: list[str], seed: int = SEED) -> tuple[list[str], list[str]]:
    ids = sorted(set(db_ids))
    random.Random(seed).shuffle(ids)
    return sorted(ids[:6]), sorted(ids[6:])


def gold_check(db: Path, sql: str) -> tuple[bool, str]:
    r = run_sql(db, sql, timeout_s=GOLD_TIMEOUT_S)
    return (r.rows is not None, r.error)


def draw(items: list[dict], dbs: list[str], counts: dict[str, int], seed: int,
         gold_ok: Callable[[dict], tuple[bool, str]]) -> tuple[list[dict], list[dict]]:
    rng = random.Random(seed)
    picked, log = [], []
    for diff, n in counts.items():
        pool = sorted((it for it in items if it["db_id"] in dbs and it["difficulty"] == diff), key=lambda it: it["question_id"])
        rng.shuffle(pool)
        took = 0
        for it in pool:
            if took == n:
                break
            ok, why = gold_ok(it)
            if ok:
                picked.append(it)
                took += 1
            else:
                log.append({"question_id": it["question_id"], "db_id": it["db_id"], "reason": why})
        if took < n:
            raise ValueError(f"only {took} usable {diff} questions, need {n}")
    return sorted(picked, key=lambda it: it["question_id"]), log


def _as_question(it: dict) -> dict:
    return {"qid": it["question_id"], "db_id": it["db_id"], "question": it["question"], "evidence": it.get("evidence", ""),
            "gold_sql": it["SQL"], "difficulty": it["difficulty"]}


def main(argv: list[str] | None = None) -> int:
    raw = Path(argv[0]) if argv else data.RAW_DIR
    items = json.loads((raw / "mini_dev_sqlite.json").read_text(encoding="utf-8"))
    a, b = split_dbs([it["db_id"] for it in items])
    check = lambda it: gold_check(raw / "dev_databases" / it["db_id"] / f"{it['db_id']}.sqlite", it["SQL"])
    log = {"seed": SEED, "group_a_main": a, "group_b_test": b, "skipped": {}}
    for name, dbs, seed in (("main", a, SEED), ("test", b, SEED + 1)):
        picked, skipped = draw(items, dbs, COUNTS, seed, check)
        log["skipped"][name] = skipped
        (data.DATA_DIR / f"{name}.json").write_text(json.dumps([_as_question(it) for it in picked], indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"{name}: {len(picked)} questions from {', '.join(dbs)}; skipped {len(skipped)}")
    (data.DATA_DIR / "build_log.json").write_text(json.dumps(log, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
