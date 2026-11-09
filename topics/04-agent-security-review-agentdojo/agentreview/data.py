"""Load topic 4's committed sets. Review code uses load_sessions and load_grants only; key loaders are for scoring."""

from __future__ import annotations

import json
from pathlib import Path

from agentreview.models import Event, Session

DATA = Path(__file__).resolve().parent.parent / "data"
SETS = ("main", "test", "fooled")


def _read(name: str) -> dict:
    return json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))


def load_sessions(set_name: str) -> list[Session]:
    return [
        Session(s["sid"], s["suite"], [Event(**e) for e in s["events"]])
        for s in _read(set_name)["sessions"]
    ]


def load_key(set_name: str) -> dict[str, str]:
    """sid -> kind (bad | refused | clean) for one set."""
    return {sid: k["kind"] for sid, k in _read("key")["sessions"].items() if k["set"] == set_name}


def load_pairs() -> dict[str, str]:
    """fooled sid -> the test-set sid it was copied from."""
    return {sid: k["plain_sid"] for sid, k in _read("key")["sessions"].items() if k["set"] == "fooled"}


def load_grants() -> dict[str, dict]:
    return _read("grants")
