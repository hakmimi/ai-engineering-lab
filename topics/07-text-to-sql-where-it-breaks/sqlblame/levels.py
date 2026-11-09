"""Levels A, B and C: the same writer prompt as topic 05's level 0; only the tables it is shown change.

A  every table of the question's own database           (BIRD's usual setup)
B  only the tables the gold SQL reads                    (Uber's "decoupled" flow)
C  a table agent picks from all 75 tables, then write    (Uber's "vanilla" flow)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from shared.llm import Tracker, llm_call
from sqlblame.agent import pick_tables
from sqlblame.warehouse import render_tables
from sqlloop.data import db_path
from sqlloop.prompts import SCHEMA_INTRO, read_sql, render_generate
from sqlloop.schema import render_schema

LEVELS = ("A", "B", "C")


@dataclass
class Ctx:
    model: str
    tracker: Tracker = field(default_factory=Tracker)
    llm: Callable[..., str] = llm_call


def solve(q, level: str, ctx: Ctx, gold: list[str], cards, path_of=None) -> dict:
    """One question at one level. Raises if a model call fails (the runner records it as an API error)."""
    path_of = path_of or db_path
    picked = made_up = None
    agent_empty = False
    if level == "A":
        given = [[c.db_id, c.table] for c in cards if c.db_id == q.db_id]
        schema = render_schema(path_of(q.db_id))
    elif level == "B":
        given = [[q.db_id, t] for t in gold]
        schema = render_tables([(q.db_id, t) for t in gold], path_of=path_of)
    elif level == "C":
        agent = pick_tables(q, ctx, cards)
        picked, made_up = agent["picked"], agent["made_up"]
        given, agent_empty = picked, not picked
        schema = render_tables([tuple(p) for p in picked], path_of=path_of)
    else:
        raise ValueError(f"unknown level {level!r}")
    text = ctx.llm(render_generate(q.question, q.evidence, []), cached_system=SCHEMA_INTRO + schema, model=ctx.model,
                   label="write", tracker=ctx.tracker)
    return {"sql": read_sql(text), "given_tables": given, "picked": picked, "made_up": made_up,
            "agent_empty": agent_empty}
