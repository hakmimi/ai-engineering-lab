# Topic 06: Does an LLM re-ranker find the right tables? (LiveSQLBench-Large) — Design

Date: 2026-11-09
Folder: `topics/06-text-to-sql-table-retrieval/` in `hakmimi/ai-engineering-lab`
Source article: LinkedIn Engineering, "Practical text-to-SQL for data analytics" (Dec 2024)
https://www.linkedin.com/blog/engineering/ai/practical-text-to-sql-for-data-analytics
Data:
- Questions, schemas, column descriptions: **LiveSQLBench-Large-v1** (BIRD team @ HKU + Google Cloud), https://huggingface.co/datasets/birdsql/livesqlbench-large-v1 , **CC BY 4.0**, pinned at `a418e108d5cbb4cf9b783a928eff5e924ad2460d`
- Answer key (which tables each question needs): **SQL-Schema-Retrieval**, `livesqlbench_large_table` (Zeng et al., Snowflake, 2026, arXiv:2607.13311), https://huggingface.co/datasets/Snowflake/SQL-Schema-Retrieval , "follow each source's licence", pinned at `e60c65cf9aeab052f0747902d31db1807099fa23`

## 1. Intent

LinkedIn built **SQL Bot**, which turns questions into SQL over a warehouse of millions of tables. They say the hard part
is not writing SQL but **finding the right tables**. Their answer: embedding search pulls the **top 20 tables**, then
**an LLM re-ranker picks 7** for the query writer. They also say **table descriptions** and **example queries** help.
Their Figure 6 shows table recall going up as each piece is added, **but gives no numbers**, the benchmark is private
(130 questions written by their experts), and the models are not named.

Topic 06 **puts numbers on that graph** with public data and an answer key nobody here wrote.

The question for the reader: **if my warehouse has hundreds of tables, does "search 20, let an LLM pick 7" actually find the
tables my question needs, and do column descriptions help?**

This is the **small version**: table finding only. Column picking, SQL writing, validators and the UI are out.

## 2. The claims under test (decided)

