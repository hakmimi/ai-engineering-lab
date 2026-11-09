# Topic 2: Prompt vs Workflow on real contracts (ContractNLI) — Design

Date: 2026-11-09
Folder: `topics/01-prompt-vs-workflow-contract-nli/` in `hakmimi/ai-engineering-lab`
Source article: Anthropic cookbook, "Basic Multi-LLM Workflows" (same as topic 1)
https://platform.claude.com/cookbook/patterns-agents-basic-workflows
Data: ContractNLI (Koreeda & Manning, 2021), https://stanfordnlp.github.io/contract-nli/ , licence CC BY 4.0

## 1. Intent

Topic 1 asked: when is one big prompt enough, and when does a multi-LLM workflow (route → parallel → chain) pay off?
On made-up insurance claims the answer was: one prompt won; a bigger model beat splitting the job.

Topic 1 had two weak spots, both in its own caveats:
- the data and the answer key were made up by us;
- the documents were short, so everything fit in one prompt easily.

Topic 2 is **a replica of topic 1 on real data**: the same five levels, the same scoring idea, the same folder layout,
but the job is reading **real NDAs** (non-disclosure agreements) and the answer key comes from **lawyers' labels**.
The question for the reader: **same test, real data: does the answer change?**

## 2. The job (decided)

Per contract:
- **Input:** one NDA, already split by the dataset into numbered spans (sentences or list items), plus the **17 fixed statements**
  ("hypotheses") the dataset checks every NDA against. Example: "Receiving Party may share some Confidential Information with some of Receiving Party's employees."
- **Output, for each of the 17 statements:**
  - **label:** `entailment` (the contract says so), `contradiction` (the contract says the opposite), or `not_mentioned`
  - **evidence:** the span numbers that prove the label (empty when `not_mentioned`)
- **Answer key:** the dataset's own annotation (`annotation_sets[0]`). No hand-written key, so no author review of the key is needed.

## 3. The levels (decided, approved in chat 2026-11-09)

Each level adds one step, as in topic 1.

