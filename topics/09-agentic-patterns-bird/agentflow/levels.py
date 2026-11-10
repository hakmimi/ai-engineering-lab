"""The five patterns from the guide, and a free agent, on the same question.

0   one prompt: every table of every database, the model names the database and writes the SQL
1   routing: a router names the database, a specialist writes SQL on that database only
1h  routing + handoff: the router may answer HUMAN; a stand-in human picks the right database
2   parallel vote: router, then 3 writers at once; the largest group with the same rows wins
3   orchestrator-worker: router, a planner splits the question, one worker per sub-question, a combiner
4   evaluator-optimizer: router, then topic 05's level 3 loop (writer + grader who sees the rows)
5   free agent: tools describe / run_sql / answer, at most AGENT_MAX_STEPS steps

Every SQL writer uses topic 05's prompt (render_generate) and schema text (render_schema).
A failed model call raises; the runner records it as an API error.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Callable

from agentflow.prompts import (AGENT_INTRO, AGENT_LAST, AGENT_STEP, BAD_ACTION, COMBINE, DATABASE_LINE, HANDOFF_LINE,
                               PART, PLAN, ROUTER, ROUTER_INTRO, STEP, WAREHOUSE_INTRO, read_action, read_database,
                               read_subquestions, render_action, render_db_list)
from shared.llm import Tracker, llm_call
from sqlblame.warehouse import render_cards
from sqlloop import levels as loop05
from sqlloop.data import db_path
from sqlloop.execute import ExecResult, normalize_rows, run_sql
from sqlloop.prompts import SCHEMA_INTRO, read_sql, render_generate, render_result
from sqlloop.schema import render_schema

LEVELS = ("0", "1", "1h", "2", "3", "4", "5")
N_WRITERS = 3
MAX_SUB = 4
AGENT_MAX_STEPS = 10
RUN_TIMEOUT_S = 10.0
PREVIEW_ROWS = 10
PART_ROWS = 5


@dataclass
class Ctx:
    model: str
    tracker: Tracker = field(default_factory=Tracker)
    llm: Callable[..., str] = llm_call


def _call(ctx: Ctx, prompt: str, system: str, label: str) -> str:
    return ctx.llm(prompt, cached_system=system, model=ctx.model, label=label, tracker=ctx.tracker)


def _db_ids(cards) -> list[str]:
    return sorted({c.db_id for c in cards})


def _write(q, ctx: Ctx, schema: str, label: str, question: str | None = None) -> str:
    return read_sql(_call(ctx, render_generate(question or q.question, q.evidence, []), SCHEMA_INTRO + schema, label))


def route(q, ctx: Ctx, cards, allow_human: bool = False) -> str | None:
    prompt = ROUTER.format(question=q.question, evidence=q.evidence or "(none)") + (HANDOFF_LINE if allow_human else "")
    return read_database(_call(ctx, prompt, ROUTER_INTRO + render_cards(cards), "route"), _db_ids(cards), allow_human)


def vote(results: list[ExecResult]) -> int:
    """Index of the winning query: the largest group with the same set of rows; ties go to the earliest.
    A failed query never wins unless every query failed (then the first)."""
    groups: dict[frozenset, list[int]] = {}
    for i, r in enumerate(results):
        if r.rows is not None:
            groups.setdefault(frozenset(normalize_rows(r.rows)), []).append(i)
    if not groups:
        return 0
    return max(groups.values(), key=lambda idx: (len(idx), -idx[0]))[0]


def _parallel(fns: list[Callable[[], object]]) -> list:
    with ThreadPoolExecutor(max_workers=len(fns)) as pool:
        return list(pool.map(lambda f: f(), fns))


def _run(path_of, db: str, sql: str, max_rows: int | None = None) -> ExecResult:
    return run_sql(path_of(db), sql, timeout_s=RUN_TIMEOUT_S, max_rows=max_rows)


def _one_prompt(q, ctx, cards, path_of, out):
    system = WAREHOUSE_INTRO + "\n\n".join(f"-- database: {d}\n{render_schema(path_of(d))}" for d in _db_ids(cards))
    text = _call(ctx, render_generate(q.question, q.evidence, []) + DATABASE_LINE, system, "write")
    db = read_database(text, _db_ids(cards))
    if db is None:
        return {**out, "stop": "db_unreadable"}
    return {**out, "db": db, "sql": read_sql(text), "stop": "ok"}


def _parallel_vote(q, ctx, schema, path_of, db, out):
    sqls = _parallel([lambda i=i: _write(q, ctx, schema, f"write-{i + 1}") for i in range(N_WRITERS)])
    results = [_run(path_of, db, s) for s in sqls]
    win = vote(results)
    key = lambda r: frozenset(normalize_rows(r.rows)) if r.rows is not None else None
    agree = sum(1 for r in results if r.rows is not None and key(r) == key(results[win])) or 1
    return {**out, "sql": sqls[win], "stop": "ok", "agree": agree, "candidates": sqls}


def _orchestrate(q, ctx, schema, path_of, db, out):
    plan = _call(ctx, PLAN.format(question=q.question, evidence=q.evidence or "(none)"), SCHEMA_INTRO + schema, "plan")
    subs = read_subquestions(plan, MAX_SUB)
    if len(subs) <= 1:
        sql = _write(q, ctx, schema, "worker-1")
        return {**out, "sql": sql, "stop": "ok", "n_sub": 1, "subquestions": subs}
    sqls = _parallel([lambda i=i, s=s: _write(q, ctx, schema, f"worker-{i + 1}", question=s) for i, s in enumerate(subs)])
    parts = []
    for s, sql in zip(subs, sqls):
        r = _run(path_of, db, sql, max_rows=PART_ROWS)
        parts.append(PART.format(sub=s, sql=sql, result=render_result(r.rows, r.n_rows, r.error, PART_ROWS).strip()))
    prompt = COMBINE.format(question=q.question, evidence=q.evidence or "(none)", parts="\n".join(parts))
    sql = read_sql(_call(ctx, prompt, SCHEMA_INTRO + schema, "combine"))
    return {**out, "sql": sql, "stop": "ok", "n_sub": len(subs), "subquestions": subs, "worker_sql": sqls}


def _evaluator(q, ctx, path_of, db, out):
    res = loop05.solve(q, "3", loop05.Ctx(ctx.model, None, ctx.tracker, ctx.llm), path_of(db))
    return {**out, "sql": res["final_sql"], "stop": res["stop"], "rounds": len(res["rounds"])}


def _agent(q, ctx, cards, path_of, out):
    dbs = {d.lower(): d for d in _db_ids(cards)}
    system = AGENT_INTRO.format(db_list=render_db_list(cards), max_steps=AGENT_MAX_STEPS)
    history: list[str] = []
    trace: list[dict] = []
    for n in range(1, AGENT_MAX_STEPS + 1):
        prompt = AGENT_STEP.format(question=q.question, evidence=q.evidence or "(none)",
                                   history="\n" + "\n".join(history) + "\n" if history else "", n=n,
                                   max_steps=AGENT_MAX_STEPS, last=AGENT_LAST if n == AGENT_MAX_STEPS else "")
        tool, args = read_action(_call(ctx, prompt, system, f"agent-{n}"))
        trace.append({"tool": tool, **args})
        db = dbs.get(args.get("database", "").lower()) if tool else None
        if tool is None:
            obs, action = BAD_ACTION, "(no tool call)"
        else:
            action = render_action(tool, args)
            if db is None:
                obs = f"Unknown database {args.get('database', '')!r}. Use one from the list."
            elif tool == "answer":
                return {**out, "db": db, "sql": args["sql"], "stop": "answer", "steps": n, "trace": trace}
            elif tool == "describe":
                obs = render_schema(path_of(db))
            else:
                r = _run(path_of, db, args["sql"], max_rows=PREVIEW_ROWS)
                obs = render_result(r.rows, r.n_rows, r.error, PREVIEW_ROWS).strip()
        history.append(STEP.format(action=action, observation=obs))
    return {**out, "stop": "cap", "steps": AGENT_MAX_STEPS, "trace": trace}


def solve(q, level: str, ctx: Ctx, cards, path_of: Callable = db_path) -> dict:
    """One question at one level: {"db", "sql", "stop", "handoff", ...}. db None / sql "" = no answer."""
    if level not in LEVELS:
        raise ValueError(f"unknown level {level!r}")
    out = {"db": None, "sql": "", "stop": "", "handoff": False}
    if level == "0":
        return _one_prompt(q, ctx, cards, path_of, out)
    if level == "5":
        return _agent(q, ctx, cards, path_of, out)
    db = route(q, ctx, cards, allow_human=level == "1h")
    if db == "HUMAN":  # the stand-in human: someone who knows the warehouse picks the question's own database
        db, out["handoff"] = q.db_id, True
    if db is None:
        return {**out, "stop": "route_unreadable"}
    out["db"] = db
    schema = render_schema(path_of(db))
    if level in ("1", "1h"):
        return {**out, "sql": _write(q, ctx, schema, "write"), "stop": "ok"}
    if level == "2":
        return _parallel_vote(q, ctx, schema, path_of, db, out)
    if level == "3":
        return _orchestrate(q, ctx, schema, path_of, db, out)
    return _evaluator(q, ctx, path_of, db, out)
