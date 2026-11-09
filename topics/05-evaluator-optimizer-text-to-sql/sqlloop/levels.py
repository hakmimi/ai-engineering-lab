"""Levels 0-3 (and 0+, which is level 0 on the large model).

0  one prompt
1  generator + AI grader that reads the SQL (the cookbook's loop), at most MAX_ROUNDS generations
2  generator + code runs the SQL; an error or zero rows goes back as feedback (no AI grader)
3  generator + AI grader that also sees the error or the first result rows
4  like 1, but the grader is a bigger model (teacher grades, student writes)
5  like 3, but the grader is a bigger model
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from shared.llm import Tracker, llm_call
from sqlloop.execute import run_sql
from sqlloop.models import Question
from sqlloop.prompts import (FEEDBACK_EMPTY, FEEDBACK_ERROR, SCHEMA_INTRO, read_grade, read_sql, render_generate,
                             render_grade, render_result)
from sqlloop.schema import render_schema

MAX_ROUNDS = 3
RUN_TIMEOUT_S = 10.0
PREVIEW_ROWS = 10


@dataclass
class Ctx:
    model: str
    grader_model: str | None = None  # None: the writer grades itself
    tracker: Tracker = field(default_factory=Tracker)
    llm: Callable[..., str] = llm_call


def _call(ctx: Ctx, prompt: str, system: str, label: str, model: str | None = None) -> str:
    return ctx.llm(prompt, cached_system=system, model=model or ctx.model, label=label, tracker=ctx.tracker)


def solve(q: Question, level: str, ctx: Ctx, db: Path) -> dict:
    level = {"4": "1", "5": "3"}.get(level, level)  # same loop, only the grader model differs
    system = SCHEMA_INTRO + render_schema(db)
    one_shot = level in ("0", "0+")
    rounds: list[dict] = []
    attempts: list[tuple[str, str]] = []
    stop = "cap"
    for n in range(1 if one_shot else MAX_ROUNDS):
        sql = read_sql(_call(ctx, render_generate(q.question, q.evidence, attempts), system, f"generate-{n + 1}"))
        rnd = {"sql": sql, "error": "", "n_rows": None, "verdict": None, "feedback": ""}
        rounds.append(rnd)
        if one_shot:
            stop = "one_shot"
            break
        if level in ("2", "3"):
            r = run_sql(db, sql, timeout_s=RUN_TIMEOUT_S, max_rows=PREVIEW_ROWS)
            rnd["error"], rnd["n_rows"] = r.error, (r.n_rows if r.rows is not None else None)
        if level == "2":
            if rnd["error"]:
                rnd["feedback"] = FEEDBACK_ERROR.format(error=rnd["error"])
            elif rnd["n_rows"] == 0:
                rnd["feedback"] = FEEDBACK_EMPTY
            else:
                stop = "ok"
                break
        else:  # levels 1 and 3: the AI grader
            result = ""
            if level == "3":
                result = render_result(r.rows, r.n_rows, r.error, PREVIEW_ROWS)
            verdict, feedback = read_grade(_call(ctx, render_grade(q.question, q.evidence, sql, result), system, f"grade-{n + 1}", ctx.grader_model))
            rnd["verdict"], rnd["feedback"] = verdict, feedback
            if verdict == "PASS":
                stop = "pass"
                break
            if verdict is None:
                stop = "grade_unreadable"
                break
        attempts.append((sql, rnd["feedback"]))
    return {"rounds": rounds, "final_sql": rounds[-1]["sql"], "stop": stop}
