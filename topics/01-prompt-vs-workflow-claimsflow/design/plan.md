# Prompt vs Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an insurance-claims test bench that runs the same made-up claims through one big prompt (level 0) and through increasingly split workflows (levels 1–3, plus 0+ on a larger model), and scores each level on decision, amount, document problems, time and cost.

**Architecture:** A small shared LLM helper (`shared/llm.py`) wraps the Anthropic SDK and records latency, tokens and cost per call. The topic package `claimsflow` holds the domain model, the policy rules (plain code: required documents, policy lookup, payout math), one function per level, a scorer, and a CLI runner with a budget guard. Every level returns the same `Result` shape so one scorer judges them all against a hand-reviewed answer key.

**Tech Stack:** Python 3.13, `anthropic` (official SDK), `python-dotenv`, `pytest`.

**Spec:** `topics/01-prompt-vs-workflow-claimsflow/design/design.md` (read it before starting any task).

## Global Constraints

- Before writing any Anthropic SDK code, load the `claude-api` skill and take the model ids and per-million-token prices (input, output, cache write, cache read) from it. Never guess prices.
- Default model for levels 0–3: env `CLAIMS_MODEL`, default `claude-haiku-5-5`. Level 0+: env `CLAIMS_MODEL_LARGE`, default `claude-opus-5-5`.
- API key comes only from `ANTHROPIC_API_KEY`, loaded from the repo-root `.env` via `python-dotenv`. Never print, log or commit it.
- Prompt caching is on at every level: fixed text (policy wordings, instructions) goes in a cached system block.
- Money is whole shekels (`int`). Rounding: `round()` to the nearest shekel after applying a rate.
- Decisions are exactly one of: `approve_full`, `approve_partial`, `decline`, `request_documents`, `hand_to_person`.
- Claim types are exactly one of: `car`, `water_damage`, `travel_medical`, `travel_cancellation`.
- A deductible alone never makes a decision `approve_partial`. Partial = cap applied, private rate < 1.0, or part excluded.
- `results.md` and the README "What we found" sections are filled only from real run files. No invented or estimated numbers.
- Every run prints an estimated cost first and aborts if it is over the budget (default `$10`).
- Commit locally after each task. Never push.
- All paths below are relative to the repo root `C:\Workshop\ai-engineering-lab`. Run commands from the repo root using the venv: `.venv\Scripts\python`.

## Review Focus

