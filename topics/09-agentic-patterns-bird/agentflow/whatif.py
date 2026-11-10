"""What if the free agent's `database.table` names had worked? An offline check, no model calls.

The agent sees the tables as `database.table` cards. Some of its final queries kept that prefix
(`FROM superhero.superhero`), which SQLite rejects ("no such table"). Here those stored queries are run again with
the database also attached under its own name, so the prefix resolves. Nothing else changes, and the reported
level-5 numbers stay as they are: this is a labelled what-if next to them.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Callable

from agentflow.score import consistency, rows_hash
from sqlloop.execute import ExecResult, same_result

TIMEOUT_S = 10.0


def run_with_db_name(db: Path | str, name: str, sql: str, timeout_s: float = TIMEOUT_S) -> ExecResult:
    """Like topic 05's run_sql (read-only, timeout), with the same file also attached as `name`."""
    uri = f"file:{Path(db).as_posix()}?mode=ro"
    con = sqlite3.connect(uri, uri=True, check_same_thread=False)
    try:
        con.execute("ATTACH DATABASE ? AS " + '"' + name.replace('"', '""') + '"', (uri,))
        deadline = time.monotonic() + timeout_s
        con.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10_000)
        rows = con.execute(sql).fetchall()
    except sqlite3.OperationalError as exc:
        return ExecResult(None, f"timeout after {timeout_s:g} s" if str(exc) == "interrupted" else str(exc))
    except (sqlite3.Error, sqlite3.Warning, ValueError) as exc:
        return ExecResult(None, str(exc))
    finally:
        con.close()
    return ExecResult(rows, "", len(rows))


def is_prefix_failure(r: dict) -> bool:
    return bool(r.get("db")) and r.get("final_error", "").startswith(f"no such table: {r['db']}.")


def ran_before_answering(r: dict) -> bool:
    """Did the agent run this exact final query with run_sql before it answered? (Spaces at the ends ignored.)"""
    sql = r.get("sql", "").strip()
    return any(isinstance(t, dict) and t.get("tool") == "run_sql" and t.get("sql", "").strip() == sql
               for t in r.get("trace", [])[:-1])


def prefix_whatif(run: dict, gold: dict, db_of: dict, path_of: Callable) -> dict:
    """{"prefix_failures", "run_before", "fixed", "right", "same"} if the prefix had worked. run_before: failing
    queries the agent had run itself before answering. right: the share right per repeat (API errors left out, as in
    the main scores), averaged over repeats. same: as agentflow.score.consistency."""
    failures = fixed = run_before = 0
    rates, repeats = [], []
    for rep in run["repeats"]:
        results = {}
        for qid, r in rep["results"].items():
            r = dict(r)
            if not r.get("error") and is_prefix_failure(r):
                failures += 1
                run_before += ran_before_answering(r)
                res = run_with_db_name(path_of(r["db"]), r["db"], r["sql"])
                if res.rows is not None:
                    r.update(final_error="", rows_hash=rows_hash(res.rows),
                             right=r["db"] == db_of[qid] and same_result(res.rows, gold[qid]))
                    fixed += r["right"]
            results[qid] = r
        ok = [r for r in results.values() if not r.get("error")]
        if ok:
            rates.append(sum(bool(r.get("right")) for r in ok) / len(ok))
        repeats.append(results)
    return {"prefix_failures": failures, "run_before": run_before, "fixed": fixed, "right": sum(rates) / len(rates) if rates else None,
            "same": consistency(repeats)["same"]}
