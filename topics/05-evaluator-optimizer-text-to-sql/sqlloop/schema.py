"""What the model sees about a database: CREATE TABLE text plus a few sample rows per table."""

from __future__ import annotations

import sqlite3
from functools import lru_cache
from pathlib import Path


def _cell(v, max_cell: int) -> str:
    text = "NULL" if v is None else ("<blob>" if isinstance(v, (bytes, bytearray)) else str(v))
    return text if len(text) <= max_cell else text[:max_cell] + "..."


@lru_cache(maxsize=None)
def _render(db: str, sample_rows: int, max_cell: int) -> str:
    con = sqlite3.connect(f"file:{Path(db).as_posix()}?mode=ro", uri=True)
    try:
        tables = con.execute(
            "SELECT name, sql FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY rowid"
        ).fetchall()
        parts = []
        for name, create in tables:
            cur = con.execute(f'SELECT * FROM "{name}" LIMIT {sample_rows}')
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
            lines = [create.strip() + ";"]
            if rows:
                lines.append(f"/* {len(rows)} example rows from {name}:")
                lines.append(" | ".join(cols))
                lines += [" | ".join(_cell(v, max_cell) for v in r) for r in rows]
                lines.append("*/")
            parts.append("\n".join(lines))
        return "\n\n".join(parts)
    finally:
        con.close()


def render_schema(db_path: Path | str, sample_rows: int = 3, max_cell: int = 60) -> str:
    return _render(str(db_path), sample_rows, max_cell)
