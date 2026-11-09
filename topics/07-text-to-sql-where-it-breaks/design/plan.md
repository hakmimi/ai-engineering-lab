# 07 · Where text-to-SQL breaks — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Measure how much of text-to-SQL's error comes from picking tables vs writing SQL (Uber's vanilla vs decoupled flows), and whether Uber's cheap per-question signals track the true answer.

**Architecture:** New package `sqlblame` in topic 07 that **imports topic 05's `sqlloop`** for questions, databases, the writer prompt, SQL execution and result comparison. Topic 07 adds: gold tables (SQLite authorizer), a 75-table warehouse with a table agent, levels A/B/C, scoring, a runner with cost guards, an LLM similarity judge, and a report.

**Tech Stack:** Python 3, sqlite3, `shared/llm.py` (OpenAI `gpt-6-luna`), pytest (offline, fake LLM).

**Spec:** `topics/07-text-to-sql-where-it-breaks/design/design.md`

## Global Constraints

- Questions: topic 05's `main.json` / `test.json` via `sqlloop.data.load_set`; databases via `sqlloop.data.db_path`. Nothing new downloaded.
- Level A's writer call must be **byte-for-byte topic 05 level 0**: `cached_system = SCHEMA_INTRO + render_schema(db)`, `prompt = render_generate(question, evidence, [])`, parsed with `read_sql`.
- Levels: `A` whole database, `B` gold tables only, `C` table agent over all 75 tables, then writer. Model `default_model("small")` for writer, agent and judge.
- Warehouse table name format: `database.table`. 75 tables, 798 columns (assert in a data test against the real files when present; skip if `data/raw` missing).
- Agent cards: `database.table` + column names and types only, no sample rows. Writer schema: CREATE TABLE + 3 sample rows (topic 05 format).
- 3 repeats per level per set. Prediction timeout 10 s. API errors are excluded from rates and counted.
- Read-only DB connections only. `$10` topic ceiling (all run + judge files in `runs/`, smoke included), smoke-measured estimate × 1.5, `--budget` stop, `--dry-run`, ask before spending.
- Judge threshold picked on **main** only, applied unchanged to held-out. No tuning after the held-out run starts.
- Nobody but the scorer sees gold SQL / gold rows; only level B's writer sees gold *tables*. The judge sees gold SQL (it never feeds back).
- No hand-typed numbers: README / results / blog numbers come from `python -m sqlblame.report`.
- README / blog: flow claim → expected → test → main → held-out, **own opening and topic-specific headings**; never "How this started", "So, I came across…", "What X claims, and what it implies".
- Commit/push only when the user asks (commit steps below are prepared, run them only with the user's OK).

## Review Focus

1. **Table agent output in odd shapes** — names with backticks/quotes, other case, bare `table` without the database, duplicates, prose around the list → matched case-insensitively, quotes stripped, a bare name accepted only if it's unique in the warehouse, duplicates dropped. Test in Task 3.
2. **Agent returns nothing usable** → writer still runs with an empty schema, outcome marked `agent_empty`, scored as written. Test in Task 4.
3. **Gold SQL with aliases, subqueries, a table used twice, quoted names** → each real table listed once, in sqlite_master spelling. Test in Task 1.
4. **Judge answer unreadable or outside 0–1** → score `None`, counted as `judge_unreadable`, left out of threshold picking and rates. Test in Task 7.
5. **API error at the agent step at level C** → whole outcome `error` set, excluded from rates, counted in `api_errors`; no writer call made. Test in Task 4.

---

### Task 1: Scaffold and gold tables

**Files:**
- Create: `topics/07-text-to-sql-where-it-breaks/sqlblame/__init__.py` (empty), `sqlblame/paths.py`, `sqlblame/gold_tables.py`, `evals/test_blame_gold.py`, `evals/blame_helpers.py`
- Modify: `pyproject.toml` (add `topics/07-text-to-sql-where-it-breaks` to `pythonpath` and its `evals` to `testpaths`)
- Create at run time: `data/gold_tables.json`, `data/NOTICE.md`

**Interfaces:**
- Produces: `tables_read(db: Path | str, sql: str) -> list[str]` (sqlite_master spelling, sorted, unique); `build(set_names=("main","test")) -> dict[str, list[str]]` keyed by `str(qid)`; `load_gold() -> dict[str, list[str]]`; `GOLD_PATH = TOPIC_DIR / "data" / "gold_tables.json"`. `sqlblame/paths.py` holds `TOPIC_DIR = Path(__file__).resolve().parent.parent` and `RUNS_DIR = TOPIC_DIR / "runs"`.
- `evals/blame_helpers.py`: `make_dbs(tmp: Path) -> dict[str, Path]` builds two tiny databases, `shop` (tables `Customer`, `orders`) and `zoo` (tables `animal`, `keeper`), unique table names.

- [ ] **Step 1: Write failing tests** in `evals/test_blame_gold.py`:
  - `test_join_lists_both_tables`: `SELECT c.name FROM Customer c JOIN orders o ON o.cid = c.id` → `["Customer", "orders"]`.
  - `test_subquery_and_repeat_listed_once`: `SELECT name FROM Customer WHERE id IN (SELECT cid FROM orders) AND id IN (SELECT cid FROM orders)` → `["Customer", "orders"]`.
  - `test_case_and_quotes_use_master_spelling`: `SELECT * FROM "customer"` → `["Customer"]`.
  - `test_does_not_execute`: a query with a 10 s cross join returns at once (< 1 s) — prepare via `EXPLAIN`, never run.
  - `test_real_gold_tables` (skip if topic 05 `data/raw` missing): `build()` gives 120 entries, none empty; main counts of 1/2/3/4 tables = 13/34/12/1, test = 12/33/10/5.
- [ ] **Step 2: Run** `pytest topics/07-text-to-sql-where-it-breaks/evals/test_blame_gold.py -v` → FAIL (module missing).
- [ ] **Step 3: Implement** `tables_read` with `con.set_authorizer` collecting `SQLITE_READ` arg1 on a read-only connection, then `EXPLAIN <sql>`; map lower-case names to sqlite_master names; drop non-tables. `build` uses `sqlloop.data.load_set` / `db_path`. `python -m sqlblame.gold_tables` writes `gold_tables.json` (`{"qid": [tables]}`) and `NOTICE.md` (BIRD Mini-Dev, CC BY-SA 4.0, derived from gold SQL by SQLite's authorizer, no SQL stored).
- [ ] **Step 4: Run** the tests → PASS. Run `python -m sqlblame.gold_tables` → writes 120 entries.
- [ ] **Step 5: Commit** (with the user's OK): `Topic 07 task 1: gold tables from SQLite's authorizer`.

### Task 2: Warehouse cards and table-subset schema

**Files:** Create `sqlblame/warehouse.py`, `evals/test_blame_warehouse.py`

**Interfaces:**
- Consumes: `sqlloop.data.db_path`, `sqlloop.schema.render_schema`.
- Produces:
  - `@dataclass(frozen=True) Card: db_id: str; table: str; columns: tuple[tuple[str, str], ...]` with property `name -> f"{db_id}.{table}"`.
  - `load_warehouse(db_ids: list[str], path_of=db_path) -> list[Card]` (db_ids sorted, tables in sqlite_master rowid order).
  - `ALL_DBS: tuple[str, ...]` = the 11 BIRD Mini-Dev db_ids, read from `data/raw/dev_databases` directory names, sorted.
  - `render_cards(cards: list[Card]) -> str`: one line per table, `database.table: col TYPE, col TYPE, …`.
  - `render_tables(picks: list[tuple[str, str]], path_of=db_path) -> str`: schema text for (db_id, table) pairs in the given order, **same block format as topic 05's `render_schema`** (CREATE TABLE + `/* 3 example rows … */`), blocks joined by a blank line; empty list → `""`.

- [ ] **Step 1: Failing tests:**
  - `test_render_tables_all_equals_render_schema`: for the `shop` fixture, `render_tables([("shop","Customer"),("shop","orders")], path_of=…) == render_schema(shop_path)`.
  - `test_render_tables_subset_keeps_order`: `[("shop","orders")]` contains `CREATE TABLE orders` and not `Customer`.
  - `test_cards_have_db_prefix_and_types`: `render_cards(load_warehouse(["shop","zoo"], path_of=…))` contains the line `shop.Customer: id INTEGER, name TEXT` (match fixture DDL) and has 4 lines.
  - `test_real_warehouse_size` (skip without raw data): 75 cards, 798 columns, all `name`s unique case-insensitively.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement.** Re-use topic 05's block format by extracting it per table (copy the 10-line block builder; the equality test pins it).
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit:** `Topic 07 task 2: warehouse cards and table-subset schema`.

### Task 3: Table agent

**Files:** Create `sqlblame/agent.py`, `evals/test_blame_agent.py`

**Interfaces:**
- Consumes: `Card`, `render_cards`; `shared.llm.extract_xml`.
- Produces:
  - `AGENT_INTRO`: system text = short instruction + `render_cards(cards)` (sent as `cached_system`).
  - `AGENT_PROMPT`: asks for the tables needed to answer, `<thoughts>…</thoughts>` then `<tables>database.table, …</tables>`; formatted with `question`, `evidence` (`"(none)"` if empty).
  - `read_tables(text: str, cards: list[Card]) -> tuple[list[tuple[str, str]], list[str]]` → (picked `(db_id, table)` in answer order, made-up raw names).
  - `pick_tables(q, ctx, cards) -> dict` → `{"picked": [[db, table], …], "made_up": [...], "raw": text}`; one call labelled `"agent"` via `ctx.llm(prompt, cached_system=..., model=ctx.model, label="agent", tracker=ctx.tracker)`.

- [ ] **Step 1: Failing tests** (cards from the fixture warehouse):
  - `test_reads_comma_and_newline_lists`: `"<tables>shop.Customer,\nshop.orders</tables>"` → both, no made-up.
  - `test_odd_spelling` (Review Focus 1): `` `SHOP.customer` ``, `"zoo.animal"`, `keeper` (bare, unique) → `[("shop","Customer"),("zoo","animal"),("zoo","keeper")]`.
  - `test_duplicates_dropped`: `shop.orders, shop.orders` → one.
  - `test_unknown_is_made_up`: `shop.payments` → picked `[]`, made_up `["shop.payments"]`.
  - `test_no_tag_falls_back_to_whole_text_lines`: an answer without `<tables>` but with `shop.orders` on a line → picked `[("shop","orders")]`.
  - `test_pick_tables_sends_cards_as_system`: fake LLM sees `shop.Customer:` in `cached_system` and the question in the prompt; label `"agent"`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit:** `Topic 07 task 3: table agent`.

### Task 4: Levels A / B / C

**Files:** Create `sqlblame/levels.py`, `evals/test_blame_levels.py`

**Interfaces:**
- Consumes: `sqlloop.prompts.SCHEMA_INTRO, render_generate, read_sql`; `sqlloop.schema.render_schema`; `render_tables`; `pick_tables`.
- Produces:
  - `LEVELS = ("A", "B", "C")`
  - `@dataclass Ctx: model: str; tracker: Tracker = field(default_factory=Tracker); llm: Callable[..., str] = llm_call`
  - `solve(q: Question, level: str, ctx: Ctx, gold: list[str], cards: list[Card], path_of=db_path) -> dict` returning `{"sql", "given_tables": [[db, table], …], "picked": [...] | None, "made_up": [...] | None, "agent_empty": bool}`.
  - A: system `SCHEMA_INTRO + render_schema(path_of(q.db_id))`; B: `SCHEMA_INTRO + render_tables([(q.db_id, t) for t in gold])`; C: `pick_tables`, then `SCHEMA_INTRO + render_tables(picked)`. Writer call label `"write"`.

- [ ] **Step 1: Failing tests:**
  - `test_level_a_matches_topic05_level0`: with the same fake LLM, `solve(...,"A",...)` sends exactly the `cached_system` and `prompt` that `sqlloop.levels.solve(q,"0",…)` sends.
  - `test_level_b_shows_only_gold_tables`: gold `["orders"]` → system has `CREATE TABLE orders`, not `Customer`.
  - `test_level_c_writer_gets_picked_tables_from_any_db`: agent picks `zoo.animal` for a `shop` question → writer system contains `CREATE TABLE animal`; `given_tables == [["zoo","animal"]]`.
  - `test_level_c_agent_empty` (Review Focus 2): agent answers `<tables></tables>` → writer still called, system == `SCHEMA_INTRO`, `agent_empty` True.
  - `test_level_c_agent_api_error_raises_before_writer` (Review Focus 5): fake LLM raises on the agent call → `solve` raises; the fake saw 1 call.
- [ ] **Step 2–4:** run FAIL → implement → run PASS.
- [ ] **Step 5: Commit:** `Topic 07 task 4: levels A, B, C`.

### Task 5: Scoring

**Files:** Create `sqlblame/score.py`, `evals/test_blame_score.py`

**Interfaces:**
- Produces `score(outcomes: dict[str, dict], difficulty: dict[str, str], gold: dict[str, list[str]], db_of: dict[str, str]) -> dict` with keys:
  `n, api_errors, right, by_difficulty{simple,moderate,challenging}, runs, has_output, final_errors` and, when outcomes carry `picked` (level C): `overlap` (mean of |gold ∩ picked-in-own-db| / |gold|), `all_found`, `exact`, `extra` (mean picked not in gold), `wrong_db` (share with any pick from another db), `made_up` (total names), `agent_empty` (count), `right_all_found`, `right_missing` (accuracy split). Rates `None` when the denominator is 0. Each outcome has `right: bool, error: str, final_error: str, n_rows: int | None, picked, made_up, agent_empty`.

- [ ] **Step 1: Failing tests** with 4 hand-built outcomes: exact values for `overlap` (e.g. gold `[a,b]`, picked `[a]` → 0.5; mean over questions), `all_found`, `exact`, `extra`, `wrong_db`, `right_all_found` / `right_missing`, an `error` outcome excluded from all rates and counted in `api_errors`, and no level-C keys' values when no outcome has `picked` (they are `None`).
- [ ] **Step 2–4:** FAIL → implement → PASS.
- [ ] **Step 5: Commit:** `Topic 07 task 5: scoring`.

### Task 6: Runner with cost guards

**Files:** Create `sqlblame/run.py`, `evals/test_blame_run.py`

**Interfaces:**
- Consumes: everything above; `sqlloop.execute.run_sql, same_result`; `shared.llm` (`PRICES, Tracker, cost_usd, default_model, llm_call, load_env, require_api_key`).
- Produces: `TOPIC_CEILING_USD = 10.0`, `SMOKE_MARGIN = 1.5`, `estimate_cost_usd(level, questions, model, repeats, gold, cards) -> float` (upper side: chars ÷ 4 tokens + 1500 output tokens per call; C counts agent call with `render_cards` size plus a writer call with the whole-db schema size), `measured_estimate(kind, n, repeats, runs_dir)` (latest `runs/smoke/{kind}-*.json`, kind = `level-A` … or `judge`), `spent_in_runs(runs_dir)` (sums `cost_usd` in every `level-*.json` and `judge-*.json` under runs, smoke included), `main(argv)` with the same flags as topic 05 (`--level {A,B,C} --set --repeats --limit --budget --workers --smoke --yes --dry-run --runs-dir`).
- Run file: `runs/[test/|smoke/]level-{L}-{stamp}.json` = `{"level","model","set","created","questions","repeats":[{"results":{qid: outcome},"scores":{...}}]}`; each outcome adds `right, error, final_error, n_rows, seconds, calls, cost_usd`.

- [ ] **Step 1: Failing tests** (fake LLM via monkeypatching `sqlblame.run.llm_call`, fixture dbs/gold via monkeypatched loaders):
  - `test_dry_run_spends_nothing`: `--dry-run` prints an estimate, no LLM call, no file.
  - `test_over_budget_does_not_run` and `test_ceiling_counts_judge_files`: an existing `judge-x.json` with `cost_usd` 9.99 blocks a run.
  - `test_run_file_records_n_rows_and_error`: a right SQL → `right True, n_rows ≥ 1`; a bad column → `right False, final_error` set.
  - `test_measured_estimate_uses_smoke_cost_with_margin`.
  - `test_api_error_counted_not_scored`.
- [ ] **Step 2–4:** FAIL → implement → PASS.
- [ ] **Step 5: Commit:** `Topic 07 task 6: runner with dry run, budget, ceiling`.

### Task 7: Uber's similarity judge and signal rates

**Files:** Create `sqlblame/judge.py`, `sqlblame/signals.py`, `evals/test_blame_judge.py`

**Interfaces:**
- `JUDGE_PROMPT`: question, evidence, predicted SQL, golden SQL; "how similar in intent is the predicted query to the golden one, 0 to 1"; answer `<score>0.0–1.0</score>`.
- `read_score(text) -> float | None` (None if missing, not a number, or outside [0, 1]).
- `python -m sqlblame.judge --set main|test [--smoke --limit N] [--budget] [--yes] [--dry-run]`: reads the latest run file per level for that set, judges every final SQL **once per distinct (qid, sql)** (cache), writes `runs/[test/|smoke/]judge-{stamp}.json` = `{"set","model","scores":{"A|<repeat>|<qid>": score|None}, "calls":[...], "cost_usd": float}`; same estimate / budget / ceiling rules as Task 6.
- `signals.py`: `THRESHOLDS = (0.1, 0.2, …, 0.9)`; `pick_threshold(pairs: list[tuple[float, bool]]) -> float` (max agreement with `right`; ties → higher threshold); `signal_rates(rows) -> dict` where each row is `{"right", "runs", "has_output", "similarity": float|None}` and output has per signal (`runs`, `has_output`, `similarity`) `good_when_wrong` and `good_when_right` rates, plus `judge_unreadable` count.

- [ ] **Step 1: Failing tests:** `read_score` on `"<score>0.8</score>"`, `"<score>1.5</score>"`→None, `"great"`→None (Review Focus 4); `pick_threshold` on a hand set with a known best and a tie; `signal_rates` exact rates on 4 rows incl. one `None` similarity; judge CLI with fake LLM calls once for two repeats with identical SQL.
- [ ] **Step 2–4:** FAIL → implement → PASS.
- [ ] **Step 5: Commit:** `Topic 07 task 7: similarity judge and Uber's signals`.

### Task 8: Report, charts, process diagram

**Files:** Create `sqlblame/report.py`, `sqlblame/charts.py`, `evals/test_blame_report.py`, `design/process-diagram.html` (+ `.png` screenshot)

**Interfaces:**
- `python -m sqlblame.report` → `results.md` (header "Built by `python -m sqlblame.report` from the run files only. Do not edit by hand."), per set: levels table (right, by difficulty, runs, has output, $/q, s/q, api errors), **gaps** (B − A, B − C, C − A, in points), table-agent table (C only), signals table (threshold picked on main, shown, used for test), total spent. Uses the latest run file per (set, level) and the latest judge file per set.
- `charts.py` → `charts/right-by-level.svg`, `charts/table-agent.svg`, `charts/signals.svg` (topic 04 style: plain inline SVG, light/dark-safe colors).
- Process diagram: question → [A whole db | B gold tables | C agent over 75 tables] → writer → run → score; same CSS tokens as topic 05's diagram.

- [ ] **Step 1: Failing tests:** report on two fake run files per level + a fake judge file: gaps computed right (e.g. A 0.50, B 0.60, C 0.55 → B − A `+10`, B − C `+5`, C − A `+5`); the threshold line shows the main-set pick for both sets; missing level shows `–`.
- [ ] **Step 2–4:** FAIL → implement → PASS. Generate the diagram PNG via the browser screenshot.
- [ ] **Step 5: Commit:** `Topic 07 task 8: report, charts, process diagram`.

### Task 9: Paid runs (stop and ask the user before each spend)

- [ ] **Step 1:** Full suite `pytest` → all pass (record count).
- [ ] **Step 2:** `--dry-run` for A, B, C and the judge; show the user the estimates. **Wait for OK.**
- [ ] **Step 3:** Smoke: each level `--smoke --limit 5 --repeats 1 --yes`, then `judge --smoke --limit 5`. Read outputs; spot-check 2 agent answers and 2 judge answers by eye. Fix bugs only (TDD), not prompts tuned to answers.
- [ ] **Step 4:** Show the measured estimates; **wait for OK**; main set A, B, C × 3, then `judge --set main`.
- [ ] **Step 5:** Report; show the user main results. Freeze prompts. **Wait for OK**; held-out A, B, C × 3, `judge --set test`, report.
- [ ] **Step 6:** `runs/` stays git-ignored; `results.md` and `charts/` are what gets committed (in Task 10).

### Task 10: README and wrap-up

- [ ] **Step 1:** `README.md` in the human style, numbers only from `results.md`: own opening (a concrete moment, not "So, I came across…"), topic-specific headings, three companies' claim, what I expected (copy design's section), the test, main results, held-out results, takeaways, limits (75 tables ≠ Uber scale; `database.table` names help the agent; one model), technical walkthrough with run commands. Check headings differ from posts 01–05 and from topic 06.
- [ ] **Step 2:** Update `design/plan.md` rulings and `C:\Workshop\ai-engineering-lab-process\articles.md` if it lists topics.
- [ ] **Step 3:** Full `pytest`; final whole-change review.
- [ ] **Step 4: Commit** with the user's OK: `Topic 07: where text-to-SQL breaks — tables vs writing (BIRD Mini-Dev)`.
