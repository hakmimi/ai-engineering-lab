"""Score a run: right answers per repeat, and whether the 3 repeats gave the same answer.

An API failure ("error" set) is left out of every rate and counted in api_errors; in the same-answer rates,
a question with an API error in any repeat is left out.
"""

from __future__ import annotations

import hashlib
import statistics

from sqlloop.execute import normalize_rows


def _rate(num: float, den: int):
    return num / den if den else None


def _mean(vals: list):
    return sum(vals) / len(vals) if vals else None


def rows_hash(rows) -> str:
    """Order and duplicates ignored, as BIRD's rule."""
    text = repr(sorted(set(normalize_rows(rows)), key=repr))
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def outcome_key(o: dict) -> str:
    if not o.get("db") or not o.get("sql"):
        return "no answer"
    if o.get("final_error"):
        return "sql error"
    return f"{o['db']}:{o['rows_hash']}"


def score_repeat(results: dict, db_of: dict) -> dict:
    ok = {k: o for k, o in results.items() if not o.get("error")}
    n = len(ok)
    vals = list(ok.values())
    rest = [o for o in vals if not o.get("handoff")]
    extra = lambda key: _mean([o[key] for o in vals if o.get(key) is not None])
    return {
        "n": n,
        "api_errors": len(results) - n,
        "right": _rate(sum(o["right"] for o in vals), n),
        "right_db": _rate(sum(o.get("db") == db_of[k] for k, o in ok.items() if not o.get("handoff")), len(rest)),
        "no_answer": _rate(sum(outcome_key(o) == "no answer" for o in vals), n),
        "sql_errors": _rate(sum(outcome_key(o) == "sql error" for o in vals), n),
        "cost": _mean([o["cost_usd"] for o in vals]),
        "seconds": _mean([o["seconds"] for o in vals]),
        "seconds_median": statistics.median([o["seconds"] for o in vals]) if vals else None,
        "calls": _mean([len(o["calls"]) for o in vals]),
        "handoff": _rate(sum(bool(o.get("handoff")) for o in vals), n),
        "right_rest": _rate(sum(o["right"] for o in rest), len(rest)),
        "agree": extra("agree"),
        "n_sub": extra("n_sub"),
        "rounds": extra("rounds"),
        "steps": extra("steps"),
        "cap": _rate(sum(o.get("stop") == "cap" for o in vals), n),
    }


def consistency(repeats: list[dict]) -> dict:
    """Over questions with no API error in any repeat: share with the same outcome every time, and right every time."""
    if len(repeats) < 2:
        return {"n": 0, "same": None, "right_all": None}
    qids = [k for k in repeats[0] if all(k in r and not r[k].get("error") for r in repeats)]
    same = sum(len({outcome_key(r[k]) for r in repeats}) == 1 for k in qids)
    right_all = sum(all(r[k]["right"] for r in repeats) for k in qids)
    return {"n": len(qids), "same": _rate(same, len(qids)), "right_all": _rate(right_all, len(qids))}
