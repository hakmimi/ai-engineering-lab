"""The review levels. Level 0: rules only. Level 1: one prompt. Level 2: the article's way."""

from __future__ import annotations

from dataclasses import dataclass

from agentreview.models import Session, Verdict, band_for
from agentreview.prompts import SYSTEM, parse_verdict, review_prompt
from agentreview.rules import check, score_hits
from shared.llm import Tracker, llm_call

MAX_TOKENS = 2000


@dataclass
class Ctx:
    grants: dict
    model: str
    tracker: Tracker


def run_level0(session: Session, ctx: Ctx) -> Verdict:
    hits = check(session, ctx.grants[session.suite])
    score = score_hits(hits)
    return Verdict(score, band_for(score), [], "ok", [f"{h.rule}@{h.event}" for h in hits])


def _review(session: Session, ctx: Ctx, label: str, hints=None) -> Verdict:
    text = llm_call(
        review_prompt(session, ctx.grants[session.suite], hints),
        cached_system=SYSTEM,
        model=ctx.model,
        label=label,
        tracker=ctx.tracker,
        max_tokens=MAX_TOKENS,
    )
    return parse_verdict(text)


def run_level1(session: Session, ctx: Ctx) -> Verdict:
    return _review(session, ctx, f"l1:{session.sid}")
