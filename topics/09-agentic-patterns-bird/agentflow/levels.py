"""The five patterns from the guide, and a free agent, on the same question.

0   one prompt: every table of every database, the model names the database and writes the SQL
1   routing: a router names the database, a specialist writes SQL on that database only
1h  routing + handoff: the router may answer HUMAN; a stand-in human picks the right database
2   parallel vote: router, then 3 writers at once; the largest group with the same rows wins
3   orchestrator-worker: router, a planner splits the question, one worker per sub-question, a combiner
4   evaluator-optimizer: router, then topic 05's level 3 loop (writer + grader who sees the rows)
5   free agent: tools describe / run_sql / answer, at most AGENT_MAX_STEPS steps

The pattern logic (route, parallel + vote, orchestrate, refine, agent_loop) comes from shared.patterns.
This file only supplies the prompts, the answer readers and the SQL tools.
Every SQL writer uses topic 05's prompt (render_generate) and schema text (render_schema).
A failed model call raises; the runner records it as an API error.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from agentflow.prompts import (AGENT_INTRO, AGENT_LAST, AGENT_STEP, BAD_ACTION, COMBINE, DATABASE_LINE, HANDOFF_LINE,
                               NO_SQL, PART, PLAN, ROUTER, ROUTER_INTRO, STEP, WAREHOUSE_INTRO, read_action, read_database,
                               read_subquestions, render_action)
from shared import patterns
from shared.llm import Tracker, llm_call
from sqlblame.warehouse import render_cards
from sqlloop.data import db_path
from sqlloop.execute import ExecResult, normalize_rows, run_sql
from sqlloop.prompts import SCHEMA_INTRO, read_grade, read_sql, render_generate, render_grade, render_result
from sqlloop.schema import render_schema

LEVELS = ("0", "1", "1h", "2", "3", "4", "5")
N_WRITERS = 3
MAX_SUB = 4
MAX_ROUNDS = 3  # level 4, the same cap as topic 05
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


def _write(q, ctx: Ctx, schema: str, label: str, question: str | None = None, attempts=()) -> str:
    prompt = render_generate(question or q.question, q.evidence, list(attempts))
    return read_sql(_call(ctx, prompt, SCHEMA_INTRO + schema, label))


def _run(path_of, db: str, sql: str, max_rows: int | None = None) -> ExecResult:
    return run_sql(path_of(db), sql, timeout_s=RUN_TIMEOUT_S, max_rows=max_rows)


def rows_key(r: ExecResult):
    """Two queries agree when they return the same set of rows. A failed query has no key, so it never wins."""
    return frozenset(normalize_rows(r.rows)) if r.rows is not None else None


def vote(results: list[ExecResult]) -> int:
    return patterns.vote(results, rows_key)


def route(q, ctx: Ctx, cards, allow_human: bool = False) -> patterns.Route:
    prompt = ROUTER.format(question=q.question, evidence=q.evidence or "(none)") + (HANDOFF_LINE if allow_human else "")
    return patterns.route(lambda: _call(ctx, prompt, ROUTER_INTRO + render_cards(cards), "route"),
                          lambda text: read_database(text, _db_ids(cards), allow_human),
                          allow_human=allow_human,
                          human=lambda: q.db_id)  # the stand-in human knows the warehouse: the question's own database


def _one_prompt(q, ctx, cards, path_of, out):
    system = WAREHOUSE_INTRO + "\n\n".join(f"-- database: {d}\n{render_schema(path_of(d))}" for d in _db_ids(cards))
    text = _call(ctx, render_generate(q.question, q.evidence, []) + DATABASE_LINE, system, "write")
    db = read_database(text, _db_ids(cards))
    if db is None:
        return {**out, "stop": "db_unreadable"}
    return {**out, "db": db, "sql": read_sql(text), "stop": "ok"}


def _parallel_vote(q, ctx, schema, path_of, db, out):
    sqls = patterns.parallel([lambda i=i: _write(q, ctx, schema, f"write-{i + 1}") for i in range(N_WRITERS)])
    results = [_run(path_of, db, s) for s in sqls]
    win = vote(results)
    agree = sum(1 for r in results if r.rows is not None and rows_key(r) == rows_key(results[win])) or 1
    return {**out, "sql": sqls[win], "stop": "ok", "agree": agree, "candidates": sqls}


def _orchestrate(q, ctx, schema, path_of, db, out):
    system = SCHEMA_INTRO + schema
    evidence = q.evidence or "(none)"

    def plan():
        return read_subquestions(_call(ctx, PLAN.format(question=q.question, evidence=evidence), system, "plan"), MAX_SUB)

    def work(i, sub):
        return _write(q, ctx, schema, f"worker-{i + 1}", question=sub)

    def combine(subs, sqls):
        parts = []
        for s, sql in zip(subs, sqls):
            r = _run(path_of, db, sql, max_rows=PART_ROWS)
            parts.append(PART.format(sub=s, sql=sql, result=render_result(r.rows, r.n_rows, r.error, PART_ROWS).strip()))
        prompt = COMBINE.format(question=q.question, evidence=evidence, parts="\n".join(parts))
        return read_sql(_call(ctx, prompt, system, "combine"))

    o = patterns.orchestrate(plan, work, combine, original=q.question)
    res = {**out, "sql": o.final, "stop": "ok", "n_sub": max(len(o.planned), 1), "subquestions": o.planned}
    return res if len(o.planned) <= 1 else {**res, "worker_sql": o.results}


def _evaluator(q, ctx, schema, path_of, db, out):
    """Topic 05's level 3 loop: the writer sees its earlier tries and the feedback; the grader sees the SQL and its rows."""
    system = SCHEMA_INTRO + schema
    rnd = [0]

    def write(history):
        rnd[0] = len(history) + 1
        return _write(q, ctx, schema, f"generate-{rnd[0]}", attempts=history)

    def grade(sql):
        r = _run(path_of, db, sql, max_rows=PREVIEW_ROWS)
        result = render_result(r.rows, r.n_rows, r.error, PREVIEW_ROWS)
        text = _call(ctx, render_grade(q.question, q.evidence, sql, result), system, f"grade-{rnd[0]}")
        verdict, feedback = read_grade(text)
        return (None if verdict is None else verdict == "PASS"), feedback

    ref = patterns.refine(write, grade, MAX_ROUNDS)
    return {**out, "sql": ref.final, "stop": ref.stop, "rounds": len(ref.rounds)}


