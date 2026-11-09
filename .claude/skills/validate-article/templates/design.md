# Topic NN: <the reader's question, in plain words> (<dataset>) — Design

Date: YYYY-MM-DD
Folder: `topics/NN-<slug>/` in `hakmimi/ai-engineering-lab`
Source article: <publisher>, "<title>"
<url>
Data: <dataset> (<authors, year>), <url>, <licence>, pinned at <commit / version / download date>

## 1. Intent

<What the article does, in 3-5 plain sentences. Quote its own caveats word for word.>

<What this topic measures that the article doesn't. Who writes the answer key (never us).>

The question for the reader: **<one sentence>**

This is the **<small / full> version** (agreed in chat YYYY-MM-DD): <what is in, what is out>.

## 2. The claims under test (decided)

| # | Article's claim | How we test it |
|---|---|---|
| 1 | <claim, close to the article's words> | <KPI and level that answers it> |

Not tested (out of scope): <platform features, things the data can't show>.

## 3. The data (decided)

<What the dataset is, who labelled it, how the labels were made. Count what exists, on the pinned version.>

| Label / group | Count | What it means for us |
|---|---|---|

**Left out:** <what and why>.

## 4. The levels (decided)

Each level adds one step.

| Level | What it does |
|---|---|
| **0 · <no-model baseline>** | <rules / heuristics / simplest thing, no cost> |
| **1 · One prompt** | <the naive model version> |
| **2 · The article's way** | <the article's method, as close as possible> |

## 5. Data sets (decided)

- **Split first, then draw**, with seed 2026. <How the split keeps main and held-out apart: different items, different sources, different styles.>
- **Main set (tuning allowed):** <N per group>.
- **Held-out set (never tuned on):** <N per group, and what is new in it>.
- **No leaks:** the model sees only <...>. Labels sit in a separate `key.json` the run code never reads. Ids are opaque.
- **Spot check:** before any run, the author checks 10 + 10 items in `spot-check.md`. The key itself is not changed.

## 6. What is measured (decided)

Per level and set, averaged over **3 repeats** (level 0 needs one).

| KPI | Meaning |
|---|---|
| <main KPI> | <plain words> |
| Errors / not reviewed / API failures | Kept apart: an API failure is never scored as a model mistake |
| $, seconds, calls | Per item, list prices from `shared.llm.PRICES` |

**What the article suggests:** <numbers or statements from the article>.
**What I expect** (the author's guesses, written before any run): <...>.

`results.md` is generated from run files only.

## 7. How it gets made

Decided (carried over from earlier topics):
- Python, pytest, offline tests with a fake `llm_call`. LLM calls through `shared/llm.py`.
- Runner: `--level`, `--set`, `--repeats`, `--limit`, `--dry-run`, `--yes`, `--budget`. Run files via `shared/runs.py`, under `runs/` (git-ignored).
- Graphs via `shared/charts.py`. Blog post via `shared/publish_post.py`.
- Keys only in the git-ignored `.env`. Work in a separate worktree and branch.

Claude's calls (the author can change them):
- **Model:** <id, and why>.
- **Budget:** estimate <$X>; per command `--budget` $1; topic ceiling **$5**.
- **Folder / package / branch:** <...>.

## 8. Goals, non-goals, anti-goals

Goals:
- <...>

Non-goals:
- <...>

Anti-goals (a failure even if it runs):
- Tuning anything on the held-out set, or rules built from held-out text.
- The model seeing any label or answer field.
- Invented or estimated results. If a run did not happen, `results.md` says so.
- Polished, AI-sounding prose.

## 9. Deliverables

`README.md` (blog structure), `design/` (this file, plan, process diagram), `data/` (sets, key, NOTICE),
`<package>/`, `evals/`, `charts/`, `results.md`, `spot-check.md`.

## 10. Left to the builder

- <details that don't change what gets built>
