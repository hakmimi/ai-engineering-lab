# 05 · Evaluator-optimizer on text-to-SQL — build plan

**Spec:** [design.md](design.md) (approved 2026-11-09, with option A: only the SQLite part of `minidev.zip`, ~346 MB; budget ~$3–6 under a $10 ceiling).

**Where:** directly in `topics/05-evaluator-optimizer-text-to-sql/` on `main`'s working folder (no worktree, per the user).

**Tech:** Python 3, `sqlite3` (stdlib), `shared/llm.py` (`llm_call`, `Tracker`, `PRICES`), pytest. Tests build a tiny SQLite file in `tmp_path`; the root `conftest.py` blocks real API calls.

## Global constraints

- Databases opened read-only: `sqlite3.connect(f"file:{path}?mode=ro", uri=True)`.
- Prediction timeout 10 s, gold timeout 30 s, via `set_progress_handler`.
- Right = `set(pred_rows) == set(gold_rows)` after normalising values (bytes → hex string).
- Cap: 3 generations per question. Levels 0–3 `gpt-6-luna`, 0+ `gpt-6.1-sol` (`default_model("small"/"large")`).
- Model never sees gold SQL, gold rows or difficulty.
- `run.py`: estimate first, `--budget` per command, refuses to pass the $10 topic ceiling counted from saved run files.
- Every reported number comes from `runs/`.

## Tasks

1. **`models.py`, `execute.py`** — `Question` dataclass; `run_sql(db, sql, timeout_s, max_rows=None) -> ExecResult(rows, error)`; `normalize_rows`; `same_result(a, b) -> bool`. Tests: read-only (an `INSERT` fails), timeout on a slow recursive query, set comparison ignores order and duplicates, bytes normalised, error text kept.
2. **`schema.py`** — `render_schema(db_path, sample_rows=3, max_cell=60) -> str`: `CREATE TABLE` text + up to 3 rows per table, long cells cut. Tests on the fixture.
3. **`build_data.py`, `data.py`** — split the 11 DBs with seed 2026 into A (6) / B (5); draw 18/30/12 by difficulty from each group; run each gold SQL (30 s); a failing gold query is replaced by the next draw and logged. `load_set(name) -> list[Question]`, `db_path(db_id)`. Tests: repeatable draw, no shared DB between sets, counts per difficulty, failing gold replaced.
4. **`prompts.py`** — generator (with history of earlier attempts + feedback), grader-reads (level 1), grader-sees-result (level 3); `read_sql`, `read_grade -> (verdict | None, feedback)`. Tests: tags parsed, ```sql fences stripped, unknown verdict → None.
5. **`levels.py`** — `solve(q, level, ctx) -> dict` with `rounds: [{sql, error, n_rows, verdict, feedback}]`, `final_sql`, `stop` (`pass`, `ok`, `cap`, `one_shot`, `grade_unreadable`). Tests with a fake `llm`: L0 one call; L1 stops on PASS, regenerates with feedback, stops at 3; L2 makes no grader call, retries on error and on zero rows; L3 grader prompt carries the rows; history grows.
6. **`score.py`** — per question: `right`, `first_right`, `final_error`; aggregate: right, first-try right, fixed, broken, fooled (final PASS & wrong, among graded), false alarm (a right SQL graded not-PASS), rounds, cap hit, by difficulty. Tests counted by hand.
7. **`run.py`** — like topic 02's runner: `--level --set --repeats --limit --budget --workers --yes --dry-run`; smoke runs go to `runs/smoke/`. Tests: dry run makes no calls, over-budget aborts, ceiling refuses, an exception in one question is recorded and the run goes on.
8. **`report.py`** — `results.md` from the latest run per level per set. Tests: no runs → "not run yet"; one row per level.
9. **Runs** — smoke (5 questions, all levels, 1 repeat) → check cost → main ×3 → held-out ×3 (no changes after held-out starts).
10. **Write-up** — README + blog post in the human-style structure, process diagram, SVG charts.

## Rulings made while planning

- **Reasoning effort: the model default** (same as topics 01/02, which this topic is compared with), not "lowest" as the design said. `llm_call` has no effort setting, and changing the shared helper would touch every topic. Cost if wrong: slightly higher token cost; measured in the smoke run.
- **Gold rows are not stored in git** (some results are thousands of rows). They are computed from the read-only DBs at run time, cached per process.
- **An unreadable grader answer stops the loop** and is counted (`grade_unreadable`), rather than looping on empty feedback.
- **Added after the first results (user's request): levels 4 and 5, "teacher and student".** Same loops as 1 and 3, writer `gpt-6-luna`, grader `gpt-6.1-sol` (`Ctx.grader_model`). No prompt changed. Run on both sets, 3 repeats, after a smoke run whose measured cost (×1.5) replaces the upper-side estimate.
- **Bare verdicts are read.** The large grader answered `PASS` without tags; `read_grade` now accepts a verdict on the first line when there is no `<evaluation>` tag. The buggy teacher runs are in `runs/superseded/`.
