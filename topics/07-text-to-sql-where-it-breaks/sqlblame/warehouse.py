"""The 'warehouse': every table of every BIRD Mini-Dev database in one list.

Two views of a table:
- a card for the table agent: `database.table: col TYPE, ...` (no sample rows)
- the writer's schema block: CREATE TABLE + a few example rows, in exactly topic 05's format
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from sqlloop.data import RAW_DIR, db_path
from sqlloop.schema import _cell

ALL_DBS: tuple[str, ...] = tuple(sorted(p.name for p in (RAW_DIR / "dev_databases").iterdir() if p.is_dir())) \
    if (RAW_DIR / "dev_databases").exists() else ()


@dataclass(frozen=True)
class Card:
    db_id: str
    table: str
    columns: tuple[tuple[str, str], ...]

    @property
    def name(self) -> str:
        return f"{self.db_id}.{self.table}"


def _connect(path: Path | str) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{Path(path).as_posix()}?mode=ro", uri=True)


def _tables(con: sqlite3.Connection) -> list[tuple[str, str]]:
    return con.execute(
        "SELECT name, sql FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY rowid"
    ).fetchall()


def load_warehouse(db_ids: list[str], path_of: Callable[[str], Path] = db_path) -> list[Card]:
    cards = []
    for db_id in sorted(db_ids):
        con = _connect(path_of(db_id))
        try:
            for name, _ in _tables(con):
                cols = tuple((r[1], r[2]) for r in con.execute(f'PRAGMA table_info("{name}")'))
                cards.append(Card(db_id, name, cols))
        finally:
            con.close()
    return cards


def render_cards(cards: list[Card]) -> str:
    return "\n".join(f"{c.name}: " + ", ".join(f"{n} {t}".strip() for n, t in c.columns) for c in cards)


def _block(con: sqlite3.Connection, name: str, create: str, sample_rows: int, max_cell: int) -> str:
    # Same text as sqlloop.schema._render builds for one table (a test pins the two together).
    cur = con.execute(f'SELECT * FROM "{name}" LIMIT {sample_rows}')
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    lines = [create.strip() + ";"]
    if rows:
        lines.append(f"/* {len(rows)} example rows from {name}:")
        lines.append(" | ".join(cols))
        lines += [" | ".join(_cell(v, max_cell) for v in r) for r in rows]
        lines.append("*/")
    return "\n".join(lines)


def render_tables(picks: list[tuple[str, str]], path_of: Callable[[str], Path] = db_path,
                  sample_rows: int = 3, max_cell: int = 60) -> str:
    parts = []
    for db_id, table in picks:
        con = _connect(path_of(db_id))
        try:
            create = dict(_tables(con))[table]
            parts.append(_block(con, table, create, sample_rows, max_cell))
        finally:
            con.close()
    return "\n\n".join(parts)
