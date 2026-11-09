"""Run SQL on a BIRD SQLite database, read-only and with a timeout, and compare results."""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ExecResult:
    rows: list[tuple] | None  # None when the query failed
    error: str = ""  # "" when it ran; "timeout after N s" or the SQLite message otherwise
    n_rows: int = 0  # full row count, even when rows were cut to max_rows


def run_sql(db: Path | str, sql: str, timeout_s: float = 10.0, max_rows: int | None = None) -> ExecResult:
    """Execute one statement on a read-only connection. Never raises for SQL problems."""
    if not sql.strip():
        return ExecResult(None, "no SQL found in the answer")
    con = sqlite3.connect(f"file:{Path(db).as_posix()}?mode=ro", uri=True, check_same_thread=False)
    deadline = time.monotonic() + timeout_s
    con.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10_000)
    try:
        rows = con.execute(sql).fetchall()
    except sqlite3.OperationalError as exc:
        if str(exc) == "interrupted":
            return ExecResult(None, f"timeout after {timeout_s:g} s")
        return ExecResult(None, str(exc))
    except (sqlite3.Error, sqlite3.Warning, ValueError) as exc:
        return ExecResult(None, str(exc))
    finally:
        con.close()
    n = len(rows)
    return ExecResult(rows[:max_rows] if max_rows is not None else rows, "", n)


def _norm(v):
    if isinstance(v, (bytes, bytearray, memoryview)):
        return "x'" + bytes(v).hex() + "'"
    return v


def normalize_rows(rows) -> list[tuple]:
    """Rows as hashable tuples; BLOBs become hex text so results can be stored as JSON."""
    return [tuple(_norm(v) for v in row) for row in rows]


def same_result(pred, gold) -> bool:
    """BIRD's execution-accuracy rule: same set of rows, order and duplicates ignored."""
    return set(normalize_rows(pred)) == set(normalize_rows(gold))


def lenient_same(pred, gold, max_cols: int = 8) -> bool:
    """A looser check, reported next to BIRD's rule: right if some choice and order of the predicted
    columns gives exactly the gold rows. Extra or reordered columns are forgiven; missing ones are not."""
    from itertools import permutations

    p, g = normalize_rows(pred), set(normalize_rows(gold))
    if not g or not p:
        return set(p) == g
    k, n = len(next(iter(g))), len(p[0])
    if k > n or n > max_cols:
        return same_result(pred, gold)
    return any({tuple(r[i] for i in idx) for r in p} == g for idx in permutations(range(n), k))
