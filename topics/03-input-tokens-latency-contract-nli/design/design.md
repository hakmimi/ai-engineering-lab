# Topic 3: Does sending fewer input tokens make the model answer faster? (ContractNLI) — Design

Date: 2026-11-09
Folder: `topics/03-input-tokens-latency-contract-nli/` in `hakmimi/ai-engineering-lab`
Source article: Anthropic cookbook, "Latency Optimization on the Claude API", section **Input token management**
https://platform.claude.com/cookbook/latency-optimization-latency-optimization#input-token-management
Data: ContractNLI (Koreeda & Manning, 2021), https://stanfordnlp.github.io/contract-nli/ , licence CC BY 4.0 — the same 60 NDAs as topic 2
Models: **OpenAI** (author's decision, 2026-11-09), the same two models as topics 1 and 2

## 1. Intent

The article says input tokens cost time: the model must read every token before it writes the first word.
It tests four ways to send fewer tokens, or to stop re-sending them, and gives numbers for each.
Its numbers are for Claude, on a made-up insurance desk, measured on Anthropic's network.

Topic 3 **re-runs those four claims on real documents (the topic 2 NDAs), on OpenAI models, from a home internet connection**.
The question for the reader: **are these general rules about input tokens, or Claude-only facts? Which ones are worth doing on my stack?**

Like topics 1 and 2, every claim becomes a before/after test: one setting changes, everything else stays the same.
Like topic 2, answers are checked against the lawyers' labels, so "faster" can never hide "worse".

## 2. The claims under test, and their OpenAI version (decided)

The article's levers are Claude API features. Each one has a close OpenAI counterpart; the test uses that counterpart.

| # | Article's claim (Claude) | Article's numbers | OpenAI version we test |
|---|---|---|---|
| 1 | **A bigger prompt means a slower first word** | Uncached ~17K / 100K / 200K tokens, 1-token reply: about **+0.25 s per 100K tokens**, about the same on every model | Same test. Nothing Claude-specific. |
| 2 | **Prompt caching** (`cache_control`) | Short tasks: cost **−85%**, speed **no change**. Long prefix (~146K): turn 2 **1.7 s → 0.5 s** | OpenAI caches a repeated prompt start **automatically** (prompts of 1,024+ tokens). "On" = stable prompt start + `prompt_cache_key`. "Off" = a unique random first line on every request, which breaks the match. |
| 3 | **Pre-warming** (`max_tokens: 0` request before traffic) | 146K prompt: first turn **1.0 s → 0.8 s** | OpenAI has no `max_tokens: 0`. Pre-warm = the same prompt start with the smallest allowed reply (`max_output_tokens` at its minimum). OpenAI caching is best-effort, so the test also shows **whether** the warm-up is hit. |
| 4 | **Message threads** (server keeps the chat) | 16 page images: first word **1.27 s → 0.63 s**, request **22.3 MB → 0.3 KB** | Responses API **`previous_response_id`** (with `store: true`): the server keeps the conversation and the client sends only the new message. Same idea, same price (old turns are still billed as input). |

The mapping is part of the finding: where OpenAI's version behaves differently (automatic caching, no zero-token warm-up), the report says so.

Not tested (named in the same section, out of scope): trimming with context editing, tool search, skills, paged tools.
Topic 2's router already measured "send only the relevant sentences" on accuracy; topic 3 does not repeat it.

## 3. The use case: an NDA desk (decided)

A legal team keeps a **contract pack** open: a set of NDAs, each with its numbered spans (sentences), placed at the start of the prompt.
A reviewer asks **one question per turn** in a chat:

> "Contract C07: does it say the receiving party may share confidential information with its employees?"

The model answers with a **label** (`entailment`, `contradiction`, `not_mentioned`) and the **evidence** span numbers,
the same answer shape as topic 2. Each question is one (contract, statement) pair from the dataset, so every answer has a lawyer's label.

Two pack sizes:
- **Short pack:** 1 NDA (median ~3K tokens; above OpenAI's 1,024-token caching minimum). Like the article's short tasks.
- **Long pack:** the 30 main-set NDAs (~95K tokens). Like the article's long prefix (146K); the main set is all we have labels for in one pack.

Why this use case: the contract text is the large, fixed part; the questions are small and change every turn.
That is the shape where the article says caching, pre-warming and threads should help.

## 4. The tests

Each test runs its variants **alternately** (A, B, A, B, …) in the same time window, so a slow minute on the home connection hits both.
One warm-up call per test is sent first and thrown away (opens the connection). All calls are sequential.

### Test 0 — Network floor
- A tiny prompt (~50 tokens), shortest reply, 10 times.
- Gives our "nothing to read" first-word time. The article's floor is about 0.4–0.5 s on Claude; ours includes home internet and a different provider.

### Test 1 — Prompt size → first-word time (claim 1)
- Prompts of about **20K, 50K, 100K and 180K tokens**, built by stacking NDAs from both sets (60 NDAs ≈ 185K tokens). The article went to 200K.
- Every request starts with a **unique random line**, so nothing is read from cache (a "cold" prompt; checked: cached tokens must be 0).
- Shortest reply allowed. The 4 sizes are sent in shuffled order each round.
- **Small model: 5 rounds. Large model: 3 rounds.** Both models are mixed inside the same rounds (rounds 4–5 are small-model only),
  so the model-vs-model comparison is also measured in the same time window.
- Result: first-word time per size and model; the **slope in seconds per 100K tokens** (straight-line fit).
- "Article holds" if the slope is in roughly the same range (about 0.15–0.35 s per 100K). A different slope is a finding, not a failure.

### Test 2 — Cache-friendly vs cache-busting prompts, short vs long pack (claim 2)
- A 17-turn chat: 17 questions, one per turn, each turn added to the conversation (the history grows).
  - Short pack: one NDA, its 17 statements. **10 main-set NDAs** → 170 answers per variant.
  - Long pack: 17 questions on 17 different contracts in the pack. **3 chats** → 51 answers per variant.
- Variants: **cache on** (stable prompt start, `prompt_cache_key` per chat) vs **cache off** (a new random first line on every request).
  Alternated chat by chat. Each long-pack "on" chat still starts with its own fresh line, so its turn 1 is really cold.
- Measured per turn: first-word time, total time, input / cached tokens, $.
- Scored against the key: label right, evidence found.
- "Article holds" if: cost drops a lot; first-word time **barely changes on the short pack** and **drops clearly from turn 2 on the long pack**; accuracy does not move beyond noise.

### Test 3 — Pre-warming (claim 3)
- Long pack only. Each repetition uses a **fresh pack** (unique first line) so there is no leftover cache.
- Variant A (cold): ask the first question directly.
- Variant B (pre-warmed): send the same pack, same model and settings, smallest reply, not streamed; wait 2 s; then ask the first question.
- **10 repetitions each.** Measured: first-word time of the first question, and its cached tokens (proof the warm-up was hit; a miss is counted and reported).
- "Article holds" if B's first word is about 0.2 s sooner and B's first question shows cached tokens.

### Test 4 — Server-side conversation (claim 4) — optional, run last, can be dropped
- Long-pack chat, cache on. Variant A: the whole conversation re-sent each turn. Variant B: `previous_response_id`, only the new question sent.
- **3 chats each.** Measured: request size in bytes, first-word time per turn.
- Our guess (not the article's): a smaller gain than the article's, because the pack is ~0.4 MB of text, not 22 MB of images.
  On a home upload link 0.4 MB is still worth measuring.

## 5. How time is measured (decided)

A small streaming timer, in the spirit of the article's `timed_stream()`, on the OpenAI Responses API stream:
- clock (`time.perf_counter`) starts just before the request is sent;
- records **first event**, **first output** (first output event of any kind, including reasoning, if the model reasons), **first text** (first
  `output_text` delta — the "first word", our TTFT), and **end** (completed event, our total time);
- records the request body size in bytes, usage (input, cached input, output, reasoning tokens) and the response id.

**No hidden retries in a timed call:** measured calls use a client with `max_retries=0`. A rate-limit or server error is logged,
the runner waits outside the clock, and the call is sent again as a new measurement.

**Reasoning risk** (checked in the smoke run): if a model reasons before writing, "first text" includes thinking time.
Requests use the lowest reasoning effort the model accepts; the smoke run logs the event order and reasoning tokens, and the report notes it.

**Context risk** (checked in the smoke run): if a 180K-token request is refused (context or rate limit) on a model,
test 1 drops that size for that model and `results.md` says so.

Reported per variant: **median (p50)**, **p90**, min, and the number of runs. With 5–10 runs, p90 is close to the slowest run; the report says so.
Differences come with a simple bootstrap interval (1,000 resamples on the difference of medians).

## 6. Models and settings (decided)

- **OpenAI**, through `shared.llm.default_model()`: small = `gpt-6-luna` (`CLAIMS_MODEL`), large = `gpt-6.1-sol` (`CLAIMS_MODEL_LARGE`), as in topics 1 and 2.
- **Small model** in every test. **Large model** in test 1 only, to check "about the same on every model".
- Called through the **OpenAI Python SDK directly** (streaming, multi-turn, `previous_response_id` are not in `shared/llm.py`); prices from `shared.llm.PRICES`.
- Lowest reasoning effort the model accepts (Claude's call; the smoke run confirms the value).

## 7. Data (decided)

- Read the NDAs, statements and answer key **from topic 2's data folder** (`topics/01-prompt-vs-workflow-contract-nli/data/`); nothing is copied.
- Test 1 stacks NDAs from **both** sets (no prompt is tuned in topic 3, so using the held-out set as reading material is fine).
- Questions for tests 2–4 come from the **main set only**.
- Pack and question choices are drawn with a fixed seed (2026) and saved in each run file, so a run can be repeated.

## 8. What is measured, and the results file

| Metric | Meaning |
|---|---|
| First word (TTFT) p50 / p90 | Seconds from sending to the first output text |
| Total time p50 / p90 | Seconds from sending to the completed event |
| Slope | Test 1 only: extra first-word seconds per 100K input tokens |
| Request size | Bytes sent per request (test 4) |
| Cached tokens | Input tokens read from cache |
| $ per turn / per chat | From usage and `shared.llm.PRICES` |
| Label right, evidence found | Tests 2–4, against the lawyers' key |
| Errors | Unreadable answers, API errors, cache misses where a hit was expected |

`results.md` is generated from the run files only, one section per test, each with a line **"Article said … / We got …"**.

## 9. How it gets made

Decided (carried over from topics 1 and 2):
- Python, pytest. Tests run offline with a fake client; the root `conftest.py` blocks real calls and the real `.env`
  (this topic's own client must be blocked too).
- Runner with `--test 0|1|2|3|4`, `--repeats`, `--model small|large`, `--dry-run` (cost estimate only), `--yes`, `--budget`.
- Run files (raw timings + usage + answers) saved under `runs/` (git-ignored). `results.md` rebuilt from them.
- API keys only in the git-ignored `.env`. Commits local; push only when the author asks.

Claude's calls (the author can change them):
- **Folder** `topics/03-input-tokens-latency-contract-nli/` (number, article idea, data — the topic 2 folder pattern). **Package** `ndaspeed`.
- **Branch** `topic-03-input-tokens-latency`, cut from `topic-02-contract-nli` at `1e92b30` (topic 2's data lives there),
  in a **separate worktree** (`C:\Workshop\ai-engineering-lab-topic03`) so another agent working on topic 2 is not disturbed.
- **`shared/llm.py` is not changed** in this topic.
- **Budget:** about **$4 in total**. Small model, tests 0–4: under $1 (≈ 6M input tokens at $0.10 per million, most of it test 1 and the cache-off chats).
  Large model in test 1: ≈ $2.8 (350K tokens × 4 rounds incl. warm-up × $2 per million). To be confirmed by `--dry-run` and a 1-round smoke run.
- **Budget stop:** each command takes `--budget` (default $3) and stops before a call that would pass it. Every run file records its spend,
  and the report shows the **running total across all runs** (hard ceiling for the topic: **$10**). If money runs short, cut: test 4 → large-model rounds → the 180K size.

## 10. Goals, non-goals, anti-goals

Goals:
- Put each of the article's four claims next to our own number, in one table.
- Show which lever is worth using for an NDA chat on OpenAI, and which is not, with numbers.
- Keep accuracy checked, so no speed win hides a quality loss.

Non-goals:
- Other parts of the article (agent loop, output tokens, effort, fast mode, timeouts, UX).
- Running the same tests on Claude (possible later: the tests are written so a second provider could be added).
- Changing topic 2's code or results.
- A latency benchmark of OpenAI in general: one machine, one connection, one week.

Anti-goals (a failure even if it runs):
- Invented or estimated results. If a test did not run, `results.md` says so.
- Comparing variants measured at different times (they must be interleaved).
- A "cold" request that secretly hits the cache (every cold request must show 0 cached tokens; checked in the report).
- Polished, AI-sounding prose. Claude writes notes; the author writes the final text.
- Over-building: no dashboards, frameworks or databases.

## 11. Deliverables

In `topics/03-input-tokens-latency-contract-nli/`:
- `README.md`: same section order as topic 2's; the "found" sections filled only from real runs.
- `design/`: this document, the plan, and a process diagram later (like topic 2's).
- `ndaspeed/`: timer, packs and questions, the five tests, scoring, cost, runner, report.
- `evals/`: offline tests.
- `results.md`: generated.

## 12. Left to the builder

- Exact prompt wording and answer tags (topic 2's answer shape is the model).
- How a pack labels its contracts (`C01` … ) and spans inside the prompt.
- The exact minimum `max_output_tokens` and reasoning setting (from the SDK / a smoke call).
- How the runner prints progress; file names inside the package; how the bootstrap is coded.
