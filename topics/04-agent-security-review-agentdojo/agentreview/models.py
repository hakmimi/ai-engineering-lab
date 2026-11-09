"""Data shapes for topic 4: a reviewed session, its events, and a reviewer's verdict."""

from __future__ import annotations

from dataclasses import dataclass, field

BANDS = ("routine", "look", "act")
KINDS = ("bad", "refused", "clean")


def band_for(score: int) -> str:
    """The article's bands (0-19 / 25-49 / 65-100); a score in a gap goes to the higher band."""
    if score < 20:
        return "routine"
    if score < 50:
        return "look"
    return "act"


@dataclass
class Event:
    n: int
    source: str  # system | user | agent | tool_call | tool_result
    text: str
    tool: str = ""
    args: dict = field(default_factory=dict)


@dataclass
class Session:
    sid: str
    suite: str
    events: list[Event]


@dataclass
class Finding:
    event: int
    quote: str
    why: str


@dataclass
class Verdict:
    score: int
    band: str  # one of BANDS, or "error"
    findings: list[Finding] = field(default_factory=list)
    status: str = "ok"  # ok | error | not_reviewed
    hits: list[str] = field(default_factory=list)
