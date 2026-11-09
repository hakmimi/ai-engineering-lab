"""Uber's cheap per-question signals, checked against the real answer.

runs        the query executed without an error
has_output  it returned more than 0 rows
similarity  an LLM's 0-1 score of how close it is to the golden SQL; "good" means score >= threshold
"""

from __future__ import annotations

THRESHOLDS = tuple(round(i / 10, 1) for i in range(1, 10))


def pick_threshold(pairs: list[tuple[float | None, bool]]) -> float:
    """The threshold whose good/not-good call agrees with `right` most often. Ties go to the higher threshold."""
    scored = [(s, r) for s, r in pairs if s is not None]
    best, best_agree = THRESHOLDS[0], -1
    for t in THRESHOLDS:
        agree = sum((s >= t) == r for s, r in scored)
        if agree >= best_agree:
            best, best_agree = t, agree
    return best


def _rates(rows: list[dict], good) -> dict:
    wrong = [r for r in rows if not r["right"]]
    right = [r for r in rows if r["right"]]
    return {"good_when_wrong": sum(map(good, wrong)) / len(wrong) if wrong else None,
            "good_when_right": sum(map(good, right)) / len(right) if right else None}


def signal_rates(rows: list[dict], threshold: float) -> dict:
    judged = [r for r in rows if r["similarity"] is not None]
    return {
        "runs": _rates(rows, lambda r: bool(r["runs"])),
        "has_output": _rates(rows, lambda r: bool(r["has_output"])),
        "similarity": _rates(judged, lambda r: r["similarity"] >= threshold),
        "judge_unreadable": len(rows) - len(judged),
    }
