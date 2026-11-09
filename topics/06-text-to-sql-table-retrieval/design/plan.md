# Topic 06 table finding — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Measure how often keyword search, embedding search, "embedding top 20 → LLM picks 7", and the same with column descriptions find every table a LiveSQLBench-Large question needs, out of a pool of 971 tables.

**Architecture:** `build_data` turns the pinned raw files into `data/tables.json` (971 tables with columns and descriptions), `data/main.json` / `data/test.json` (questions, opaque ids) and a git-ignored `data/key.json`. Four levels share one search layer (BM25, cached embeddings) and one re-rank step. A runner saves run files through `shared/runs.py`; a report builds `results.md` and SVG charts through `shared/charts.py`.

**Tech Stack:** Python 3, pytest, `openai` SDK (embeddings), `shared/llm.py` (re-ranker), no new dependencies.

**Spec:** `topics/06-text-to-sql-table-retrieval/design/design.md`

## Global Constraints

- Pool = all 971 tables for every question and every level. Hand-off size k = 7; re-rank input = top 20.
- Split: 18 databases sorted, shuffled with `random.Random(2026)`, first 9 = group A (main), rest = group B (test).
- Main 173 questions, test 159 (all SELECT questions in the Snowflake qrels). Ids `m-001…`, `t-001…` in sorted source-id order.
- Table ids are `db.table` with the table name lowercased; matching is case-insensitive.
- Never fetch, store or show gold SQL. `data/key.json` and `data/raw/` are git-ignored.
- Re-ranker model from env `RERANK_MODEL`, default `gpt-6-luna`; embeddings `text-embedding-3-small` at $0.02 per M tokens.
- Levels 0–1: 1 repeat. Levels 2–3: 3 repeats. Per command `--budget` default $1; topic ceiling $5 (`shared.runs`).
- Unreadable re-ranker answer → picks = [] (found nothing), status "error". API exception → status "failed", not scored.
- Tests are offline; root `conftest.py` blocks real clients.

## Review Focus

1. Re-ranker names a table in other case, with quotes, schema prefix or only the bare table name → still matched (test in Task 4).
2. Re-ranker repeats a table or returns more than 7 / fewer than 7 → deduped, cut, or filled from search order with `filled` recorded (Task 4).
3. Re-ranker names a real table that was not among its 20 → counted as made up, not as a pick (Task 4).
4. A description card longer than the embedding limit → truncated to 24,000 characters before embedding, never an API error (Task 3).
5. Card format changed after embeddings were cached → cache key includes model and text hash, so stale vectors are never reused (Task 3).

---

### Task 1: Data build

**Files:** Create `tablefind/__init__.py`, `tablefind/build_data.py`, `tablefind/data.py`, `evals/td_helpers.py`, `evals/test_td_data.py`; modify `pyproject.toml` (add topic 06 to `pythonpath` and `testpaths`).

**Interfaces:**
- Produces: `parse_schema(text: str) -> dict[str, list[tuple[str, str]]]` (table name as written → [(column, type)]; only `CREATE TABLE … );` blocks, sample rows ignored);
  `parse_meanings(d: dict) -> dict[tuple[str, str], str]` ((table lower, column lower) → text; dict values use their `column_meaning`);
  `split_dbs(dbs: list[str], seed=2026) -> tuple[list[str], list[str]]`;
  `build(raw: Path, out: Path) -> dict` (writes `tables.json`, `main.json`, `test.json`, `key.json`, `build_log.json`; returns counts);
  `data.load_tables() -> list[Table]`, `data.load_questions(set) -> list[Question]`, `data.load_key(set) -> dict[str, set[str]]`.
  `Table(id, db, name, columns: list[Column])`, `Column(name, type, desc)`, `Question(qid, text)`.