def _agent(q, ctx, cards, path_of, out):
    dbs = {d.lower(): d for d in _db_ids(cards)}
    system = AGENT_INTRO.format(cards=render_cards(cards), max_steps=AGENT_MAX_STEPS)
    evidence = q.evidence or "(none)"

    def call(n, history, last):
        steps = "\n".join(STEP.format(action=a, observation=o) for a, o in history)
        prompt = AGENT_STEP.format(question=q.question, evidence=evidence, history=f"\n{steps}\n" if history else "",
                                   n=n, max_steps=AGENT_MAX_STEPS, last=AGENT_LAST if last else "")
        return _call(ctx, prompt, system, f"agent-{n}")

    def on_database(fn, needs_sql=True):
        """A tool that refuses (with a note back to the agent) an unknown database or a missing query."""
        def tool(args):
            db = dbs.get(args.get("database", "").lower())
            if db is None:
                return f"Unknown database {args.get('database', '')!r}. Use one from the list."
            if needs_sql and not args["sql"]:
                return NO_SQL
            return fn(db, args["sql"])
        return tool

    def preview(db, sql):
        r = _run(path_of, db, sql, max_rows=PREVIEW_ROWS)
        return render_result(r.rows, r.n_rows, r.error, PREVIEW_ROWS).strip()

    tools = {"describe": on_database(lambda db, _sql: render_schema(path_of(db)), needs_sql=False),
             "run_sql": on_database(preview),
             "answer": on_database(lambda db, sql: patterns.Final((db, sql)))}
    run = patterns.agent_loop(call, read_action, tools, AGENT_MAX_STEPS,
                              render=lambda name, args, _text: render_action(name, args), bad_action=BAD_ACTION)
    if run.final is None:
        return {**out, "stop": "cap", "steps": run.steps, "trace": run.trace}
    db, sql = run.final
    return {**out, "db": db, "sql": sql, "stop": "answer", "steps": run.steps, "trace": run.trace}


def solve(q, level: str, ctx: Ctx, cards, path_of: Callable = db_path) -> dict:
    """One question at one level: {"db", "sql", "stop", "handoff", ...}. db None / sql "" = no answer."""
    if level not in LEVELS:
        raise ValueError(f"unknown level {level!r}")
    out = {"db": None, "sql": "", "stop": "", "handoff": False}
    if level == "0":
        return _one_prompt(q, ctx, cards, path_of, out)
    if level == "5":
        return _agent(q, ctx, cards, path_of, out)
    r = route(q, ctx, cards, allow_human=level == "1h")
    out["handoff"] = r.handoff
    if r.choice is None:
        return {**out, "stop": "route_unreadable"}
    db = out["db"] = r.choice
    schema = render_schema(path_of(db))
    if level in ("1", "1h"):
        return {**out, "sql": _write(q, ctx, schema, "write"), "stop": "ok"}
    if level == "2":
        return _parallel_vote(q, ctx, schema, path_of, db, out)
    if level == "3":
        return _orchestrate(q, ctx, schema, path_of, db, out)
    return _evaluator(q, ctx, schema, path_of, db, out)