- The router returns a label outside the four types (`"Car"`, `"home"`, `"other"`): normalize case and whitespace; anything still unknown becomes `hand_to_person`, never a `KeyError` (the article's own bug). Test owned by Task 4.
- A response has a missing or messy tag (`<amount>10,500 ₪</amount>`, no `<decision>`): parse numbers with commas and ₪; an unparseable answer becomes a `Result` with `decision="error"` that scores as wrong, and the run continues. Test owned by Task 4.
- The API fails mid-run (rate limit, overload): the SDK retries (`max_retries=4`); a claim that still fails is recorded as an error and the run continues with the next claim. Test owned by Task 7.
- A claim with no attachments at all: every required document is reported missing, no crash. Test owned by Task 5.
- Running without `ANTHROPIC_API_KEY` set: the runner stops before any call with `Missing ANTHROPIC_API_KEY: add it to .env`. Test owned by Task 7.

---

## File Structure

```
requirements.txt                         anthropic, python-dotenv, pytest
pyproject.toml                           pytest config: pythonpath = [".", "topics/01-prompt-vs-workflow-claimsflow"], testpaths
shared/__init__.py
shared/llm.py                            llm_call, extract_xml, Tracker, CallRecord, PRICES, cost_usd
tests/test_llm.py                        offline tests for shared/llm.py

topics/01-prompt-vs-workflow-claimsflow/
  claimsflow/__init__.py
  claimsflow/models.py                   dataclasses: Attachment, Claim, Policy, Customer, Figures, Result
  claimsflow/rules.py                    CLAIM_TYPES, LINE_FOR_TYPE, REQUIRED_DOCS, find_policy, compute_payout
  claimsflow/data.py                     loaders for policies, customers, claims, answer key
  claimsflow/prompts.py                  prompt templates and the shared result parser
  claimsflow/levels.py                   run_level0..run_level3, parallel()
  claimsflow/score.py                    Scores, score()
  claimsflow/run.py                      CLI runner, budget guard, run files
  claimsflow/report.py                   builds results.md from run files
  data/policies/car.md, water_damage.md, travel.md
  data/customers.json
  data/claims.json
  data/answer_key.json
  evals/test_rules.py, test_data.py, test_levels.py, test_score_run.py
  runs/                                  run output JSON (git-ignored)
  results.md
```

---

### Task 1: Shared LLM helper

**Files:**
- Create: `requirements.txt`, `pyproject.toml`, `shared/__init__.py`, `shared/llm.py`
- Modify: `.gitignore` (add `topics/*/runs/`)
- Test: `tests/test_llm.py`

**Interfaces:**
- Produces:
  - `@dataclass CallRecord(label: str, model: str, seconds: float, input_tokens: int, output_tokens: int, cache_write_tokens: int, cache_read_tokens: int)`
  - `class Tracker`: `records: list[CallRecord]`; `add(r: CallRecord) -> None` (thread-safe); `total_cost_usd() -> float`; `total_seconds() -> float`; `calls() -> int`
  - `PRICES: dict[str, dict[str, float]]` keyed by model id, values `{"input", "output", "cache_write", "cache_read"}` in USD per million tokens
  - `cost_usd(r: CallRecord) -> float`
  - `llm_call(prompt: str, *, cached_system: str = "", system: str = "", model: str | None = None, label: str = "", tracker: Tracker | None = None, max_tokens: int = 2048, client=None) -> str`
  - `extract_xml(text: str, tag: str) -> str` (returns `""` when the tag is missing)
  - `require_api_key() -> None` (raises `RuntimeError("Missing ANTHROPIC_API_KEY: add it to .env")`)

- [ ] **Step 1: Setup.** Write `requirements.txt` (`anthropic`, `python-dotenv`, `pytest`), `pyproject.toml` with `[tool.pytest.ini_options] pythonpath = [".", "topics/01-prompt-vs-workflow-claimsflow"]` and `testpaths = ["tests", "topics/01-prompt-vs-workflow-claimsflow/evals"]`, then run `.venv\Scripts\python -m pip install -r requirements.txt`. Expected: installs without error.

- [ ] **Step 2: Write failing tests** in `tests/test_llm.py`:

```python
def test_extract_xml_returns_inner_text_stripped():
    assert extract_xml("a <x> hi </x> b", "x") == "hi"

def test_extract_xml_missing_tag_returns_empty():
    assert extract_xml("nothing here", "x") == ""

def test_llm_call_records_tokens_and_uses_cache_block():
    fake = FakeClient(text="ok", input_tokens=100, output_tokens=20, cache_read=900, cache_write=0)
    t = Tracker()
    out = llm_call("hello", cached_system="POLICY TEXT", label="route", tracker=t, client=fake, model="claude-haiku-5-5")
    assert out == "ok"
    assert t.calls() == 1 and t.records[0].label == "route" and t.records[0].cache_read_tokens == 900
    system = fake.last_kwargs["system"]
    assert system[0]["text"] == "POLICY TEXT" and system[0]["cache_control"] == {"type": "ephemeral"}

def test_cost_usd_uses_prices_table():
    r = CallRecord("x", "claude-haiku-5-5", 1.0, 1_000_000, 0, 0, 0)
    assert cost_usd(r) == PRICES["claude-haiku-5-5"]["input"]

def test_require_api_key_message(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="Missing ANTHROPIC_API_KEY: add it to .env"):
        require_api_key()
```

`FakeClient` lives in the test file: an object with `.messages.create(**kwargs)` that stores `last_kwargs` and returns an object shaped like the SDK response (`.content[0].text`, `.usage.input_tokens`, `.usage.output_tokens`, `.usage.cache_read_input_tokens`, `.usage.cache_creation_input_tokens`).

- [ ] **Step 3: Run tests.** `.venv\Scripts\python -m pytest tests/test_llm.py -v` → FAIL (module missing).

- [ ] **Step 4: Implement `shared/llm.py`.** `llm_call` builds `system` as a list of text blocks: the `cached_system` block first with `cache_control={"type": "ephemeral"}` (only if non-empty), then `system` (if non-empty). Default client is a module-level `anthropic.Anthropic(max_retries=4)` created lazily after `load_dotenv()`. Time the call with `time.perf_counter()`. `Tracker.add` uses a `threading.Lock` (step 2 of the workflow calls it from threads). Fill `PRICES` from the `claude-api` skill for both default models.

- [ ] **Step 5: Run tests.** Same command → PASS.

- [ ] **Step 6: Commit.** First commit the existing topic docs on their own: `git add topics/01-prompt-vs-workflow-claimsflow/README.md topics/01-prompt-vs-workflow-claimsflow/design && git commit -m "Topic 1 design, diagram, plan and README skeleton"`. Then `git add requirements.txt pyproject.toml shared tests .gitignore && git commit -m "Shared LLM helper with call tracking and prompt caching"`

---

### Task 2: Domain model and policy rules

**Files:**
- Create: `topics/01-prompt-vs-workflow-claimsflow/claimsflow/__init__.py`, `claimsflow/models.py`, `claimsflow/rules.py`
- Test: `topics/01-prompt-vs-workflow-claimsflow/evals/test_rules.py`

**Interfaces:**
- Produces (`models.py`):
  - `Attachment(filename: str, text: str)`
  - `Claim(claim_id: str, customer_id: str, submitted: date, description: str, attachments: list[Attachment])`
  - `Policy(policy_number: str, line: str, start: date, end: date, deductible: int, cap: int | None, private_rate: float, addons: list[str], listed_drivers: list[dict], min_driver_age: int | None)` where `line` is `car`, `home` or `travel`
  - `Customer(customer_id: str, name: str, policies: list[Policy])`
  - `Figures(recognized_amount: int, provider: str | None = None)` with `provider` in `{"network", "private", None}`
  - `Result(decision: str, amount: int, doc_problems: list[str], reason: str, claim_type: str | None = None)`; `doc_problems == []` means documents complete
- Produces (`rules.py`):
  - `CLAIM_TYPES = ("car", "water_damage", "travel_medical", "travel_cancellation")`
  - `LINE_FOR_TYPE = {"car": "car", "water_damage": "home", "travel_medical": "travel", "travel_cancellation": "travel"}`
  - `REQUIRED_DOCS: dict[str, list[str]]`:
    - `car`: `claim_form`, `drivers_license`, `damage_photos`, `assessor_report`
    - `water_damage`: `claim_form`, `damage_photos`, `plumber_finding`, `repair_quote`
    - `travel_medical`: `claim_form`, `medical_summary`, `receipts`
    - `travel_cancellation`: `claim_form`, `cancellation_proof`, `payment_receipts`, `supplier_refund_letters`
  - `find_policy(customer: Customer, claim_type: str) -> Policy | None`
  - `compute_payout(policy: Policy, figures: Figures) -> tuple[int, str]` returning `(amount, decision)`

- [ ] **Step 1: Write failing tests** in `evals/test_rules.py` (build `Policy` objects inline):

```python
def test_car_worked_example():            # 12,000 − 1,500
    assert compute_payout(car_policy(deductible=1500, cap=None), Figures(12000)) == (10500, "approve_full")

def test_water_worked_example():          # 8,000 − 1,000
    assert compute_payout(home_policy(deductible=1000), Figures(8000, "network")) == (7000, "approve_full")

def test_water_private_plumber_is_partial():   # 8,000 × 0.9 − 1,000
    assert compute_payout(home_policy(deductible=1000, private_rate=0.9), Figures(8000, "private")) == (6200, "approve_partial")

def test_cancellation_worked_example():   # loss 7,000, cap 5,000, no deductible
    assert compute_payout(travel_policy(deductible=0, cap=5000), Figures(7000)) == (5000, "approve_partial")

def test_payout_never_negative():
    assert compute_payout(car_policy(deductible=1500, cap=None), Figures(900)) == (0, "approve_full")

def test_find_policy_by_line_and_missing_line():
    c = Customer("C1", "Dana Levi", [car_policy(), travel_policy()])
    assert find_policy(c, "travel_cancellation").line == "travel"
    assert find_policy(c, "water_damage") is None
```

- [ ] **Step 2: Run tests.** `.venv\Scripts\python -m pytest topics/01-prompt-vs-workflow-claimsflow/evals/test_rules.py -v` → FAIL.

- [ ] **Step 3: Implement.** `compute_payout` order: `base = round(recognized × rate)` where `rate = private_rate` if `provider == "private"` else `1.0`; `capped = min(base, cap)` if `cap` else `base`; `amount = max(0, capped − deductible)`; decision is `approve_partial` if `rate < 1.0` or `capped < base`, else `approve_full`. For travel cancellation, `recognized_amount` is already "paid in advance − supplier refunds" (computed by the caller, see Task 6).

- [ ] **Step 4: Run tests** → PASS.

- [ ] **Step 5: Commit.** `git commit -m "Claims domain model and payout rules"`

---

### Task 3: Test data, loaders, and the author review gate

**Files:**
- Create: `data/policies/car.md`, `data/policies/water_damage.md`, `data/policies/travel.md`, `data/customers.json`, `data/claims.json`, `data/answer_key.json` (all under `topics/01-prompt-vs-workflow-claimsflow/`), `claimsflow/data.py`
- Test: `evals/test_data.py`

**Interfaces:**
- Consumes: models and `REQUIRED_DOCS`, `CLAIM_TYPES` from Task 2.
- Produces (`data.py`, all default to the topic's `data/` folder):
  - `load_wordings() -> dict[str, str]` keyed by line (`car`, `home`, `travel`); file `water_damage.md` maps to key `home`
  - `load_customers() -> dict[str, Customer]`
  - `load_claims() -> list[Claim]`
  - `load_answer_key() -> dict[str, Result]`

Data content (from spec §2–§5):
- **Wordings:** made-up insurer "Meridian Mutual". 1–2 pages each. Covered events, exclusions (car: unlisted driver, driver under `min_driver_age`, event outside policy dates; home: no `water_damage` add-on, pipe wear or corrosion; travel: event outside trip dates, cancellation reason not on the covered list, pre-existing condition without its add-on), caps, deductibles, network vs private rate.
- **Customers:** about 15. Several hold more than one policy. Some lack a home policy (for the no-matching-policy case).
- **Claims:** 30 total: car 8, water damage 8, travel medical 6, travel cancellation 6, plus at least 1 unclear description (`hand_to_person`) and 1 with no matching policy (`decline`) drawn from those counts. Each claim has `customer_id` (not a policy number), `submitted`, `description`, `attachments` as `{filename, text}`. Attachment text stands in for the real document.
- **Tricky (about 10):** policy not active on the event date, unlisted driver, underage driver, missing assessor report, a driver's license in another person's name (wrong document), no water add-on, pipe corrosion, private plumber (partial), medical over the cap (partial), event outside trip dates, cancellation reason not covered, missing supplier refund letter.
- **Answer key:** per claim `claim_type`, `decision`, `amount`, `doc_problems` (list of required doc ids), `reason`. Apply the spec rules: recognized amount source per type (spec §3), date and driver problems → `decline` (not document problems), deductible alone → not partial.
- **The three worked examples appear as claims:** car 12,000/1,500 → 10,500; water 8,000/1,000 → 7,000; cancellation 10,000 − 3,000 with cap 5,000 → 5,000.

- [ ] **Step 1: Write failing tests** in `evals/test_data.py`:

```python
def test_counts():
    claims = load_claims()
    assert len(claims) == 30
    assert len(load_answer_key()) == 30

def test_every_claim_has_a_key_and_valid_values():
    key = load_answer_key()
    for c in load_claims():
        r = key[c.claim_id]
        assert r.decision in DECISIONS
        assert r.claim_type in CLAIM_TYPES or r.decision == "hand_to_person"
        assert all(d in REQUIRED_DOCS[r.claim_type] for d in r.doc_problems)
        assert (r.decision == "request_documents") == bool(r.doc_problems)

def test_every_claim_customer_exists():
    customers = load_customers()
    assert all(c.customer_id in customers for c in load_claims())

def test_answer_key_amounts_match_payout_rules():
    customers, claims = load_customers(), {c.claim_id: c for c in load_claims()}
    for cid, r in load_answer_key().items():
        if r.decision.startswith("approve"):
            policy = find_policy(customers[claims[cid].customer_id], r.claim_type)
            assert compute_payout(policy, r.figures) == (r.amount, r.decision), cid

def test_worked_examples_present():
    amounts = sorted(r.amount for r in load_answer_key().values())
    assert {10500, 7000, 5000} <= set(amounts)

def test_mix_of_decisions():
    decisions = {r.decision for r in load_answer_key().values()}
    assert decisions == {"approve_full", "approve_partial", "decline", "request_documents", "hand_to_person"}
```

The answer key also stores `figures` (`recognized_amount`, `provider`) per approved claim so `test_answer_key_amounts_match_payout_rules` can recompute every amount with `compute_payout`. For that, `Result` gets one more optional field in this task: `figures: Figures | None = None` (append it last in `models.py`). `DECISIONS = ("approve_full", "approve_partial", "decline", "request_documents", "hand_to_person")` is added to `rules.py`.

- [ ] **Step 2: Run tests** → FAIL.
- [ ] **Step 3: Write the wordings, customers, claims and answer key; implement `data.py`.**
- [ ] **Step 4: Run tests** → PASS.
- [ ] **Step 5: Commit.** `git commit -m "Made-up policies, customers, claims and answer key"`
- [ ] **Step 6: STOP: author review gate.** Show the author a one-page summary of the 30 claims (id, type, one-line story, expected decision, amount). Wait for corrections. Apply them, re-run `test_data.py`, commit `"Answer key reviewed by author"`. No measured run (Task 8) happens before this step is done.

---

### Task 4: Prompts, result parser, levels 0 and 1

**Files:**
- Create: `claimsflow/prompts.py`, `claimsflow/levels.py`
- Test: `evals/test_levels.py`

**Interfaces:**
- Consumes: `llm_call`, `extract_xml`, `Tracker` (Task 1); models, rules (Task 2); loaders (Task 3).
- Produces:
  - `@dataclass Ctx(customers: dict[str, Customer], wordings: dict[str, str], model: str, tracker: Tracker)`
  - `parse_result(text: str, claim_type: str | None) -> Result` (reads `<decision>`, `<amount>`, `<doc_problems>` as comma-separated ids or `none`, `<reason>`)
  - `normalize_type(label: str) -> str | None` (returns one of `CLAIM_TYPES` or `None`)
  - `run_level0(claim: Claim, ctx: Ctx) -> Result`
  - `run_level1(claim: Claim, ctx: Ctx) -> Result`
  - All LLM calls in `levels.py` go through the module-level name `llm_call` (so tests can monkeypatch `claimsflow.levels.llm_call`) and pass `label=` one of: `level0`, `route`, `decide`, `doc:<doc_id>`, `covered`, `excluded`, `figures`.

Behavior:
- **Level 0:** one call, label `level0`. Cached system: all three wordings, `REQUIRED_DOCS`, the decision rules from the spec (partial vs deductible, which document gives the recognized amount, date and driver problems are declines). User prompt: the customer's full record (all policies) and the claim with attachments. Output tags: `<claim_type>`, `<decision>`, `<amount>`, `<doc_problems>`, `<reason>`. The cached rules also tell it: unclear claim → `hand_to_person`; no policy of the needed line → `decline`. Level 0 gets the same information as the other levels, only in one call.
- **Level 1:** call `route` (description only, returns `<claim_type>` one of the four or `unclear`). `normalize_type` → `None` → `hand_to_person`. `find_policy` → `None` → `decline` with reason `"No matching policy"`. Else one `decide` call whose cached system holds only that line's wording and that type's required documents and rules; user prompt holds that one policy and the claim.

- [ ] **Step 1: Write failing tests** (a `fake_llm(responses: dict[str, str])` helper patches `claimsflow.levels.llm_call` and returns by label prefix):

```python
def test_normalize_type_handles_case_and_unknown():
    assert normalize_type(" Car ") == "car"
    assert normalize_type("water damage") == "water_damage"
    assert normalize_type("other") is None

def test_parse_result_messy_amount():
    r = parse_result("<decision>approve_full</decision><amount>10,500 ₪</amount><doc_problems>none</doc_problems><reason>ok</reason>", "car")
    assert (r.decision, r.amount, r.doc_problems) == ("approve_full", 10500, [])

def test_parse_result_missing_decision_is_error():
    assert parse_result("<amount>5</amount>", "car").decision == "error"

def test_level1_unknown_label_hands_to_person(monkeypatch):
    fake_llm(monkeypatch, {"route": "<claim_type>boat</claim_type>"})
    assert run_level1(claim_for("C1"), ctx()).decision == "hand_to_person"

def test_level1_no_matching_policy_declines(monkeypatch):
    fake_llm(monkeypatch, {"route": "<claim_type>water_damage</claim_type>"})
    r = run_level1(claim_for(customer_without_home), ctx())
    assert r.decision == "decline" and r.reason == "No matching policy"

def test_level1_calls_route_then_decide(monkeypatch):
    calls = fake_llm(monkeypatch, {"route": "<claim_type>car</claim_type>", "decide": FULL_APPROVE_XML})
    run_level1(claim_for(car_customer), ctx())
    assert [c.label for c in calls] == ["route", "decide"]

def test_level0_single_call(monkeypatch):
    calls = fake_llm(monkeypatch, {"level0": FULL_APPROVE_XML_WITH_TYPE})
    run_level0(claim_for(car_customer), ctx())
    assert [c.label for c in calls] == ["level0"]
```

- [ ] **Step 2: Run** `.venv\Scripts\python -m pytest topics/01-prompt-vs-workflow-claimsflow/evals/test_levels.py -v` → FAIL.
- [ ] **Step 3: Implement** `prompts.py` and the level 0/1 parts of `levels.py`.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit.** `git commit -m "Levels 0 and 1: one prompt and routing"`

---

### Task 5: Level 2, parallel document check

**Files:**
- Modify: `claimsflow/levels.py`, `claimsflow/prompts.py`
- Test: `evals/test_levels.py`

**Interfaces:**
- Consumes: Task 4 (`Ctx`, `normalize_type`, route and decide helpers).
- Produces:
  - `parallel(fn: Callable[[T], R], items: list[T], n_workers: int = 4) -> list[R]` (results in input order)
  - `check_documents(claim: Claim, claim_type: str, policy: Policy, ctx: Ctx) -> list[str]` (returns problem doc ids in `REQUIRED_DOCS` order; `[]` = complete)
  - `run_level2(claim: Claim, ctx: Ctx) -> Result`

Behavior: route and policy lookup as level 1. Then one call per required document, in parallel, label `doc:<doc_id>`. Each call sees the document requirement, the claim and the list of attachments, and answers `<status>ok</status>`, `<status>missing</status>` or `<status>wrong</status>` plus `<problem>` (one sentence). It checks only "is the paperwork there and does it belong to this claim" (spec §3 step 2): right kind, insured's name, details matching the claim. Any problem → `Result("request_documents", 0, problems, reason naming each problem, claim_type)`. Otherwise the level 1 `decide` call, told that documents were verified.

- [ ] **Step 1: Write failing tests:**

```python
def test_parallel_keeps_order():
    assert parallel(lambda x: x * 2, [3, 1, 2]) == [6, 2, 4]

def test_level2_missing_doc_requests_documents(monkeypatch):
    fake_llm(monkeypatch, {"route": "<claim_type>car</claim_type>",
                           "doc:assessor_report": "<status>missing</status><problem>No assessor report</problem>",
                           "doc:": "<status>ok</status>"})
    r = run_level2(claim_for(car_customer), ctx())
    assert r.decision == "request_documents" and r.doc_problems == ["assessor_report"] and r.amount == 0

def test_level2_one_doc_call_per_required_doc(monkeypatch):
    calls = fake_llm(monkeypatch, {"route": "<claim_type>travel_medical</claim_type>", "doc:": "<status>ok</status>", "decide": FULL_APPROVE_XML})
    run_level2(claim_for(travel_customer), ctx())
    assert sorted(c.label for c in calls if c.label.startswith("doc:")) == sorted(f"doc:{d}" for d in REQUIRED_DOCS["travel_medical"])

def test_level2_no_attachments_all_missing(monkeypatch):
    fake_llm(monkeypatch, {"route": "<claim_type>car</claim_type>", "doc:": "<status>missing</status><problem>Not attached</problem>"})
    r = run_level2(claim_with_no_attachments(car_customer), ctx())
    assert r.doc_problems == REQUIRED_DOCS["car"]
```

(The `fake_llm` helper matches the longest label prefix, so `doc:assessor_report` wins over `doc:`.)

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement.** `parallel` uses `concurrent.futures.ThreadPoolExecutor` as in the article.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit.** `git commit -m "Level 2: parallel document check"`

---

### Task 6: Level 3, the decision chain

**Files:**
- Modify: `claimsflow/levels.py`, `claimsflow/prompts.py`
- Test: `evals/test_levels.py`

**Interfaces:**
- Consumes: Tasks 2, 4, 5 (`compute_payout`, `Figures`, `check_documents`).
- Produces: `run_level3(claim: Claim, ctx: Ctx) -> Result`

Behavior: route, policy lookup and document check as level 2. Then in order:
1. `covered` call: is this event a covered event under this policy (policy active on the event date, right add-on bought, event type covered)? `<covered>yes|no</covered><reason>`. `no` → `decline` with that reason.
2. `excluded` call: does an exclusion apply (unlisted or underage driver, pipe wear or corrosion, reason not on the covered list, outside trip dates, pre-existing condition)? `<excluded>yes|no</excluded><reason>`. `yes` → `decline`.
3. `figures` call: read the numbers from the right document (spec §3 table): `<recognized_amount>`, `<provider>network|private|none</provider>`, and for travel cancellation `<paid>` and `<refunds>`. For travel cancellation, code sets `recognized_amount = paid − refunds`.
4. `compute_payout(policy, figures)` gives amount and decision. Reason is built in code from the numbers (for example `"12,000 − deductible 1,500 = 10,500"`).

- [ ] **Step 1: Write failing tests:**

```python
def test_level3_chain_order_and_code_math(monkeypatch):
    calls = fake_llm(monkeypatch, {"route": "<claim_type>car</claim_type>", "doc:": "<status>ok</status>",
        "covered": "<covered>yes</covered><reason>ok</reason>", "excluded": "<excluded>no</excluded><reason>ok</reason>",
        "figures": "<recognized_amount>12000</recognized_amount><provider>none</provider>"})
    r = run_level3(claim_for(car_customer_deductible_1500), ctx())
    assert (r.decision, r.amount) == ("approve_full", 10500)
    assert [c.label for c in calls if not c.label.startswith("doc:")] == ["route", "covered", "excluded", "figures"]

def test_level3_not_covered_stops_chain(monkeypatch):
    calls = fake_llm(monkeypatch, {"route": "<claim_type>car</claim_type>", "doc:": "<status>ok</status>",
        "covered": "<covered>no</covered><reason>Policy not active on the event date</reason>"})
    r = run_level3(claim_for(car_customer), ctx())
    assert r.decision == "decline" and "excluded" not in [c.label for c in calls]

def test_level3_cancellation_uses_paid_minus_refunds(monkeypatch):
    fake_llm(monkeypatch, {"route": "<claim_type>travel_cancellation</claim_type>", "doc:": "<status>ok</status>",
        "covered": "<covered>yes</covered><reason>ok</reason>", "excluded": "<excluded>no</excluded><reason>ok</reason>",
        "figures": "<paid>10000</paid><refunds>3000</refunds><provider>none</provider>"})
    r = run_level3(claim_for(travel_customer_cap_5000_no_deductible), ctx())
    assert (r.decision, r.amount) == ("approve_partial", 5000)
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit.** `git commit -m "Level 3: decision chain with code payout"`

---

### Task 7: Scoring, runner, budget guard, report

**Files:**
- Create: `claimsflow/score.py`, `claimsflow/run.py`, `claimsflow/report.py`, `topics/01-prompt-vs-workflow-claimsflow/results.md` (header only: "Not run yet")
- Test: `evals/test_score_run.py`

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `@dataclass Scores(n: int, decision_right: float, amount_right: float, doc_caught: float, doc_false_alarms: float, errors: int)`; rates are 0–1
  - `score(results: dict[str, Result], key: dict[str, Result]) -> Scores`:
    - `decision_right`: share with the same decision
    - `amount_right`: share with the exact same amount (all claims; declines and requests are 0)
    - `doc_caught`: among key claims with `doc_problems`, share where the result is `request_documents` with the same set of problem ids
    - `doc_false_alarms`: among key claims with no `doc_problems`, share where the result is `request_documents`
    - `errors`: count of `decision == "error"`
  - `estimate_cost_usd(level: str, claims: list[Claim], ctx: Ctx, repeats: int) -> float`: characters ÷ 4 as tokens, calls per claim by level (0: 1, 1: 2, 2: 2 + docs, 3: 5 + docs), priced with `PRICES`
  - `LEVELS: dict[str, Callable[[Claim, Ctx], Result]]` in `run.py`: `{"0": run_level0, "1": run_level1, "2": run_level2, "3": run_level3, "0+": run_level0}`
  - CLI: `.venv\Scripts\python -m claimsflow.run --level {0,1,2,3,0+} [--repeats 3] [--limit N] [--budget 10] [--yes] [--runs-dir PATH]`
    - calls `require_api_key()` first
    - measures **wall-clock seconds per claim** with `time.perf_counter()` around each level call (the tracker's summed call time overstates level 2 and 3, whose document calls overlap); the report's "seconds per claim" uses the wall clock
    - prints the estimate; aborts with exit code 2 if over `--budget`; asks for confirmation unless `--yes`
    - level `0+` runs `run_level0` with `CLAIMS_MODEL_LARGE`
    - a claim whose run raises after the SDK's retries is recorded as `Result("error", 0, [], str(exc))` and the run continues
    - writes `runs/level-<level>-<YYYYMMDD-HHMMSS>.json` with per-claim results, per-call records and scores per repeat
  - `.venv\Scripts\python -m claimsflow.report` rewrites `results.md`: one table (level, model, decision right, amount right, doc problems caught, false alarms, seconds per claim, $ per claim, calls per claim, cached share of input tokens), averaged over repeats, built only from files in `runs/`, with the run file names listed under the table. With no run files it writes "Not run yet".

The module is run from the topic folder (`cd topics/01-prompt-vs-workflow-claimsflow`) with `PYTHONPATH` set to the repo root, or via the pytest pythonpath. Document the exact command in `results.md`.

- [ ] **Step 1: Write failing tests:**

```python
def test_score_counts():
    key = {"a": R("approve_full", 100, []), "b": R("request_documents", 0, ["receipts"]), "c": R("decline", 0, [])}
    got = {"a": R("approve_full", 90, []), "b": R("request_documents", 0, ["receipts"]), "c": R("request_documents", 0, ["claim_form"])}
    s = score(got, key)
    assert (s.decision_right, s.amount_right, s.doc_caught, s.doc_false_alarms) == (2/3, 2/3, 1.0, 0.5)

def test_run_aborts_over_budget(monkeypatch, capsys):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setattr("claimsflow.run.estimate_cost_usd", lambda *a, **k: 12.0)
    assert main(["--level", "0", "--budget", "10", "--yes"]) == 2

def test_run_requires_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="Missing ANTHROPIC_API_KEY"):
        main(["--level", "0", "--yes"])

def test_run_continues_after_claim_error(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setattr("claimsflow.run.estimate_cost_usd", lambda *a, **k: 0.01)
    first = load_claims()[0].claim_id
    def flaky(claim, ctx):
        if claim.claim_id == first:
            raise RuntimeError("overloaded")
        return Result("decline", 0, [], "x", "car")
    monkeypatch.setitem(LEVELS, "0", flaky)
    assert main(["--level", "0", "--limit", "3", "--repeats", "1", "--yes", "--runs-dir", str(tmp_path)]) == 0
    run = json.loads(next(tmp_path.glob("level-0-*.json")).read_text())
    assert run["repeats"][0]["results"][first]["decision"] == "error"
    assert len(run["repeats"][0]["results"]) == 3

def test_report_without_runs_says_not_run(tmp_path):
    assert "Not run yet" in build_report(tmp_path)
```

`main(argv: list[str]) -> int` and `build_report(runs_dir: Path) -> str` are the testable entry points.

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement.** `load_dotenv()` at the top of `run.py`; the tracker's records go into the run file without any key or header.
- [ ] **Step 4: Run** the whole suite `.venv\Scripts\python -m pytest -v` → all PASS.
- [ ] **Step 5: Commit.** `git commit -m "Scoring, runner with budget guard, results report"`

---

### Task 8: Real runs and results

Needs: Task 3 Step 6 done (answer key reviewed) and `ANTHROPIC_API_KEY` filled in `.env`. If either is missing, stop and tell the author.

**Files:**
- Modify: `topics/01-prompt-vs-workflow-claimsflow/results.md` (generated), `topics/01-prompt-vs-workflow-claimsflow/README.md` ("What we found" table only)

- [ ] **Step 1: Smoke run.** `--level 3 --limit 2 --repeats 1 --yes`. Expected: estimate printed, 2 claims processed, a run file written. Read one result to confirm the call labels and that amounts are integers.
- [ ] **Step 2: Full runs.** Levels `0`, `1`, `2`, `3`, `0+`, each `--repeats 3`. Note the total spent from the run files.
- [ ] **Step 3: Report.** `python -m claimsflow.report` → `results.md`. Copy the averaged numbers into the README "What we found" table exactly as in `results.md`.
- [ ] **Step 4: Draft observations.** Under the README table, at most 5 one-line bullets, each pointing at a number in the table (for example, which level first catches document problems, cost ratio level 3 vs 0). Mark them `DRAFT`. Leave "When to use it" and "Caveats" for the author, with a list of facts they can use.
- [ ] **Step 5: Commit.** `git commit -m "Measured results for levels 0-3 and 0+"`
- [ ] **Step 6: Hand over to the author** with: total cost spent, the results table, and anything that looked wrong (for example a level with many `error` results).
