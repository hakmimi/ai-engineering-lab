# Topic 09 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline). Steps use `- [ ]`.

**Goal:** Run five workflow patterns and a free agent on the same 60 + 60 BIRD Mini-Dev questions and report right
answers, same-answer-in-3-repeats, $ and seconds.

**Architecture:** Package `agentflow` in `topics/09-agentic-patterns-bird/`. `prompts.py` holds new prompt text and
answer readers; `levels.py` has one `solve(q, level, ctx, ...)` per pattern, built from topic 05's writer
(`sqlloop.prompts.render_generate`, `sqlloop.schema.render_schema`, `sqlloop.levels.solve` for the evaluator loop) and
topic 07's cards (`sqlblame.warehouse`). `run.py` runs the final SQL, scores, saves with `shared.runs.save_run`.
`score.py` + `report.py` + `charts.py` build `results.md` and `charts/*.svg`.

**Tech stack:** Python 3, sqlite3, pytest; `shared.llm`, `shared.runs`, `shared.charts`.

**Spec:** `topics/09-agentic-patterns-bird/design/design.md`

PYTHONPATH: `.;topics/05-evaluator-optimizer-text-to-sql;topics/07-text-to-sql-where-it-breaks;topics/09-agentic-patterns-bird`

## Global Constraints

- Model `gpt-6-luna` (`default_model("small")`) in every role. 3 repeats. Topic ceiling $5 (`shared.runs.DEFAULT_CEILING_USD`).
- Gold SQL, difficulty and `q.db_id` never appear in a prompt (exception: level 1h's stand-in human, which is code).
- An API exception → `error` set, left out of rates. A run file has top-level `cost_usd`, `limit`, `partial`.
- Right = chosen database is `q.db_id` **and** `same_result(rows, gold_rows)`.
- Tests are offline (`conftest.py` blocks real clients); test files `evals/test_flow_*.py`, helper `evals/flow_helpers.py`.

## Review Focus

1. A level that cannot read the database name → "no answer", not a crash and not an API error.
2. Level 2 vote with all three queries failing → falls back to writer 1's SQL.
3. Level 3 planner answer with 0 or more than 4 sub-questions → 1 (the question itself) / first 4.
4. Level 5 agent that never calls `answer` → stops at 10 steps, "no answer", cap counted.
5. Consistency with an API error in one repeat → the question is left out of the 3/3 rates.

---

### Task 1: Prompts and readers

**Files:** create `agentflow/__init__.py`, `agentflow/paths.py`, `agentflow/prompts.py`; test `evals/test_flow_prompts.py`;
modify `pyproject.toml` (add the 09 folder to `pythonpath` and `testpaths`).

**Produces:**
- `read_database(text: str, db_ids: Sequence[str], allow_human=False) -> str | None` — `<database>` tag, matched case-insensitively;
  `"HUMAN"` only when `allow_human`; unknown → None.
- `read_subquestions(text: str, cap: int = 4) -> list[str]` — every `<subquestion>`; first `cap`.
- `read_action(text: str) -> tuple[str | None, dict]` — `<tool>` in {describe, run_sql, answer} plus `database`, `sql`.
- `render_db_list(cards) -> str` — `db: table, table, ...` per database.

Tests: tag found / unknown name / HUMAN refused without `allow_human`; 0, 2, 6 sub-questions; each tool; no tool → (None, {}).

### Task 2: Levels 0, 1, 1h, 2

**Files:** create `agentflow/levels.py`, `evals/flow_helpers.py` (two tiny DBs, as topic 07); test `evals/test_flow_levels.py`.

**Produces:** `Ctx(model, tracker, llm)`, `LEVELS = ("0", "1", "1h", "2", "3", "4", "5")`,
`solve(q, level, ctx, cards, path_of=db_path) -> dict` with at least `db`, `sql`, `stop`, `handoff`, `calls_detail`.

- 0: one call, system = SCHEMA_INTRO + every database's schema under a `-- database: <id>` header; reads `<database>` + `<sql>`.
- 1/1h: router (cards) → db; 1h may answer HUMAN → `db = q.db_id`, `handoff = True`. Writer = topic 05 level 0 call.
- 2: router → 3 writers in a thread pool → run each (`run_sql`, 10 s) → `vote(results) -> int` (largest same-rows group,
  ties to the earliest; failures only if all fail → writer 1).

Tests: prompts never contain gold SQL or the db id string of a question whose db the router must find (level 0/1);
unreadable router → `stop == "route_unreadable"`, `sql == ""`; 1h handoff; vote majority, tie, all-fail.

### Task 3: Levels 3, 4, 5

**Files:** modify `agentflow/levels.py`; test `evals/test_flow_levels.py`.

- 3: router → planner (`<subquestion>`s) → 1: one worker on the original question, its SQL final; n>1: n workers at once,
  each SQL run (5 preview rows), combiner writes `<sql>`. Record `n_sub`.
- 4: router → `sqlloop.levels.solve(q, "3", ctx05, db)`. Record `rounds`.
- 5: transcript loop, at most `AGENT_MAX_STEPS = 10`; observations: describe → `render_schema`, run_sql → `render_result`
  (10 rows), unreadable → a format reminder. `answer` ends it. Record `steps`, `stop` ∈ {answer, cap}.

Tests: 3 with one and with two sub-questions (combiner called once); 4 passes rounds through; 5 answer after
describe + run_sql; 5 cap at 10 → `sql == ""`, `stop == "cap"`.

### Task 4: Runner and scoring

**Files:** create `agentflow/score.py`, `agentflow/run.py`; tests `evals/test_flow_score.py`, `evals/test_flow_run.py`.

**Produces:** `outcome_key(db, rows, error, stop, handoff) -> str`; `score_repeat(results) -> dict`
(`n, api_errors, right, right_db, handoff, right_rest, cost, seconds, calls` and per-level extras);
`consistency(repeats) -> dict` (`same`, `right_all`, `n`); `run.main(argv) -> int` with the standard flags,
`estimate_cost_usd`, smoke-measured estimate (latest run of the level with `limit` set, × 1.5), guard on budget and
`shared.runs.over_ceiling`, `save_run`.

Tests: right needs the right database; API error left out; same outcome across repeats; an error repeat excluded;
dry run spends nothing; over-budget refuses; saved file has `cost_usd`, `limit`, `repeats`.

### Task 5: Report and charts

**Files:** create `agentflow/report.py` (`results.md` + `charts/`), test `evals/test_flow_report.py`.

Tables per set: Level | Right | Same answer 3/3 | Right 3/3 | Right database | $ / q | s / q | calls / q | API errors;
1h row adds handoff share and right on the rest; extras (vote agreement, sub-questions, rounds, agent steps, cap hit).
Charts: right by level, same-answer 3/3 by level, seconds per question, $ per question (main and held-out series).
"Not run" for missing levels.

Tests: report from two fake run files; a missing level prints "not run"; charts written.