| Level | Topic 1 (claims) | Topic 2 (NDAs) |
|---|---|---|
| 0 | one big prompt | **One prompt:** the whole NDA (numbered spans) + all 17 statements → 17 labels + evidence in one call |
| 1 | + route by claim type | **+ route:** one call reads the whole NDA and, for each statement, picks the span numbers that matter. The decide prompt then sees, per statement, **only those spans**. A statement with no picked spans is `not_mentioned` by code, with no further call (like topic 1's "no matching policy" exit). |
| 2 | + parallel document checks | **+ parallel:** after routing, **one call per statement, all at the same time**, each seeing only its own picked spans |
| 3 | + chain, code does the math | **+ chain, per statement (still in parallel):** step A: which of the picked spans actually speak to the statement? → **code** keeps only real span numbers from the picked set; none left → `not_mentioned`. Step B: given only those spans, `entailment` or `contradiction`? |
| 0+ | bigger model | Level 0 on the bigger model |

Why route = "pick the spans": topic 1 found that splitting lost because **each call saw less**. Here the route step cuts the
context on purpose, which tests that finding directly: does a shorter context help the model focus, or does it lose evidence
that sat elsewhere in the contract?

## 4. Data sets (decided)

- **Main set (tuning allowed):** 30 NDAs drawn from the dataset's **dev** split.
- **Held-out set (never tuned on):** 30 NDAs drawn from the dataset's **test** split. This replaces topic 1's hand-made "hard set";
  the split comes from the dataset itself, so nobody picked "hard" cases.
- Draw: random, fixed seed, recorded in the data folder with the source file and document ids, so it can be repeated.
- The **train** split is not used (no few-shot examples, no tuning on it).
- 30 NDAs × 17 statements = **510 judged pairs per set** per repeat.
- What the source splits look like (measured 2026-11-09 from the downloaded files):

  | Split | NDAs | Length (characters) | Spans per NDA | Labels |
  |---|---|---|---|---|
  | dev | 61 | median 11,299, max 32,359 | median 72, max 255 | 50% entailment, 9% contradiction, 41% not mentioned |
  | test | 123 | median 9,614, max 41,779 | median 72, max 249 | 46% entailment, 11% contradiction, 43% not mentioned |

  Every NDA has all 17 statements labelled. Evidence: median 2 spans per labelled pair. The longest NDA is about 10k tokens,
  so **every contract fits in one prompt**: the route step is a choice to cut context, not a need.
  Contradiction is rare (about 1 in 10 pairs), so with 30 NDAs a set has roughly 45–55 contradiction pairs; its F1 will be noisy.
- The selected NDAs are stored in `data/` (`main.json`, `test.json`) with a NOTICE giving the dataset's citation and CC BY 4.0 licence.
  The original zip is not committed.

## 5. What is measured (decided)

Per level and set, averaged over **3 repeats**:

| Metric | Meaning |
|---|---|
| Label right | share of the 510 pairs with the right label (3 options) |
| F1 entailment, F1 contradiction | how well it finds the "yes" and the "no" answers (the dataset paper's main scores); `not_mentioned` is the majority class, so accuracy alone flatters a lazy model |
| Evidence found (recall) | of the key's evidence spans, on pairs the key labels entailment/contradiction: share the model named |
| Evidence precision | of the spans the model named: share that are in the key |
| Errors | pairs whose answer could not be read (counted wrong) |
| Seconds, $, calls, cached input | per contract, as in topic 1 |

Scores are recomputed from the saved run files against the current key, as in topic 1.

## 6. How it gets made

Decided (carried over from topic 1):
- Python, OpenAI Responses API through `shared/llm.py` (`llm_call`, `extract_xml`, `Tracker`). Levels 0–3 on `gpt-6-luna`, 0+ on `gpt-6.1-sol`,
  through the same `default_model()` settings (`CLAIMS_MODEL`, `CLAIMS_MODEL_LARGE`; the names stay as they are, Claude's call).
- Answers in XML tags, read with `extract_xml`. Prompt caching on at every level, fixed text first.
- Tests run offline with a fake `llm_call`; the root `conftest.py` already blocks real API calls and the real `.env`.
- Runner with `--level`, `--set main|test`, `--repeats`, `--limit`, `--dry-run`, a printed cost estimate and a budget stop.
- `results.md` is generated from run files only, one section per set.
- API keys only in the git-ignored `.env`. Commits local; push only when the author asks.

Claude's calls (the author can change them):
- **Package name** `ndaflow`, folder `topics/01-prompt-vs-workflow-contract-nli/`.
- **Branch** `topic-02-contract-nli`, cut from `topic-01-prompt-vs-workflow` (topic 1's `shared/llm.py` fixes live there; `main` doesn't have them yet).
- **Budget:** about $5–10 for the whole topic, almost all of it level 0+ (the big model reading whole contracts:
  roughly 3k tokens in and 3k out per contract ≈ $0.04, × 30 NDAs × 3 repeats × 2 sets ≈ $7; levels 0–3 on the small model add under $1). To be confirmed by a `--dry-run` and a 2-contract smoke run before the full runs.
- **Statement order:** the 17 statements keep the dataset's ids (`nda-1` … `nda-20`, not all numbers used) in every prompt and file.

## 7. Goals, non-goals, anti-goals

Goals:
- Re-run topic 1's question on real, longer documents with an independent answer key.
- Keep the five levels directly comparable to topic 1 (same names, same table shape).
- Show where the workflow helps or hurts, with numbers.

Non-goals:
- Beating the published ContractNLI scores, or fine-tuning anything.
- Embeddings or a vector search (the router is an LLM call, like topic 1's).
- Using the train split, few-shot examples or chunking strategies.
- Any user interface.

Anti-goals (a failure even if it runs):
- Invented or estimated results. If a run did not happen, `results.md` says so.
- Tuning prompts on the held-out (test) set.
- Polished, AI-sounding prose in the README or blog. Claude writes notes; the author writes the final text.
- Over-building: agents, frameworks, databases, extra patterns.

## 8. Deliverables

In `topics/01-prompt-vs-workflow-contract-nli/`, mirroring topic 1:
- `README.md`: same section order as topic 1's README; the "found" sections are filled only from real runs.
- `design/`: this document, the plan, and a process diagram (`process-diagram.html` + `.png`) like topic 1's.
- `data/`: the two sets, the 17 statements, the NOTICE.
- `ndaflow/`: data, models, prompts, levels, run, score, report.
- `evals/`: offline tests.
- `results.md`: generated.

The blog post is a later step, written by the author.

## 9. Left to the builder

- Exact prompt wording and tag layout for the 17 answers.
- How a routed span list is shown to the decide prompt (with its span numbers kept).
- How the runner prints progress; file names inside the package.
- How topic 2's tests sit next to topic 1's in one pytest run without a package-name clash.
