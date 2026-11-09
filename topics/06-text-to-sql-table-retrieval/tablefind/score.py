"""Score saved answers against the key. API failures are left out; unreadable answers count as nothing found."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean


@dataclass
class Scores:
    n: int
    all_found: float  # share of questions with every gold table in the 7
    recall: float  # share of gold tables found, averaged over questions
    ceiling: float | None  # levels 2-3: share with every gold table in the top 20
    made_up: float | None  # levels 2-3: share of answers naming a table not shown
    errors: int
    failed: int


def _scored(answers: dict[str, dict], key: dict[str, set[str]]) -> list[tuple[dict, set[str]]]:
    return [(a, key[q]) for q, a in answers.items() if a["status"] != "failed"]


def score(answers: dict[str, dict], key: dict[str, set[str]]) -> Scores:
    rows = _scored(answers, key)
    failed = len(answers) - len(rows)
    if not rows:
        return Scores(0, 0.0, 0.0, None, None, 0, failed)
    shortlisted = [(a, g) for a, g in rows if a.get("top20") is not None]
    return Scores(
        n=len(rows),
        all_found=mean(g <= set(a["picks"]) for a, g in rows),
        recall=mean(len(g & set(a["picks"])) / len(g) for a, g in rows),
        ceiling=mean(g <= set(a["top20"]) for a, g in shortlisted) if shortlisted else None,
        made_up=mean(bool(a["made_up"]) for a, _ in shortlisted) if shortlisted else None,
        errors=sum(a["status"] == "error" for a, _ in rows),
        failed=failed,
    )


def by_gold_size(answers: dict[str, dict], key: dict[str, set[str]]) -> dict[str, float]:
    buckets: dict[str, list[bool]] = {}
    for a, g in _scored(answers, key):
        b = str(len(g)) if len(g) < 3 else "3+"
        buckets.setdefault(b, []).append(g <= set(a["picks"]))
    return {b: mean(v) for b, v in sorted(buckets.items())}
