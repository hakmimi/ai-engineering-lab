# Topic 09: Workflow or free agent: which one gives the right answer, and the same answer twice? (BIRD Mini-Dev) — Design

Date: 2026-11-10
Status: **approved** (2026-11-10, in chat)
Folder: `topics/09-agentic-patterns-bird/` in `hakmimi/ai-engineering-lab`
Source article: Safe Software (FME), "AI Agentic Workflows: Tutorial & Best Practices"
https://fme.safe.com/guides/ai-agent-architecture/ai-agentic-workflows/ (no author or date on the page; image paths say May 2025)
Data: BIRD Mini-Dev (Li et al., 2023/2024), https://github.com/bird-bench/mini_dev, CC BY-SA 4.0, the same pinned files
as topics 05 and 07 (nothing new downloaded).

## 1. Intent

The guide walks through five patterns for building with LLMs: a **single agent**, **routing / handoff** (also to a human),
**parallelization**, **orchestrator-worker** (a planner sends work to a dynamic number of workers) and
**evaluator-optimizer**. Its main claim: "In most cases, an agentic workflow will provide better reliability and
reproducibility than an AI agent." It also says agents "generally increase the latency" and cost more tokens.
It shows no numbers. Its LangGraph code is partial. It uses GPT-4o, LangGraph and LangChain.

This topic builds all five patterns, plus a free agent with tools, on one task with someone else's answer key:
text-to-SQL on BIRD Mini-Dev, over a "warehouse" of all 11 databases (75 tables). BIRD's gold SQL decides right / wrong
by the rows it returns. We never write the key.

The question for the reader: **does a fixed workflow beat a free agent on right answers, on giving the same answer
every time, and on cost and time?**

This is the **small version** (agreed in chat 2026-11-10): one task, one cheap model, 60 + 60 questions, 3 repeats.

## 2. The claims under test (decided)

| # | Article's claim | How we test it |
|---|---|---|
| 1 | Workflows are more **reliable** than an agent | Right answers, levels 1–4 vs level 5 |
| 2 | Workflows are more **reproducible** | Same answer in all 3 repeats, levels 1–4 vs level 5 |
| 3 | Agents **increase latency** and use more tokens | Seconds and $ per question, level 5 vs the rest |
| 4 | Each pattern helps (routing narrows context, parallel votes, orchestrator splits, evaluator fixes) | Each level vs level 1 |
| 5 | Handoff to a human helps when the router is unsure | Level 1h: share handed off, right on the rest |

Not tested: LangGraph itself, FME's platform, GPT-4o (see model below), other tasks.

## 3. The data (decided)

BIRD Mini-Dev SQLite: 500 questions on 11 databases, each with a hint ("evidence"), gold SQL written by the BIRD
authors, and a difficulty. Topic 05 drew 60 + 60 questions (split by database, seed 2026, stratified
simple 18 / moderate 30 / challenging 12); topics 07 and 09 reuse them unchanged.

| Set | Questions | Databases |
|---|---|---|
| Main | 60 | california_schools, codebase_community, debit_card_specializing, european_football_2, formula_1, thrombosis_prediction |
| Held-out | 60 | card_games, financial, student_club, superhero, toxicology |

The warehouse every level starts from is all 11 databases (75 tables) in both sets, so the router can be wrong.

## 4. The levels (decided)

The same writer prompt as topics 05 and 07 (question + hint → `<sql>`) and the same schema text
(CREATE TABLE + 3 example rows per table) are used everywhere a level writes SQL. Each level changes one thing.

| Level | Pattern | What it does |
|---|---|---|
| **0 · one prompt** | single agent, no workflow | One call sees all 75 tables (schema + example rows) and answers `<database>` + `<sql>` |
| **1 · routing** | routing | A router sees one line per table (`db.table: columns`) and names the database; a specialist writer sees only that database |
| **1h · routing + handoff** | routing, handoff to a human | Same, but the router may answer HUMAN when unsure. Handoffs are counted; a stand-in human routes them to the right database |
| **2 · parallel vote** | parallelization | Router, then 3 writers at once; their queries are run and the largest group with the same rows wins |
| **3 · orchestrator-worker** | orchestrator-worker | Router, then a planner splits the question into 1–4 sub-questions; one worker writes SQL per sub-question (at once); with more than one, a final call combines them into one query, seeing each worker's SQL and first rows |
| **4 · evaluator-optimizer** | evaluator-optimizer | Router, then topic 05's level 3 loop: writer + grader who sees the result rows, up to 3 rounds |
| **5 · free agent** | AI agent | One model with tools: `describe(db)`, `run_sql(db, sql)`, `answer(db, sql)`; it decides the steps, at most 10 |

