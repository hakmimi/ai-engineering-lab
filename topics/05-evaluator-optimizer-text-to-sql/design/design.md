# 05 · Evaluator-optimizer on text-to-SQL — design

Status: **draft, waiting for approval** (2026-11-09)

## Intent and the why

Anthropic's cookbook page [Evaluator-optimizer](https://platform.claude.com/cookbook/patterns-agents-evaluator-optimizer) shows one LLM writing an answer and a second LLM grading it (PASS / NEEDS_IMPROVEMENT / FAIL plus feedback), in a loop until PASS.

What the page shows, and doesn't:

- **One example:** a MinStack class (push, pop, getMin in O(1)).
- **The grader only reads the code.** Nothing is run or tested.
- **The loop is `while True`.** There is no round limit.
- **No metrics.** No accuracy, cost or time. The shown run stops after round 2, so we never see a PASS.
- **Its rule for a good fit:** "LLM responses can be demonstrably improved when feedback is provided" and "The LLM can provide meaningful feedback itself."

The page asserts those two conditions; it never tests them. This topic does, on a job where right and wrong can be checked by running code.

**The question:** on real text-to-SQL questions with known answers, does the evaluator-optimizer loop give more right answers than one prompt? When the AI grader says PASS, is the answer actually right? And does feedback from **running the SQL** beat feedback from **an AI reading it**?

Same series as topics 01–04: real data with someone else's labels, levels that add one thing at a time, a main set to tune on and a held-out set that is never tuned on, offline tests, every number from run files, and the blog / README in the human-style structure (How this started → What Anthropic claims → My experiment → How I measure it → Results → Key takeaways → Limitations → Technical walkthrough).

## Goals

- Measure **execution accuracy** (does the SQL return the right rows) per level, on a main and a held-out set.
- Measure the grader itself: **PASS on a wrong answer** (fooled), and **NEEDS_IMPROVEMENT on a right answer** (false alarm).
- Measure what the loop does: answers it **fixed** (wrong → right), answers it **broke** (right → wrong), rounds used, how often it hit the cap.
- Cost and time per question, per level.

## Non-goals

- Beating the BIRD leaderboard, or schema linking, retrieval or fine-tuning.
- The efficiency metric (R-VES) and Soft F1.
- MySQL / PostgreSQL. SQLite only.
- Claude models (the series uses OpenAI via `shared/llm.py`; a Claude rerun is a "next time").

## Anti-goals (would make this a failure even if it runs)

- Any tuning, prompt change or rule change after the held-out run starts.
- A grader or generator that can see the gold SQL or the gold result.
- A loop without a cap, or a timeout / API outage scored as "the model was wrong" without being counted separately.
- SQL that can write to the database.
- Numbers typed by hand into the README, results or blog.

## Data

