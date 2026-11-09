# Topic 3: Input tokens and latency on ContractNLI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Measure the four "input token management" claims of Anthropic's latency article (prompt size, caching, pre-warming, server-side conversation) on OpenAI models, using topic 2's 60 NDAs and lawyers' labels.

**Architecture:** A new package `ndaspeed` in `topics/03-input-tokens-latency-contract-nli/`: config → timer → packs → stats/cost → chat → experiments → run → report. It reuses topic 2's `ndaflow` for data loading, contract rendering and answer parsing, and `shared.llm` for model names and prices, without changing either. Every API call goes through one streaming timer.

**Tech Stack:** Python 3, OpenAI Python SDK (Responses API, streaming), pytest.

**Spec:** `topics/03-input-tokens-latency-contract-nli/design/design.md`

## Global Constraints

- Work in the worktree `C:\Workshop\ai-engineering-lab-topic03`, branch `topic-03-input-tokens-latency`. Commit locally; never push without the author's OK.
- The worktree has no `.venv`: run Python as `C:\Workshop\ai-engineering-lab\.venv\Scripts\python.exe` (written `$PY` below) from the worktree root.
- Do **not** modify `shared/llm.py` or anything under `topics/01-prompt-vs-workflow-contract-nli/`. Import from them only.
- Models: `shared.llm.default_model("small")` (gpt-6-luna) everywhere; `default_model("large")` (gpt-6.1-sol) in test 1 only. Call `shared.llm.load_env()` first.
- Timed calls use `openai.OpenAI(max_retries=0)`. Retries happen outside the clock.
- All API calls are sequential. Variants are interleaved inside each test.
- Seed `2026` for every random choice; the seed and the drawn packs/questions are saved in each run file.
- Test 1 sizes: `20_000, 50_000, 100_000, 180_000` tokens. Short pack = 1 NDA; long pack = the 30 main-set NDAs. Questions from the main set only.
- Budget: `--budget` default `3.0` USD per command; topic ceiling `10.0` USD across all run files.
- Labels exactly `entailment`, `contradiction`, `not_mentioned`; unreadable = `error`, counts wrong.
- Results only from real runs. API keys only in `.env`. Tests never touch the network.

## Review Focus

1. **A stream that ends with no output text** (reasoning only, or empty): `first_text_s` is `None`, the record is kept, left out of TTFT stats and counted. Tests in Task 1 and Task 3.
2. **An API error, before or mid-stream** (429, 5xx, dropped connection): the timer returns a `Timing` with `error` set and never raises; the experiment waits outside the clock and re-sends. Tests in Task 1 and Task 5.
3. **A rejected `previous_response_id`** (expired or not stored): that turn re-sends the full conversation, is marked `fallback`, and the chat goes on. Test in Task 4.
4. **A "cold" request that shows cached tokens > 0**: flagged in `results.md` with a count, never silently averaged in. Test in Task 7.
5. **Not enough NDAs for a target size**: `stack_to` raises `ValueError` naming the size; test 1 records that size as `skipped` and runs the others. Tests in Task 2 and Task 5.

---

### Task 1: Folder, config and the streaming timer

**Files:**
- Create: `topics/03-input-tokens-latency-contract-nli/ndaspeed/__init__.py` (empty), `ndaspeed/config.py`, `ndaspeed/timer.py`
- Create: `topics/03-input-tokens-latency-contract-nli/evals/speed_helpers.py`, `evals/test_speed_timer.py`
- Modify: `pyproject.toml` (add `"topics/03-input-tokens-latency-contract-nli"` to `pythonpath`, `"topics/03-input-tokens-latency-contract-nli/evals"` to `testpaths`)
- Modify: `conftest.py` (also block `ndaspeed.config.make_client`, same `_blocked` function)

The evals folder has **no `__init__.py`**; every file name starts with `speed_` or `test_speed_` (no clash with topics 1 and 2).