Level 0 is the "no workflow" baseline; there is no free no-model level (a rule cannot write SQL).

## 5. Data sets (decided)

- Same sets as topics 05/07 (split by database before drawing, seed 2026). Held-out = 5 databases never seen in tuning.
- **No leaks:** the model sees the question, the hint and the schema. Gold SQL, difficulty and the right database never
  reach a prompt (a test checks this). The level 1h stand-in human uses the right database by design and is labelled so.
- **Spot check:** skipped by the author's choice (2026-11-10); the key is BIRD's and was used in topics 05 and 07.
  Stated in Limitations.

## 6. What is measured (decided)

Per level and set, **3 repeats**.

| KPI | Meaning |
|---|---|
| **Right** | The final query returns the same set of rows as the gold query (BIRD's rule) |
| **Same answer 3/3** | All 3 repeats end with the same outcome (same rows, or the same failure) |
| **Right 3/3** | All 3 repeats right |
| Right database | The level picked the question's own database (every level except 1h's handoffs) |
| Handoff share, right on the rest | Level 1h only |
| API errors | Kept apart: never scored as a wrong answer, left out of rates |
| $, seconds, calls | Per question; seconds are wall-clock, so parallel calls overlap |

**What the article suggests:** workflows are more reliable and reproducible; agents are slower and cost more.
**What I expect** (the author, 2026-11-10, before any run): the free agent is **less right and less stable**;
workflows win on right answers and on giving the same answer each run.

`results.md` is generated from run files only.

## 7. How it gets made

Decided (carried over):
- Python, pytest, offline tests with a fake `llm_call`. Calls through `shared/llm.py`; run files via `shared/runs.py`;
  graphs via `shared/charts.py`; post via `shared/publish_post.py`.
- Runner flags: `--level --set --repeats --limit --budget --workers --yes --dry-run`.
- Keys only in the git-ignored `.env`. Worktree `C:\Workshop\ai-engineering-lab-topic09`, branch `topic-09-agentic-patterns-bird`.
- Reuses topic 05 (`sqlloop`: writer prompt, schema text, SQL runner, row comparison, evaluator loop) and topic 07
  (`sqlblame.warehouse`: table cards, 11-database list).

Claude's calls (the author can change them):
- **Model:** `gpt-6-luna` (the series' cheap model; the article's GPT-4o is retired). Same model in every role.
- **Level 0 sees example rows too**, so it differs from level 1 only in routing, not in what a table looks like.
- **Agent tools are text actions** (`<tool>…</tool>`), not native function calling, so every level uses the same
  `llm_call`. Each step re-sends the whole transcript. Stated in Limitations.
- **Vote ties** go to the group holding the earliest writer. Queries that fail never win a vote unless all fail.
- **"Same answer" outcomes:** the database plus a hash of the result rows (order and duplicates ignored), or
  "sql error", or "no answer". After a level 1h handoff the final answer still counts.
- **The agent starts with the same table cards as the router** (`db.table: columns`), so neither starts with more
  (from the fresh review). An `answer` without SQL, or with an unknown database, is shown back to it as an
  observation, not taken as final.
- **Time is the median** seconds per question (a smoke run had two single API calls of about 400 s), timed over the
  level only; running and scoring the final SQL is not counted. Gold SQL runs once before any model call.
- **Budget:** the upper-side guess was about $10 for all 14 runs (no caching, long answers). 8-question smoke runs
  measured about $2.5 for all 14 with a 1.5× margin, so that decides; per command `--budget` $1; topic ceiling **$5**.
- **Package:** `agentflow`.

## 8. Goals, non-goals, anti-goals

Goals: the five patterns and a free agent on the same questions, model and writer prompt; right / same answer / $ / s.

Non-goals: beating BIRD, LangGraph, bigger models, tuning prompts per level.

Anti-goals: tuning on held-out; the model seeing gold SQL or the right database; API failures scored as wrong;
SQL that can write (connections are read-only); hand-typed numbers.

## 9. Deliverables

`README.md`, `design/` (this file, plan, process diagram), `data/NOTICE.md`, `agentflow/`, `evals/`, `charts/`,
`results.md`.

## 10. Left to the builder

Prompt wording for the router, planner, combiner and agent (written on the main set only), worker counts in tests,
chart layout.