- [ ] Step 1: tests with a tiny fake raw folder (2 dbs, 3 tables, 3 questions) in `td_helpers.make_raw(tmp_path)`:
  `test_parse_schema_skips_sample_rows`, `test_parse_meanings_handles_jsonb_dict`, `test_split_dbs_is_seeded_and_disjoint`,
  `test_build_ids_are_opaque_and_key_is_separate` (questions files hold only `qid`,`text`; key maps qid → `db.table` lowercase),
  `test_build_fails_when_a_gold_table_is_not_in_the_pool` (ValueError), `test_key_and_raw_are_gitignored` (reads repo `.gitignore`).
- [ ] Step 2: run, expect ImportError. Step 3: implement. Step 4: tests pass.
- [ ] Step 5: run `python -m tablefind.build_data` on the real raw folder; expect 971 tables, 173 main, 159 test. Commit (data files except key).

### Task 2: Cards and BM25 (level 0)

**Files:** Create `tablefind/cards.py`, `tablefind/search.py`, `evals/test_td_search.py`.

**Interfaces:**
- Produces: `card(t: Table, with_desc: bool) -> str` (`Table: db.table` line, then one line per column `name type` and, with descriptions, ` — desc`);
  `tokens(text: str) -> list[str]` (lowercase; splits snake_case, CamelCase, digits);
  `BM25(docs: list[list[str]], k1=1.5, b=0.75).scores(query_tokens) -> list[float]`;
  `top_k(scores: list[float], ids: list[str], k: int) -> list[str]` (ties broken by id).
- [ ] Tests: `test_tokens_split_camel_and_snake` (`"ArtifactTag fund_flux"` → `["artifact","tag","fund","flux"]`), `test_card_with_and_without_desc`,
  `test_bm25_prefers_matching_doc`, `test_top_k_stable_ties`. RED → implement → GREEN → commit.

### Task 3: Embeddings with a disk cache (level 1)

**Files:** Create `tablefind/embed.py`, `evals/test_td_embed.py`.

**Interfaces:**
- Produces: `EMBED_MODEL = "text-embedding-3-small"`, `EMBED_USD_PER_M = 0.02`, `MAX_CHARS = 24000`;
  `Embedder(cache_dir: Path, client=None, model=EMBED_MODEL)` with `.embed(texts: list[str]) -> list[list[float]]` and `.cost_usd` (cache misses only, from `usage.total_tokens`), batches of 100;
  `cosine_top_k(q: list[float], vecs: list[list[float]], ids: list[str], k: int) -> list[str]`.
- [ ] Tests with a fake client: `test_cache_hit_makes_no_call`, `test_cache_key_changes_with_text_and_model`, `test_long_text_is_truncated_before_call`,
  `test_cost_counts_only_misses`, `test_cosine_top_k`. RED → implement → GREEN → commit.

### Task 4: Re-ranker prompt and answer parsing (level 2–3 core)

**Files:** Create `tablefind/rerank.py`, `evals/test_td_rerank.py`.

**Interfaces:**
- Produces: `SYSTEM` (the job: pick the 7 tables a SQL query for the question needs, from the cards shown; answer `<tables>` one `db.table` per line, most needed first);
  `rerank_prompt(question: str, cards: list[str]) -> str`;
  `parse_picks(text: str, shown: list[str], k=7) -> Picks` with `Picks(ids: list[str], made_up: list[str], status: "ok"|"error")`;
  `fill(picks: list[str], ranked: list[str], k=7) -> tuple[list[str], int]` (returns ids and how many were filled).
- [ ] Tests: `test_parse_matches_case_quotes_and_bare_names` (`"Archeology_Scan_Large.\"Projects\""` and `projects` → `archeology_scan_large.projects`),
  `test_parse_dedupes_and_cuts_to_k`, `test_parse_flags_unshown_names_as_made_up`, `test_parse_without_tag_is_error`,
  `test_fill_tops_up_from_search_order`. RED → implement → GREEN → commit.

### Task 5: Levels

**Files:** Create `tablefind/levels.py`, `evals/test_td_levels.py`.