**BIRD Mini-Dev** ([github.com/bird-bench/mini_dev](https://github.com/bird-bench/mini_dev), Hugging Face `birdsql/bird_mini_dev`), **CC BY-SA 4.0**.

- 500 questions over **11 SQLite databases**, tagged simple (~30%), moderate (~50%), challenging (~20%).
- Each item: `db_id`, `question`, `evidence` (a short hint written by the annotators, e.g. "eligible free rate = Free Meal Count / Enrollment"), gold `SQL`, `difficulty`.
- Source file: `minidev.zip` from the official link (`bird-bench.oss-cn-beijing.aliyuncs.com/minidev.zip`, **801 MB**), which holds the original 500-question `mini_dev_sqlite.json` and the 11 SQLite databases. (The Hugging Face copy has the questions but not the databases, and its newer V2 has 780 items; I use the original 500.) **It stays out of git:** downloaded to `data/raw/` (git-ignored). Only the drawn question sets and a NOTICE go into git (share-alike: those files are CC BY-SA 4.0 too).

**Sets (my call):**

- Split the 11 databases with a fixed seed (2026) into **group A (6 DBs)** and **group B (5 DBs)**.
- **Main set:** 60 questions from group A. **Held-out set:** 60 questions from group B.
- Both drawn stratified by difficulty: **18 simple, 30 moderate, 12 challenging**.
- So the held-out set has databases, tables and column names the prompts were never tuned on.

**Gold results** are computed once by running each gold SQL (read-only, 30 s timeout) and stored in the set files. A gold query that errors or times out is dropped and replaced by the next draw (logged in NOTICE).

## What the model sees

- **Schema:** each table's `CREATE TABLE` statement from `sqlite_master`, plus the first 3 rows of each table. (My call. It's the common BIRD baseline setup.)
- The `evidence` hint and the question.
- Never: the gold SQL, the gold result, the difficulty tag.

## Levels

Each level adds one thing, so we see what each step is worth. The generator prompt is the same at every level; only the feedback changes.

| Level | What happens | Calls per question |
|---|---|---|
| **0 · one prompt** | Schema + evidence + question → SQL. | 1 |
| **1 · the article's loop** | Generator, then an **AI grader that reads the SQL only** (no running), PASS / NEEDS_IMPROVEMENT / FAIL + feedback. Not PASS → regenerate with the feedback. | 2 to 6 |
| **2 · run it, no AI grader** | Code runs the SQL. Error, timeout or **zero rows** → regenerate with the real error (or "returned no rows"). Otherwise accept. | 1 to 3 |
| **3 · AI grader that sees the result** | Code runs the SQL; the grader sees the SQL **and** the error or the first 10 result rows (plus the row count). Then like level 1. | 2 to 6 |
| **0+ · bigger model** | Level 0 on the large model. | 1 |

- **Cap: 3 generations per question** (the article has none). If the cap is hit, the last SQL is the answer. Hitting the cap is counted.
- Levels 0–3 use `gpt-6-luna`; level 0+ uses `gpt-6.1-sol`. Lowest reasoning effort each accepts (as in topic 03). Grader = same model as generator (as in the article: one model, two prompts).
- Level 2 is plain code, so it's also the "free check" baseline for levels 1 and 3.
- **3 repeats** per level per set.

## Metrics

| Metric | Meaning |
|---|---|
| **Right (EX)** | The predicted SQL's result rows equal the gold rows as a **set** (BIRD's execution-accuracy rule). Overall and per difficulty |
| **First try right** | Same, for the round-1 SQL. Shows what the loop added |
| **Fixed / broken** | Round 1 wrong → final right / round 1 right → final wrong |
| **Fooled (PASS on wrong)** | Levels 1 and 3: final answer graded PASS, but wrong |
| **False alarm** | Levels 1 and 3: a right SQL got NEEDS_IMPROVEMENT or FAIL |
| **Rounds, cap hit** | Average generations; share of questions that hit 3 |
| **SQL errors** | Final SQL errors or times out (counted as wrong) |
| **Time, cost** | Seconds and dollars per question |

Prediction timeout: 10 s per query (counts as wrong, and is fed back at levels 2–3). An API outage is left out of accuracy and counted separately, as in topic 04.

## What I expect (written before any run)

- **Level 1 barely helps.** A grader reading SQL can't see the data, so it will mostly polish style and PASS wrong answers.
- **Level 2 fixes the "doesn't run" cases** but not wrong logic.
- **Level 3 helps most**, because the grader sees real rows.
- **Level 0+ might beat all of them**, like in topics 01 and 02.
- Some **right answers will get broken** by a grader asking for "improvements".

## Safety and money

- Databases are opened **read-only** (`file:...?mode=ro` URI). A progress handler enforces the timeout.
- `run.py`: cost estimate first, asks before spending, budget stop per command, **$10 ceiling for the topic**. A smoke run (5 questions, levels 0–3, 1 repeat) comes first and its measured cost replaces the estimate.
- Rough estimate (before the smoke run): main + held-out, all levels, 3 repeats ≈ **$3–6**, most of it level 0+.

## Folder

```
05-evaluator-optimizer-text-to-sql/
├── README.md, results.md
├── design/            design.md, plan.md, process-diagram.html / .png
├── sqlloop/           models, build_data, data, schema, execute, prompts, levels, score, run, report
├── data/              main.json, test.json, NOTICE.md   (raw/ git-ignored)
├── evals/             offline tests (no API calls; small SQLite fixture built in the test)
└── runs/              git-ignored
```

Work happens directly in `C:\Workshop\ai-engineering-lab\topics` (no separate worktree), per the user.

## Left to the builder

- Exact prompt wording (the generator and grader prompts follow the article's tags: `<thoughts>`, `<response>` / `<evaluation>`, `<feedback>`; SQL in `<sql>`).
- How to cut very long rows in the schema samples and result previews (keep the prompt bounded).
- Chart style for the blog (SVG, like topic 04).

## Calls I made (for review)

1. **Split by database**, 6 / 5, so the held-out set tests new schemas.
2. **60 + 60 questions**, stratified 18 / 30 / 12.
3. **Cap of 3 generations.**
4. **Zero rows counts as "try again"** at level 2.
5. **Schema = CREATE TABLE + 3 sample rows.** The `evidence` hint is included.
6. **Grader = same model as the generator.**
