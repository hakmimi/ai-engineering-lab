"""Run files and money guards, shared by every topic's runner and report.

A run file is runs/<set>/level-<L>-<stamp>.json with at least: level, set, created, limit, partial, cost_usd.
`limit` set = a smoke run; `partial` = stopped by the budget. Reports use only full runs (latest_run).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

DEFAULT_CEILING_USD = 5.0  # per topic, across all runs; raise it only on purpose


def spent_so_far(runs_dir: Path) -> float:
    """Total cost_usd over every run file under runs_dir. Unreadable files count as 0."""
    total = 0.0
    if not runs_dir.exists():
        return total
    for path in runs_dir.rglob("*.json"):
        try:
            total += float(json.loads(path.read_text(encoding="utf-8")).get("cost_usd", 0))
        except (ValueError, AttributeError):
            continue
    return total


def over_ceiling(spent: float, estimate: float, ceiling: float = DEFAULT_CEILING_USD) -> bool:
    return spent + estimate > ceiling


def save_run(runs_dir: Path, set_name: str, level: str, run: dict, stamp: str | None = None) -> Path:
    stamp = stamp or datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = runs_dir / set_name
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"level-{level}-{stamp}.json"
    payload = {"level": level, "set": set_name, "created": stamp, **run}
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
    return path


def latest_run(runs_dir: Path, set_name: str, level: str) -> dict | None:
    """The newest full run (no limit, not partial) for this set and level, or None."""
    for path in sorted((runs_dir / set_name).glob(f"level-{level}-*.json"), reverse=True):
        run = json.loads(path.read_text(encoding="utf-8"))
        if run.get("limit") is None and not run.get("partial"):
            return run
    return None
