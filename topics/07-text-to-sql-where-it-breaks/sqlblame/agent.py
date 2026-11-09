"""The table agent (Uber's 'Table Agent'): reads a card for every table in the warehouse and names the ones it needs."""

from __future__ import annotations

import re

from shared.llm import extract_xml
from sqlblame.warehouse import Card, render_cards
from sqlloop.models import Question

AGENT_INTRO = """\
You help write SQL against a data warehouse. These are all its tables, as database.table with their columns:

"""

AGENT_PROMPT = """\
Which tables are needed to write one SQLite query that answers this question? Name every table the query will read,
and only those. All tables of one query must come from the same database.

Hint from the person asking: {evidence}
Question: {question}

Think it through in <thoughts></thoughts>, then list the tables as database.table, separated by commas, in <tables></tables>.
"""

_QUOTES = "`\"'[]*"


def _lookup(cards: list[Card]):
    full = {c.name.lower(): c for c in cards}
    bare: dict[str, list[Card]] = {}
    for c in cards:
        bare.setdefault(c.table.lower(), []).append(c)
    return full, {k: v[0] for k, v in bare.items() if len(v) == 1}


def read_tables(text: str, cards: list[Card]) -> tuple[list[tuple[str, str]], list[str]]:
    """(picked (db_id, table) in answer order, made-up names). Without a <tables> tag, only known names are taken."""
    tagged = extract_xml(text, "tables")
    body = tagged if tagged else text
    full, bare = _lookup(cards)
    picked: list[tuple[str, str]] = []
    made_up: list[str] = []
    for raw in re.split(r"[,\n]", body):
        token = raw.strip().strip(_QUOTES).strip()
        token = ".".join(part.strip(_QUOTES) for part in token.split("."))
        if not token:
            continue
        card = full.get(token.lower()) or (bare.get(token.lower()) if "." not in token else None)
        if card is None:
            if tagged:
                made_up.append(token)
            continue
        if (card.db_id, card.table) not in picked:
            picked.append((card.db_id, card.table))
    return picked, made_up


def pick_tables(q: Question, ctx, cards: list[Card]) -> dict:
    prompt = AGENT_PROMPT.format(question=q.question, evidence=q.evidence or "(none)")
    text = ctx.llm(prompt, cached_system=AGENT_INTRO + render_cards(cards), model=ctx.model, label="agent",
                   tracker=ctx.tracker)
    picked, made_up = read_tables(text, cards)
    return {"picked": [list(p) for p in picked], "made_up": made_up, "raw": text}