| # | Article's claim | How we test it |
|---|---|---|
| 1 | Embedding search alone isn't enough; an LLM re-ranker (top 20 → 7) finds the right tables more often | Level 1 vs level 2: **all found** and **table recall** at 7 |
| 2 | Table/column descriptions raise table recall | Level 2 vs level 3 (same, with the dataset's column descriptions) |
| 3 | (Their metric) the re-ranker must not invent tables | **Made-up tables**: names the LLM returns that are not among the 20 it was shown |
| 4 | It's practical: cheap and fast enough per question | $ and seconds per question |

Not tested: example queries (no query logs; and the held-out databases have no past queries by design), personalization
(org chart, access history), the knowledge graph, column re-ranking, query writing, validators and self-correction
(topic 05 covers a fix loop), the UI, adoption and survey numbers, the LLM judge.

## 3. The data (decided)

**LiveSQLBench-Large-v1**: 18 "industrial" databases (archeology scans, solar plants, cross-border payments …),
**971 tables**, about 54 tables and 1,000 columns each. Column names are enterprise-messy on purpose
(`vesseltag` is the project name, `fundflux` the funding source). Every column has a description written by the BIRD
team (`*_column_meaning_base.json`), e.g. `projects.vesseltag → "Project name or designation label."`

**Answer key:** Snowflake's SQL-Schema-Retrieval parsed each question's **gold SQL** (written by the BIRD annotators) and
lists the tables it uses. We use their `livesqlbench_large_table` qrels: **332 questions** (the SELECT tasks), 1 to 8 gold tables
each. Every gold table is in the question's own database (checked).

**Left out:** the 148 Management (CRUD) tasks (no gold tables published), BEAVER (licence unclear: NC-ND on the paper),
Spider and BIRD-dev (6–7 tables per database: too easy to tell anything apart).

**Note on the key:** the BIRD team gates the gold SQL behind an email to keep it out of model training data. We never fetch
or store gold SQL. The gold *table lists* are already public in Snowflake's release; `build_data.py` downloads them at the
pinned commit, and **`key.json` is not committed** (my call, to respect the BIRD team's intent). Everything else is committed.

## 4. The levels (decided)

Every level searches **one pool of all 971 tables** (the whole "warehouse", as at LinkedIn) and hands **7 tables** to the
(imagined) query writer.

| Level | What it does |
|---|---|
| **0 · Keyword search** | BM25 over the table cards (name + column names), top 7. No model, no cost. |
| **1 · Embedding search** | Embed the question and each table card, top 7 by cosine. |
| **2 · The article's way** | Embedding top 20, then an LLM reads the 20 cards and picks 7. |
| **3 · + descriptions** | Level 2, with each card also carrying the column descriptions (both for search and for the re-ranker). |

A **table card** is `database.table` plus its columns with types (from `*_schema.txt`). Level 3's card adds the
description of each column. No sample rows.

## 5. Data sets (decided)

- **Split first, then draw:** the 18 databases are shuffled with seed 2026 and cut 9 / 9.
- **Main set (tuning allowed):** all **173** questions from group A.
- **Held-out set (never tuned on):** all **159** questions from group B (new databases, new domains).
- The pool is always all 971 tables, for both sets.
- Group B happens to be harder (3.1 gold tables per question vs 2.3; only 21 single-table questions vs 66). So **levels are
  compared within a set**, never main vs held-out.
- **No leaks:** the model sees only the question text and the table cards. Question ids are opaque (`m-001`, `t-001`).
- **Spot check:** before any paid run, the author checks 20 main-set questions against their gold tables in `spot-check.md`.

## 6. What is measured (decided)

Levels 0 and 1 give the same answer every time: 1 run. Levels 2 and 3: **3 repeats**, averaged.

| KPI | Meaning |
|---|---|
| **All found** (main KPI) | Share of questions where **every** gold table is in the 7. If one is missing, the SQL can't be right |
| **Table recall** | Share of gold tables found, averaged over questions |
| **Search ceiling** | For levels 2–3: all found within the top 20 (the re-ranker can't find what search didn't bring) |
| **Made-up tables** | Share of re-ranker answers naming a table not in its 20 |
| Errors / API failures | Unreadable answers count as "found nothing"; API failures are kept apart and not scored |
| $, seconds | Per question, list prices |

**What the article suggests:** recall goes up with the re-ranker, and again with descriptions (Figure 6, no numbers).
**What I expect** (the author's guesses, before any run): _to fill in at stop 2_.

`results.md` and `charts/*.svg` are generated from run files only.

## 7. How it gets made

Decided (carried over):
- Python, pytest, offline tests with fakes. LLM calls through `shared/llm.py`; run files and budget via `shared/runs.py`;
  graphs via `shared/charts.py`; blog via `shared/publish_post.py`.
- Runner: `--level 0|1|2|3 --set main|test --repeats --limit --budget --dry-run --yes`.
- Branch `topic-06-text-to-sql-table-retrieval`, worktree `C:\Workshop\ai-engineering-lab-topic06`.

Claude's calls (the author can change them):
- **Re-ranker model: `gpt-6-luna`** (the article names none; it's the cheap tier we used in topic 4, and the Anthropic account
  had no credit then). `claude-haiku-5-5` if the author prefers and the account has credit.
- **Embeddings: OpenAI `text-embedding-3-small`** ($0.02 per M tokens), cached to disk so tables are embedded once.
- **BM25:** a small in-repo implementation (no new dependency).
- **Budget:** about **$1.50** (re-ranker: 332 questions × 2 levels × 3 repeats; level 3 prompts ≈ 12k tokens).
  Checked by `--dry-run` and a 5-question smoke run first. Per command `--budget` $1, topic ceiling $5.

## 8. Goals, non-goals, anti-goals

Goals:
- The first public numbers for "search 20, LLM picks 7" against plain search, on an enterprise-shaped schema.
- Show what descriptions add, and what keyword search alone gets for free.

Non-goals: building SQL Bot, writing or running SQL, beating the Snowflake paper's embedders, personalization.

Anti-goals (a failure even if it runs):
- Tuning the card format, prompt or k on the held-out set.
- The model seeing gold tables, gold SQL or the knowledge base answers.
- Committing gold SQL or `key.json`.
- Invented or estimated results.

## 9. Deliverables

`README.md` (blog structure), `design/` (this file, plan, process diagram), `data/` (sets, table cards, NOTICE; `raw/`
and `key.json` git-ignored), `tablefind/` (package), `evals/`, `charts/`, `results.md`, `spot-check.md`.

## 10. Left to the builder

- Re-ranker prompt wording and answer tags; what happens when it returns fewer or more than 7 (pad from search order / cut).
- Matching returned names to tables (case, quotes, `db.table` vs `table`).
- BM25 tokenisation (split snake_case and CamelCase).
