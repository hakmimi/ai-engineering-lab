# 07 · Where does text-to-SQL break: finding the tables, or writing the SQL? — design

Status: **approved** (2026-11-09)

## Intent and the why

Uber's [QueryGPT](https://www.uber.com/lb/en/blog/query-gpt/) turns questions into SQL with small agents: an intent agent picks
a business area, a **table agent** picks the tables (the user can fix them), a column-prune agent trims wide schemas, then the
query is written. LinkedIn ("Practical text-to-SQL for data analytics") and Pinterest ("How we built Text-to-SQL at Pinterest")
say the same thing in other words: **the hard part is finding the right tables, not writing SQL.**

Uber also describes a good way to check that, and never publishes the numbers:

- **"Vanilla" flow:** the system finds the tables itself and writes the query (the real product).
- **"Decoupled" flow:** the system is **given the right tables** and only writes (a human-in-the-loop stand-in).
- Per question they log intent, **table overlap** (0–1), **successful run**, **run has output**, and an **LLM-scored similarity**
  to the golden SQL (0–1). No accuracy, overlap, latency or cost numbers are reported, and the eval set size isn't given.

**The question:** with a known answer for every question, how much of text-to-SQL's error comes from **picking the tables**,
and how much from **writing the SQL**? And are Uber's cheap per-question signals (runs / has output / LLM similarity) a good
stand-in for "the answer is right"?