**Interfaces:**
- Produces (`config.py`): `SEED = 2026`, `MIN_OUTPUT_TOKENS = 16`, `REASONING = {"effort": "low"}` (confirmed in Task 8), `TOPIC_DIR`, `RUNS_DIR = TOPIC_DIR / "runs"`, `RESULTS = TOPIC_DIR / "results.md"`, `TOPIC_CEILING_USD = 10.0`, `model(size: str) -> str` (calls `load_env()` then `default_model(size)`), `make_client(size: str = "small") -> openai.OpenAI` (`require_api_key(model(size))`, `max_retries=0`).
- Produces (`timer.py`):
  - `@dataclass Timing(first_event_s: float | None, first_output_s: float | None, first_text_s: float | None, total_s: float | None, request_bytes: int, input_tokens: int = 0, cached_tokens: int = 0, output_tokens: int = 0, reasoning_tokens: int = 0, response_id: str = "", text: str = "", error: str | None = None, status: int | None = None)`
  - `timed_stream(client, *, clock=time.perf_counter, **request) -> Timing` — sends `client.responses.create(stream=True, **request)`.
  - `nonce(rng: random.Random) -> str` — `"run-id: "` + 16 hex chars.
- Produces (`evals/speed_helpers.py`): `FakeClient(scripts: list[list[FakeEvent]] | None)` with `.responses.create(**kw)` that records `kw` in `.requests` and returns the next script (a list of events) or raises a scripted exception; `ev(type, **fields)` builds an event; `completed(id, input_tokens, cached, output, reasoning=0)` builds a `response.completed` event with a `.response.usage` shaped like the SDK's; `fake_clock(times)`.

Event rules: first event of any type → `first_event_s`; first `response.output_item.added` or any `*.delta` → `first_output_s`; first `response.output_text.delta` → `first_text_s` (text deltas are joined into `text`); `response.completed` → `total_s` and usage. `request_bytes = len(json.dumps(request, ensure_ascii=False).encode("utf-8"))` (the request kwargs, a close stand-in for the body).

- [ ] **Step 1: Write the failing tests** in `evals/test_speed_timer.py`:

```python
def test_timer_records_first_text_total_and_usage():
    client = FakeClient([[ev("response.created"), ev("response.output_item.added"),
                          ev("response.output_text.delta", delta="ent"), ev("response.output_text.delta", delta="ail"),
                          completed("r1", input_tokens=1200, cached=1024, output=5)]])
    t = timed_stream(client, clock=fake_clock([0.0, 0.3, 0.5, 0.9, 1.0, 1.4]), model="m", input="hi")
    assert (t.first_event_s, t.first_output_s, t.first_text_s, t.total_s) == (0.3, 0.5, 0.9, 1.4)
    assert t.text == "entail" and t.response_id == "r1"
    assert (t.input_tokens, t.cached_tokens, t.output_tokens) == (1200, 1024, 5)
    assert t.request_bytes == len(json.dumps({"model": "m", "input": "hi"}).encode())

def test_timer_reasoning_counts_as_output_not_text():
    # reasoning delta first → first_output_s set at it, first_text_s later

def test_timer_stream_without_text_leaves_first_text_none():
    # only created + completed → first_text_s is None, total_s set, error None

def test_timer_api_error_returns_timing_with_error_and_status():
    # FakeClient raises openai.RateLimitError (status 429) → no raise; error contains "RateLimitError", status == 429

def test_timer_error_mid_stream_keeps_partial_times():
    # script yields created, then raises openai.APIConnectionError → first_event_s set, error set, total_s None
```

- [ ] **Step 2: Run, expect FAIL** — `$PY -m pytest topics/03-input-tokens-latency-contract-nli/evals/test_speed_timer.py -q` → import errors.
- [ ] **Step 3: Implement** `config.py` and `timer.py` per the Interfaces block; edit `pyproject.toml` and `conftest.py`.
- [ ] **Step 4: Run, expect PASS**, then the whole suite `$PY -m pytest -q` → all green (topics 1 and 2 still pass).
- [ ] **Step 5: Commit** — `git add pyproject.toml conftest.py topics/03-input-tokens-latency-contract-nli && git commit -m "Topic 3: package, config, streaming timer"`

---

### Task 2: Packs, questions, prompt text, answer reading

**Files:**
- Create: `ndaspeed/packs.py`
- Test: `evals/test_speed_packs.py` (with tiny fake `Contract`s from `ndaflow.models`)

