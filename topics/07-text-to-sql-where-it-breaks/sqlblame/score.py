"""Score one repeat of one level: execution accuracy, Uber's cheap signals, and (level C) how the table agent did.

An API failure ("error" set) is left out of every rate and counted in api_errors.
"""

from __future__ import annotations

from sqlloop.models import DIFFICULTIES


def _rate(num: float, den: int):
    return num / den if den else None


def score(outcomes: dict, difficulty: dict, gold: dict, db_of: dict) -> dict:
    ok = {k: o for k, o in outcomes.items() if not o.get("error")}
    n = len(ok)
    by_diff = {}
    for d in DIFFICULTIES:
        ks = [k for k in ok if difficulty.get(k) == d]
        by_diff[d] = _rate(sum(ok[k]["right"] for k in ks), len(ks))
    s = {
        "n": n,
        "api_errors": len(outcomes) - n,
        "right": _rate(sum(o["right"] for o in ok.values()), n),
        "by_difficulty": by_diff,
        "runs": _rate(sum(not o.get("final_error") for o in ok.values()), n),
        "has_output": _rate(sum(bool(o.get("n_rows")) for o in ok.values()), n),
        "final_errors": sum(1 for o in ok.values() if o.get("final_error")),
    }
    agent = {k: o for k, o in ok.items() if o.get("picked") is not None}
    keys = ("overlap", "all_found", "exact", "extra", "wrong_db", "made_up", "agent_empty", "right_all_found",
            "right_missing")
    if not agent:
        return s | dict.fromkeys(keys)
    overlap, all_found, exact, extra, wrong_db = [], [], [], [], []
    for k, o in agent.items():
        g = set(gold[k])
        own = {t for d, t in o["picked"] if d == db_of[k]}
        others = [p for p in o["picked"] if p[0] != db_of[k]]
        overlap.append(len(g & own) / len(g))
        all_found.append(g <= own)
        exact.append(own == g and not others)
        extra.append(len(own - g) + len(others))
        wrong_db.append(bool(others))
    found = [o["right"] for o, f in zip(agent.values(), all_found) if f]
    missing = [o["right"] for o, f in zip(agent.values(), all_found) if not f]
    m = len(agent)
    return s | {
        "overlap": sum(overlap) / m,
        "all_found": sum(all_found) / m,
        "exact": sum(exact) / m,
        "extra": sum(extra) / m,
        "wrong_db": sum(wrong_db) / m,
        "made_up": sum(len(o.get("made_up") or []) for o in agent.values()),
        "agent_empty": sum(1 for o in agent.values() if o.get("agent_empty")),
        "right_all_found": _rate(sum(found), len(found)),
        "right_missing": _rate(sum(missing), len(missing)),
    }