Not tested: the intent agent (a router; topic 01 already covers routing, and the user judged it not SQL-specific), column
pruning (the user's call: less interesting for now), the prompt enhancer, workspaces, the chat UI.

Same series rules as topics 01–06: real data with someone else's labels, levels that change one thing, a main set to tune on and
a held-out set never tuned on, offline tests, every number from run files. The README and blog keep the flow (claim → what I
expected → the test → main results → held-out results), but **with their own opening and topic-specific headings**: none of
the template wording of posts 01–05 ("How this started", "So, I came across…", "What X claims, and what it implies").

## Goals

- **Execution accuracy** per level, main and held-out, so the gaps between levels split the error into "tables" and "writing".
- **Table-agent quality:** table overlap (Uber's metric), all tables found, extra tables, tables from the wrong database.
- **Uber's signals vs the truth:** how well "runs", "has output" and the LLM similarity score agree with execution accuracy.
- Cost and time per question, per level.

## Non-goals

- Intent routing, column pruning, prompt enhancing, workspaces.
- Embedding search (topic 06 covers it); the table agent here reads the whole warehouse list in one prompt.
- Fixing loops (topic 05 covers them), bigger models, Claude models (series uses OpenAI via `shared/llm.py`).
- Beating the BIRD leaderboard.

## Anti-goals (would make this a failure even if it runs)

- The writer or table agent seeing the gold SQL, gold tables (except level B, by design), or gold rows.
- Any tuning after the held-out run starts.
- An API outage scored as "wrong" (counted separately, as in topics 04–05).
- SQL that can write to a database.
- Hand-typed numbers in README / results / blog.
- Presenting a 75-table warehouse as if it were Uber's scale (it's stated as a limit).

## Data

**BIRD Mini-Dev**, the same files as topic 05 (**CC BY-SA 4.0**): `topics/05-…/data/main.json` and `test.json`
(60 + 60 questions, split by database 6 / 5, stratified 18 / 30 / 12), and the 11 SQLite databases in topic 05's git-ignored
`data/raw/`. Nothing new is downloaded. Topic 05's level 0 is the same setup as level A here, so the numbers can be compared,
but level A is **re-run** here for a like-for-like day and code path.

**The warehouse (decided by the user):** all tables of all 11 databases in one list: **75 tables, 798 columns**. No two tables
share a name (checked). Each table is named `database.table` (as in a real warehouse's `schema.table`).

**Gold tables** per question: the tables the gold SQL **reads**, found by preparing the gold SQL in SQLite with an
**authorizer callback** (`set_authorizer`, `SQLITE_READ` events), not by parsing SQL text. Built once, stored in topic 07's own
`data/gold_tables.json` (table names only, no SQL; CC BY-SA 4.0 with a NOTICE).

Checked on 2026-11-09 (a dry check, no API calls): the authorizer works on all 120 gold queries. Gold tables per question:
main 1 / 2 / 3 / 4 tables = 13 / 34 / 12 / 1 questions; held-out = 12 / 33 / 10 / 5. In **3 main questions** (none held-out)
the gold tables are the whole database, so levels A and B give the writer the same schema there.

## Levels (decided)

The writer prompt is topic 05's level 0 prompt; only **which tables' schemas it is given** changes. Schema of a table =
its `CREATE TABLE` + first 3 rows (topic 05's format).

| Level | The writer gets | Uber's name | Calls / question |
|---|---|---|---|
| **A · whole database** | every table of the question's own database | (BIRD baseline) | 1 |
| **B · right tables** | only the gold tables | decoupled | 1 |
| **C · table agent, whole warehouse** | the tables a **table agent** picked from all 75 | vanilla | 2 |

- **Table agent (level C):** one call. It sees the question, the evidence hint, and a card per table in the warehouse:
  `database.table` + column names and types (no sample rows). It returns the tables it needs, any number, in a tag.
  Names that aren't in the warehouse are dropped and counted as **made-up tables**. If nothing valid is left, the writer gets
  no schema and that question is counted as **agent returned nothing** (and scored as written).
- The writer at level C gets the schemas of the picked tables, whatever database they're from. The SQL always runs on the
  question's database, so picking a table from another database usually means an error: it is scored wrong and also
  counted as **wrong database**.
- Model: `gpt-6-luna` for the writer and the table agent, lowest reasoning effort it accepts (as in topic 05).
- **3 repeats** per level per set.

## Metrics

| Metric | Meaning |
|---|---|
| **Right (EX)** | Result rows equal the gold rows as a set (topic 05's scorer). Overall and per difficulty |
| **Gap B − A** | What removing the extra tables is worth (does extra schema hurt?) |
| **Gap B − C** | What the table agent's mistakes cost: the "finding tables" share of the error |
| **Table overlap** | Level C: share of gold tables the agent picked (Uber's 0–1 metric), averaged |
| **All found / exact** | Level C: every gold table picked / picked set equals the gold set |
| **Extra tables, wrong database, made-up** | Level C: average extra tables; questions with a table from another database; names not in the warehouse |
| **Right when all found vs not** | Level C: accuracy split by whether the agent found every gold table |
| **Uber's signals** | For every final SQL at every level: **runs**, **has output** (>0 rows), **LLM similarity** 0–1 (a judge sees the question, the predicted SQL and the gold SQL, as Uber describes). Reported: how often each signal says "good" when the answer is wrong, and when it's right |
| **Time, cost** | Seconds and dollars per question, per level (agent and writer split at C) |

- **LLM similarity threshold:** "good" = score ≥ a threshold **picked on the main set** (the one that best matches EX there),
  then applied unchanged to the held-out set. The judge runs after all levels, on stored SQL; it never feeds back.
- Prediction timeout 10 s (counts as wrong); API outages left out and counted.

## What I expect (written before any run)

- **B beats A by a few points.** Less schema, less to get confused by. But BIRD databases are small (3–13 tables), so not by much.
- **The table agent finds every gold table most of the time** (maybe 85–90%): the 11 databases are very different topics,
  so the right database is easy to see. **C lands close to A.**
- So on 75 tables, **"finding tables" is a small share of the error**; most of it is writing. The companies' claim is about
  hundreds of thousands of tables, which this can't reach. I'll say so.
- **"Runs" and "has output" will say "good" to most wrong answers.** The LLM similarity will do better, but still pass a fair
  share of wrong ones (topic 05: the grader passed 82–94% of wrong SQL).

## Safety and money

- Databases opened **read-only** (`file:…?mode=ro`), timeout via progress handler (topic 05's code).
- `run.py`: estimate first, ask before spending, budget stop per command, **$10 ceiling for the topic**. A smoke run (5
  questions, all levels, 1 repeat, plus the judge on its SQL) comes first; its measured cost × 1.5 replaces the estimate.
- Rough estimate before the smoke run: A and B ≈ $0.07 each, C ≈ $0.30 (the agent reads ~10k tokens of cards), the judge
  ≈ $0.30. **≈ $1–2 in all.**

## Folder

```
07-text-to-sql-where-it-breaks/
├── README.md, results.md
├── design/            design.md, plan.md, process-diagram.html / .png
├── sqlblame/          gold_tables, warehouse, agent, levels, judge, score, run, report
├── data/              gold_tables.json, NOTICE.md   (questions + databases come from topic 05)
├── evals/             offline tests (no API calls; small SQLite fixtures built in the test)
└── runs/              git-ignored
```

Work happens directly in `C:\Workshop\ai-engineering-lab\topics` (no separate worktree), per the user.

## Left to the builder

- Exact wording of the table-agent and judge prompts (tags like topic 05: `<thoughts>`, `<tables>`, `<score>`).
- How topic 07 reuses topic 05's `sqlloop` modules (import vs copy), as long as level A's prompt and scorer are byte-for-byte
  topic 05's.
- Chart style for the blog (SVG, like topics 04 and 06).

## Calls I made (for review)

1. **Same 60 + 60 questions and databases as topic 05**, so the numbers line up with it.
2. **Level A re-run**, not copied from topic 05.
3. **Gold tables from SQLite's authorizer**, not a SQL parser.
4. **Table names carry the database** (`database.table`): realistic, but it makes the agent's job easier.
5. **The table agent picks any number of tables**, no top-K.
6. **Cards for the agent = names and types only**; the writer still gets 3 sample rows.
7. **LLM similarity threshold picked on main, frozen for held-out.**
