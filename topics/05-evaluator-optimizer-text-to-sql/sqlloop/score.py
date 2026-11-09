"""Score one repeat: execution accuracy, what the loop changed, and how the grader did.

Each outcome holds the rounds (each with "right" and, at levels 1 and 3, the grader's "verdict").
An API failure ("error" set) is left out of the rates and counted separately.
"""

from __future__ import annotations

from sqlloop.models import DIFFICULTIES


def _rate(num: int, den: int):
    return num / den if den else None


def score(outcomes: dict, difficulty: dict) -> dict:
    ok = {k: o for k, o in outcomes.items() if not o.get("error")}
    n = len(ok)
    graded = [r for o in ok.values() for r in o["rounds"] if r.get("verdict") is not None]
    wrong_graded = [r for r in graded if not r["right"]]
    right_graded = [r for r in graded if r["right"]]
    final_pass = [o for o in ok.values() if o["rounds"] and o["rounds"][-1].get("verdict") == "PASS"]
    by_diff = {}
    for d in DIFFICULTIES:
        ks = [k for k in ok if difficulty.get(k) == d]
        by_diff[d] = _rate(sum(ok[k]["right"] for k in ks), len(ks))
    return {
        "n": n,
        "api_errors": len(outcomes) - n,
        "right": _rate(sum(o["right"] for o in ok.values()), n),
        "first_right": _rate(sum(o["first_right"] for o in ok.values()), n),
        "fixed": sum(1 for o in ok.values() if o["right"] and not o["first_right"]),
        "broken": sum(1 for o in ok.values() if o["first_right"] and not o["right"]),
        "pass_on_wrong": _rate(sum(r["verdict"] == "PASS" for r in wrong_graded), len(wrong_graded)),
        "false_alarm": _rate(sum(r["verdict"] != "PASS" for r in right_graded), len(right_graded)),
        "pass_right": _rate(sum(o["right"] for o in final_pass), len(final_pass)),
        "rounds": _rate(sum(len(o["rounds"]) for o in ok.values()), n),
        "cap_hit": _rate(sum(o["stop"] == "cap" for o in ok.values()), n),
        "final_errors": sum(1 for o in ok.values() if o.get("final_error")),
        "by_difficulty": by_diff,
    }