**Interfaces:**
- Consumes: Tasks 1–4.
- Produces: `Ctx(tables, embedder, model, tracker)`; `prepare(ctx)` builds BM25 and the two card embeddings once;
  `run_level(level: str, q: Question, ctx) -> dict` with keys `picks` (7 ids), `top20` (levels 2–3), `made_up`, `filled`, `status`.
  Level 2 searches and shows plain cards; level 3 searches and shows description cards. Re-rank call: `llm_call(prompt, cached_system=SYSTEM, label=f"l{level}:{qid}", model=ctx.model, tracker=ctx.tracker, max_tokens=600)`.
- [ ] Tests with fake embedder and fake `llm_call` (monkeypatched): `test_level0_returns_7`, `test_level1_uses_question_embedding`,
  `test_level2_reranks_only_top20_plain_cards`, `test_level3_shows_descriptions`, `test_unreadable_answer_finds_nothing`. RED → GREEN → commit.

### Task 6: Scoring

**Files:** Create `tablefind/score.py`, `evals/test_td_score.py`.

**Interfaces:**
- Produces: `Scores(n, all_found, recall, ceiling, made_up, errors, failed)` (ceiling and made_up are None for levels 0–1);
  `score(answers: dict[str, dict], key: dict[str, set[str]]) -> Scores` (failed answers excluded from n; errors count as nothing found);
  `by_gold_size(answers, key) -> dict[str, float]` (all found for questions needing 1, 2, 3+ tables).
- [ ] Tests: `test_all_found_needs_every_gold_table`, `test_recall_is_per_question_mean`, `test_failed_excluded_error_counts_as_miss`,
  `test_ceiling_uses_top20`, `test_by_gold_size_buckets`. RED → GREEN → commit.

### Task 7: Runner

**Files:** Create `tablefind/run.py`, `evals/test_td_run.py`.

**Interfaces:**
- Consumes: Tasks 5–6, `shared.runs.spent_so_far/over_ceiling/save_run`, `shared.llm.PRICES`.
- Produces: CLI `--level 0|1|2|3 --set main|test --repeats --limit --budget 1.0 --workers 8 --yes --dry-run --runs-dir`;
  `estimate_cost_usd(level, questions, tables, model, repeats) -> float` (chars ÷ 4 for the 20 cards + question + SYSTEM, 300 output tokens; plus embedding of uncached texts);
  run file payload: `model, embed_model, limit, partial, n, cost_usd, repeats: [{answers, seconds, cost_usd, errors}]`.
- [ ] Tests: `test_dry_run_writes_nothing`, `test_ceiling_blocks_run`, `test_api_exception_is_failed_not_scored`, `test_budget_stop_marks_partial`. RED → GREEN → commit.

### Task 8: Report, charts, process diagram

**Files:** Create `tablefind/report.py`, `evals/test_td_report.py`, `design/process-diagram.html` + `.png`.

**Interfaces:**
- Consumes: `shared.runs.latest_run`, `shared.charts.bar_chart/pct/money`, Task 6.
- Produces: `results.md` (per set: a table of levels × all found, recall, ceiling, made up, errors, failed, $/question, s/question; "not run" for missing levels; the by-gold-size table for the test set; one line "Article says: recall goes up with the re-ranker and with descriptions (no numbers) / We got …");
  charts `all-found.svg` (main and held-out panels, all found + recall per level), `ceiling.svg` (levels 2–3: found in top 20 vs found in the 7), `by-gold-size.svg` (held-out), `cost-per-question.svg`.
- [ ] Tests on fake run files: `test_report_says_not_run`, `test_report_ignores_smoke_runs`, `test_charts_written_only_with_data`. RED → GREEN → commit.

### Task 9: Spot-check sheet

**Files:** Create `tablefind/spot_check.py`, `spot-check.md`.
- [ ] Draw 20 main questions with `random.Random(2026)`: 7 needing 1 table, 7 needing 2, 6 needing 3+. For each: the question, the gold tables with their columns (plain card), a ✓/✗ column. Commit.
