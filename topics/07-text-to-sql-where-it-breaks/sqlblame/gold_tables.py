"""Which tables each gold query reads, found by SQLite itself (an authorizer callback), not by parsing SQL.

    python -m sqlblame.gold_tables      writes data/gold_tables.json and data/NOTICE.md
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

from sqlblame.paths import DATA_DIR
from sqlloop.data import SETS, db_path, load_set

GOLD_PATH = DATA_DIR / "gold_tables.json"

NOTICE = """\
# Data notice

`gold_tables.json` lists, for each question of topic 05's main and held-out sets, the tables its gold SQL reads.
It is derived from **BIRD Mini-Dev** (https://github.com/bird-bench/mini_dev), licensed **CC BY-SA 4.0**, so this
file is CC BY-SA 4.0 too. The lists were made by preparing each gold query in SQLite with an authorizer callback
(`SQLITE_READ` events); no SQL is stored here. Built by `python -m sqlblame.gold_tables`.
"""


def tables_read(db: Path | str, sql: str) -> list[str]:
    """The tables `sql` reads, in sqlite_master spelling, sorted, each once. The query is prepared, never run."""
    con = sqlite3.connect(f"file:{Path(db).as_posix()}?mode=ro", uri=True)
    try:
        names = {n.lower(): n for (n,) in con.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")}
        seen: set[str] = set()

        def auth(action, arg1, arg2, db_name, source):
            if action == sqlite3.SQLITE_READ and arg1:
                seen.add(arg1.lower())
            return sqlite3.SQLITE_OK

        con.set_authorizer(auth)
        con.execute("EXPLAIN " + sql).fetchall()  # EXPLAIN compiles the statement without running it
        return sorted(names[n] for n in seen if n in names)
    finally:
        con.close()


def build(set_names=SETS) -> dict[str, list[str]]:
    return {str(q.qid): tables_read(db_path(q.db_id), q.gold_sql) for s in set_names for q in load_set(s)}


def load_gold() -> dict[str, list[str]]:
    return json.loads(GOLD_PATH.read_text(encoding="utf-8"))


def main() -> int:
    gold = build()
    GOLD_PATH.write_text(json.dumps(gold, indent=1), encoding="utf-8")
    (DATA_DIR / "NOTICE.md").write_text(NOTICE, encoding="utf-8")
    print(f"Wrote {len(gold)} questions to {GOLD_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