**Interfaces:**
- Consumes: `ndaflow.data.load_contracts(set_name)`, `load_statements()`, `load_answer_key(set_name)`; `ndaflow.prompts.ROLE`, `LABEL_RULES`, `render_contract(c)`; `ndaflow.levels.parse_answer(block: str, valid: set[int]) -> Answer`; `ndaflow.models.Contract`, `Statement`, `Answer`.
- Produces:
  - `est_tokens(text: str) -> int` = `len(text) // 4` (planning only; real counts come from usage).
  - `@dataclass Pack(name: str, contracts: list[Contract], codes: list[str], text: str)`; `codes` are `C01`, `C02`, … in pack order; property `est_tokens`.
  - `make_pack(name: str, contracts: list[Contract]) -> Pack` — text is one block per contract: `"## Contract C07\n" + render_contract(c)`, joined by blank lines.
  - `all_contracts() -> list[Contract]` — main then test, each sorted by `doc_id` as stored.
  - `stack_to(contracts: list[Contract], target_tokens: int) -> list[Contract]` — shortest prefix of `contracts` with `est_tokens >= target_tokens`; `ValueError(f"not enough NDAs for {target_tokens} tokens")` if the list runs out.
  - `@dataclass Question(code: str, doc_id: str, sid: str, text: str)`.
  - `short_questions(pack: Pack, statements: list[Statement]) -> list[Question]` — the 17 statements in order, all on `C01`.
  - `long_questions(pack: Pack, statements: list[Statement], n: int, rng: random.Random) -> list[Question]` — `n` distinct contracts, one random statement each.
  - `instructions(nonce: str | None) -> str` — nonce line first (if given), then `ROLE`, `LABEL_RULES`, and the answer format `<answer><label>…</label><evidence>span numbers, or none</evidence></answer>`.
  - `PING = "Reply with OK."` (test 0/1 question and test 3 warm-up question).
  - `question_text(q: Question) -> str` — `f"Contract {q.code}: {q.text}"`.
  - `read_answer(text: str, contract: Contract) -> Answer` — the `<answer>` block through `parse_answer` with the contract's span ids; no block → `Answer("error")`.

- [ ] **Step 1: Write the failing tests:** `test_make_pack_numbers_contracts_and_keeps_span_ids` (text contains `"## Contract C02"` and `"[3] "`), `test_stack_to_stops_at_first_prefix_over_target`, `test_stack_to_raises_when_too_few` (message names the size), `test_long_questions_distinct_contracts_and_repeatable` (same seed → same list; codes distinct), `test_short_questions_are_17_in_dataset_order`, `test_instructions_put_nonce_first_and_same_without_nonce_is_stable`, `test_read_answer_reads_block_and_drops_unknown_spans`, `test_read_answer_without_block_is_error`.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement `packs.py`.**
- [ ] **Step 4: Run, expect PASS.** Also a quick real-data check: `$PY -c "from ndaspeed.packs import *; print(make_pack('long', __import__('ndaflow.data').data.load_contracts('main')).est_tokens, est_tokens(make_pack('all', all_contracts()).text))"` → about 95,000 and 185,000.
- [ ] **Step 5: Commit** — `"Topic 3: packs, questions, prompt text"`

---

### Task 3: Stats and cost

**Files:**
- Create: `ndaspeed/stats.py`, `ndaspeed/cost.py`
- Test: `evals/test_speed_stats.py`

**Interfaces:**
- Consumes: `Timing` (Task 1); `shared.llm.PRICES`.
- Produces (`stats.py`): `values(xs: list[float | None]) -> list[float]` (drops `None`); `median(xs) -> float | None`; `p90(xs) -> float | None` (nearest rank: `sorted(xs)[ceil(0.9 * n) - 1]`); `slope_per_100k(tokens: list[int], seconds: list[float]) -> float` (least squares slope × 100,000); `bootstrap_diff(a, b, rng, n=1000) -> tuple[float, float]` (2.5th and 97.5th percentile of `median(resample b) - median(resample a)`).
- Produces (`cost.py`): `cost_of(t: Timing, model: str) -> float` = `((input - cached) * input_price + cached * cache_read + output * output_price) / 1e6`; `class BudgetExceeded(Exception)`; `@dataclass Budget(limit_usd: float, spent_usd: float = 0.0)` with `before(estimate_usd: float) -> None` (raises `BudgetExceeded` if `spent + estimate > limit`) and `add(usd: float) -> None`; `spent_in_runs(runs_dir: Path) -> float` (sum of `spent_usd` over `test*.json`).

