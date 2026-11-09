"""The review levels. Level 0: rules only. Level 1: one prompt. Level 2: the article's way."""

from __future__ import annotations

from dataclasses import dataclass

from agentreview.models import Session, Verdict, band_for
from agentreview.rules import check, score_hits
from shared.llm import Tracker


@dataclass
class Ctx:
    grants: dict
    model: str
    tracker: Tracker


def run_level0(session: Session, ctx: Ctx) -> Verdict:
    hits = check(session, ctx.grants[session.suite])
    score = score_hits(hits)
    return Verdict(score, band_for(score), [], "ok", [f"{h.rule}@{h.event}" for h in hits])
