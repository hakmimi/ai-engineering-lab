"""The review levels. Level 0: rules only. Level 1: one prompt. Level 2: the article's way."""

from __future__ import annotations

import re
from dataclasses import dataclass

from agentreview.models import Session, Verdict, band_for
from agentreview.prompts import SYSTEM, parse_verdict, review_prompt
from agentreview.rules import check, score_hits
from agentreview.transcript import event_body
from shared.llm import Tracker, llm_call

MAX_TOKENS = 2000
TRIES = 3  # the first answer plus two re-runs, as in the article


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


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def quotes_ok(verdict: Verdict, session: Session) -> bool:
    """Every finding cites an event that exists, and its quote is in that event (whitespace ignored)."""
    events = {e.n: e for e in session.events}
    for f in verdict.findings:
        e = events.get(f.event)
        if e is None or not f.quote.strip():
            return False
        quote = _flat(f.quote)
        if quote not in _flat(event_body(e)) and quote not in _flat(e.text):
            return False
    return True


def run_level2(session: Session, ctx: Ctx) -> Verdict:
    """The article's way: rule hits as hints, then code checks; a session is never cleared by a failed check."""
    hits = check(session, ctx.grants[session.suite])
    hit_names = [f"{h.rule}@{h.event}" for h in hits]
    for attempt in range(1, TRIES + 1):
        v = _review(session, ctx, f"l2:{session.sid}:try{attempt}", hits)
        if v.status == "ok" and quotes_ok(v, session):
            v.hits = hit_names
            return v
    return Verdict(score=25, band="look", findings=[], status="not_reviewed", hits=hit_names)