- [ ] **Step 1: Write the failing tests:** `test_median_and_p90_ignore_none` (`[None, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]` → median 5.5, p90 9), `test_median_of_empty_is_none`, `test_slope_per_100k_exact_line` (tokens 0/100K/200K, secs 0.5/0.75/1.0 → 0.25), `test_bootstrap_diff_brackets_true_shift` (b = a + 1.0 → interval contains 1.0), `test_cost_of_prices_cached_tokens_at_cache_rate` (gpt-6-luna, 1,000 in, 600 cached, 100 out → `(400*0.10 + 600*0.01 + 100*0.50)/1e6`), `test_budget_stops_before_crossing_limit`, `test_spent_in_runs_sums_run_files`.
- [ ] **Step 2: Run, expect FAIL.** - [ ] **Step 3: Implement.** - [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** — `"Topic 3: stats and cost"`

---

### Task 4: One chat, three ways (cache on, cache off, server-side conversation)

**Files:**
- Create: `ndaspeed/chat.py`
- Test: `evals/test_speed_chat.py`

**Interfaces:**
- Consumes: `timed_stream`, `Timing`, `nonce` (Task 1); `Pack`, `Question`, `instructions`, `question_text`, `read_answer` (Task 2); `Budget`, `cost_of` (Task 3); `config.REASONING`.
- Produces:
  - `VARIANTS = ("cache_on", "cache_off", "thread")`
  - `@dataclass Turn(index: int, question: Question, timing: Timing, answer: Answer, fallback: bool = False)`
  - `run_chat(client, model: str, pack: Pack, questions: list[Question], variant: str, rng: random.Random, budget: Budget, chat_id: str) -> list[Turn]`
  - `ANSWER_TOKENS = 2000` (`max_output_tokens` for answers)

Request shape (every turn): `model`, `instructions=instructions(<nonce>)`, `input=[{"role": "user", "content": pack.text}, then question/answer pairs as {"role": "user"/"assistant", "content": text}]`, `max_output_tokens=ANSWER_TOKENS`, `reasoning=REASONING`.
- `cache_off`: a **new nonce on every turn**; `store=False`; no `prompt_cache_key`.
- `cache_on`: **one nonce per chat** (fresh for each chat, so turn 1 is cold); `store=False`; `prompt_cache_key=chat_id`.
- `thread`: like `cache_on`, but `store=True`; from turn 2 on, `input=[<new question only>]` and `previous_response_id=<last response id>` (`instructions` are re-sent, the Responses API does not carry them over). If that turn's `Timing.error` is set, re-send the turn the `cache_on` way, set `fallback=True`, and continue from the new response id.
- Before each call `budget.before(<est_tokens of the request> * input price)`; after it `budget.add(cost_of(timing, model))`.

- [ ] **Step 1: Write the failing tests** (FakeClient answering `<answer><label>entailment</label><evidence>1</evidence></answer>`): `test_cache_off_changes_first_line_every_turn`, `test_cache_on_keeps_instructions_and_pack_identical_across_turns`, `test_history_grows_with_previous_answers_in_order`, `test_thread_sends_only_new_question_after_turn_one` (turn 2 `input` has length 1 and `previous_response_id == "r1"`), `test_thread_falls_back_to_full_resend_on_error` (turn 2 raises → turn marked `fallback`, a full-history request follows, turn 3 continues from the fallback's id), `test_unreadable_answer_is_error_and_chat_continues`, `test_budget_exceeded_stops_before_the_call` (no request recorded after the limit).
- [ ] **Step 2: Run, expect FAIL.** - [ ] **Step 3: Implement `chat.py`.** - [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** — `"Topic 3: chat in three variants"`

---

### Task 5: The five experiments

**Files:**
- Create: `ndaspeed/experiments.py`
- Test: `evals/test_speed_experiments.py`

**Interfaces:**
- Consumes: Tasks 1–4; `ndaflow.data` loaders.
- Produces:
  - `measure(client, budget: Budget, model: str, sleep=time.sleep, **request) -> tuple[Timing, list[Timing]]` — calls `timed_stream`; on an error with status 429 or ≥ 500, or a connection error, `sleep(5 * attempt)` (outside the clock) and retry, up to 3 retries; returns the last timing and the failed attempts (saved as `error` records).
  - `test0(client, model, rng, budget, repeats=10) -> dict`
  - `test1(client, models: dict[str, str], rng, budget, rounds={"small": 5, "large": 3}, sizes=SIZES) -> dict` with `SIZES = (20_000, 50_000, 100_000, 180_000)`
  - `test2(client, model, rng, budget, short_n=10, long_chats=3) -> dict`
  - `test3(client, model, rng, budget, reps=10, sleep=time.sleep) -> dict`
  - `test4(client, model, rng, budget, chats=3) -> dict`
  - Every `testN` returns `{"test": "N", "started": <ISO time>, "seed": 2026, "models": {...}, "plan": {<drawn packs and questions>}, "records": [...], "spent_usd": float, "stopped": None | "budget"}`; each record holds `variant`, the test's own keys (`size`, `turn`, `rep`, `chat`), `model`, the `Timing` as a dict, and for answers `doc_id`, `sid`, `label`, `evidence`.
  - The first call of every test is a warm-up record (`variant: "warmup"`), left out of all stats.

Per test:
- **test0:** `instructions(None)` + `PING`, `max_output_tokens=MIN_OUTPUT_TOKENS`, `repeats` times.
- **test1:** every request is `instructions(nonce(rng))` + `make_pack("stack", stack_to(all_contracts(), size)).text` + `PING`, `max_output_tokens=MIN_OUTPUT_TOKENS`, `store=False`. Each round = every (model, size) pair whose model still has rounds left, shuffled with `rng`. A size that raises `ValueError` is recorded once as `{"size": s, "skipped": "<message>"}`.
- **test2:** short pack: `short_n` main-set NDAs drawn with `rng`, each run as `cache_on` and `cache_off` (order alternates: even chats on-first, odd chats off-first). Long pack: `long_chats` chats per variant with `long_questions(pack, statements, 17, rng)`, alternated the same way. Each answer record carries the key's label and evidence.
- **test3:** `reps` repetitions × {`cold`, `prewarm`}, alternated. Each uses a fresh nonce. `prewarm`: a non-streamed `client.responses.create` with the same `instructions`, the pack message, `PING`, `max_output_tokens=MIN_OUTPUT_TOKENS`, `prompt_cache_key`; then `sleep(2)`; then the first long-pack question streamed through `measure`. `cold`: the first question only. Record `cached_tokens` of the measured call.
- **test4:** `chats` long-pack chats × {`cache_on`, `thread`}, alternated, through `run_chat`.
- On `BudgetExceeded`: stop, set `"stopped": "budget"`, return what was measured.

- [ ] **Step 1: Write the failing tests** (FakeClient, `sleep` and `rng` injected, tiny contracts patched in via `monkeypatch` on `ndaspeed.packs.all_contracts` / `ndaflow.data` loaders): `test_measure_retries_429_outside_clock_and_keeps_failed_attempt`, `test_measure_does_not_retry_400`, `test_first_record_of_each_test_is_warmup`, `test_test1_mixes_models_and_sizes_and_large_stops_after_its_rounds` (small 5 rounds, large 3 → 4 × 5 + 4 × 3 measured records), `test_test1_records_skipped_size_and_continues`, `test_test2_alternates_variant_order_by_chat`, `test_test3_prewarm_is_not_streamed_and_shares_prefix_with_question` (same `instructions` and pack message; `max_output_tokens == 16`; `sleep(2)` called), `test_budget_stop_returns_partial_run_marked_budget`.
- [ ] **Step 2: Run, expect FAIL.** - [ ] **Step 3: Implement `experiments.py`.** - [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** — `"Topic 3: the five tests"`

---

### Task 6: Runner (dry run, budget, run files)

**Files:**
- Create: `ndaspeed/run.py`
- Test: `evals/test_speed_run.py`

**Interfaces:**
- Consumes: Tasks 1–5.
- Produces: `estimate_usd(test: str, models: dict[str, str], args) -> float` — upper bound: every planned request's `est_tokens` priced as uncached input, plus `ANSWER_TOKENS / 4` output per answer and `MIN_OUTPUT_TOKENS` per ping; `main(argv: list[str] | None = None, client=None) -> int`.
- CLI: `python -m ndaspeed.run --test {0,1,2,3,4} [--model small|large|both] [--repeats N] [--limit N] [--budget 3.0] [--dry-run] [--yes]`.
  `--model` only matters for test 1 (default `both`); `--repeats` overrides the test's count; `--limit` caps chats/rounds for smoke runs.
- Behaviour: always print the estimate and the topic total so far (`spent_in_runs(RUNS_DIR)`). `--dry-run` → exit 0 with no call. Without `--yes` → print "add --yes to run" and exit 0. Refuse (exit 2) if `spent so far + estimate > TOPIC_CEILING_USD`. Otherwise run with `Budget(args.budget)` and save `runs/test<N>-<YYYYmmdd-HHMMSS>.json` (also when stopped by budget).

- [ ] **Step 1: Write the failing tests:** `test_dry_run_prints_estimate_and_makes_no_call`, `test_without_yes_makes_no_call`, `test_refuses_over_topic_ceiling` (a fake run file with `spent_usd: 9.9` in a tmp `RUNS_DIR`), `test_run_writes_run_file_with_spent_usd`, `test_estimate_test1_large_model_is_about_2_8_usd` (3 rounds + warm-up, 350K tokens, $2/M → between 2.5 and 3.2).
- [ ] **Step 2: Run, expect FAIL.** - [ ] **Step 3: Implement `run.py`.** - [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** — `"Topic 3: runner"`

---

### Task 7: Report (`results.md`) and README skeleton

**Files:**
- Create: `ndaspeed/report.py`
- Modify: `topics/03-input-tokens-latency-contract-nli/README.md` (skeleton exists), `results.md` (generated)
- Test: `evals/test_speed_report.py`

**Interfaces:**
- Consumes: run files; `stats`; `ndaflow.score` is **not** used (only label right and evidence found are needed).
- Produces: `ARTICLE: dict[str, str]` (the "Article said" line per test, copied from the design's section 2 table); `build_results(runs_dir: Path = RUNS_DIR) -> str`; `main() -> int` (writes `RESULTS`).
- Content: one section per test from its **latest** run file, or "Not run yet."; each section starts with **Article said … / We got …**, then a table:
  - test 0: p50 / p90 / min first word, total.
  - test 1: per model × size: input tokens (from usage), first word p50 / p90, n; then the slope per model and the line "cold check: N requests with cached tokens > 0".
  - test 2: per pack × variant: first word p50 for turn 1 and for turns 2–17, total time p50, cached share of input, $ per chat, label right, evidence found, errors; the bootstrap interval for turns 2–17 on vs off.
  - test 3: per variant: first word p50 / p90, warm-up hit rate (share of `prewarm` first questions with cached tokens > 0), bootstrap interval.
  - test 4: per variant: request bytes p50 (turns 2–17), first word p50 (turns 2–17), fallbacks.
  - footer: spend per run and the running total; the how-to-run block.
- Warm-up and error records are excluded from stats and counted in an "errors" column.

- [ ] **Step 1: Write the failing tests** (hand-written run dicts in a tmp dir): `test_missing_test_says_not_run_yet`, `test_warmup_and_errors_left_out_of_stats_but_counted`, `test_test1_shows_slope_and_flags_cold_requests_with_cached_tokens`, `test_test3_shows_prewarm_hit_rate`, `test_footer_shows_running_total`, `test_latest_run_per_test_wins`.
- [ ] **Step 2: Run, expect FAIL.** - [ ] **Step 3: Implement `report.py`; fill the README's "What's in the folder" and "How to run" sections (no findings).** - [ ] **Step 4: Run, expect PASS; then `$PY -m ndaspeed.report` → `results.md` says "Not run yet." for every test.**
- [ ] **Step 5: Commit** — `"Topic 3: report and README skeleton"`

---

### Task 8: Smoke run (real API — only after the author says yes)

Needs `.env` in the worktree root (the author copies it from `C:\Workshop\ai-engineering-lab\.env`; it is git-ignored). Spend: under $0.50.

- [ ] **Step 1:** `$PY -m ndaspeed.run --test 1 --dry-run` and the same for tests 0, 2, 3, 4 → note the estimates; they should add up to about $4 (design section 9).
- [ ] **Step 2:** `$PY -m ndaspeed.run --test 0 --repeats 3 --yes` → 3 records, first word under 2 s, no errors. Check from the run file: the stream's event order, `reasoning_tokens`, and that `REASONING` and `MIN_OUTPUT_TOKENS = 16` are accepted. If either is refused, change it in `config.py` and record why in the design's section 6.
- [ ] **Step 3:** `$PY -m ndaspeed.run --test 1 --model both --repeats 1 --yes` → every size answers on both models, cold check is 0. If 180K fails on a model, follow the design (drop that size for that model) and write it in `results.md` notes.
- [ ] **Step 4:** `$PY -m ndaspeed.run --test 2 --limit 1 --yes` and `--test 4 --limit 1 --yes` → answers are readable (errors 0 or near 0); `cache_on` turn 2 shows cached tokens; `thread` turn 2 sends one message.
- [ ] **Step 5:** delete the smoke run files (they are not results), then commit any config fix — `"Topic 3: settings confirmed in the smoke run"`. Full runs are a separate step, each with the author's yes.
