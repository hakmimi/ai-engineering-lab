# Topic 2: Prompt vs Workflow on ContractNLI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild topic 1's five levels (0, 1, 2, 3, 0+) on 60 real NDAs from ContractNLI and measure them against the dataset's own labels.

**Architecture:** A new package `ndaflow` in `topics/02-prompt-vs-workflow-contract-nli/`, shaped like topic 1's `claimsflow`: models → data → prompts → levels → score → run → report. It reuses `shared/llm.py` unchanged. A one-off builder script turns the downloaded ContractNLI files into two small committed sets (main = 30 dev NDAs, test = 30 test NDAs).

**Tech Stack:** Python 3, OpenAI Responses API via `shared.llm`, pytest, ThreadPoolExecutor.

**Spec:** `topics/02-prompt-vs-workflow-contract-nli/design/design.md`

## Global Constraints

- Branch `topic-02-contract-nli` (exists, cut from `topic-01-prompt-vs-workflow`). Commit locally; never push without the author's OK.
- Levels 0–3 use `default_model("small")` (gpt-6-luna); 0+ uses `default_model("large")` (gpt-6.1-sol). Call `load_env()` before choosing the model.
- Labels are exactly `entailment`, `contradiction`, `not_mentioned`; an unreadable answer is `error` and counts wrong.
- Statement ids are the dataset's: `nda-1 nda-2 nda-3 nda-4 nda-5 nda-7 nda-8 nda-10 nda-11 nda-12 nda-13 nda-15 nda-16 nda-17 nda-18 nda-19 nda-20` (17), always in this order.
- Span ids are the dataset's 0-based span indices.
- Main set: 30 NDAs from `dev.json`; test (held-out) set: 30 NDAs from `test.json`; drawn with `random.Random(2026).sample`, stored sorted by dataset id. The train split is never read.
- Never tune prompts on the test set. Results only from real runs. API keys only in `.env`.
- Every committed data file carries attribution: ContractNLI, Koreeda & Manning 2021, CC BY 4.0.
- Tests never touch the network (root `conftest.py` already enforces this).

## Review Focus

1. **Router answers in the wrong shape** (no `<nda-5>` tag for a statement): that statement becomes `error`, never silently `not_mentioned`. Test in Task 3.
2. **Made-up span numbers** (outside the contract, or outside the spans the router picked): dropped, never crash, never scored as evidence. Test in Task 2 and Task 5.
3. **Label spelling drift** (`NotMentioned`, `Not mentioned`, `ENTAILMENT`): read as the right label. Test in Task 2.
4. **Router picks nothing for any statement:** all 17 are `not_mentioned`, and no decide call is made. Test in Task 3.
5. **No contradiction pairs in a set slice** (e.g. `--limit 2`): F1 is 0.0, not a ZeroDivisionError. Test in Task 6.

---

### Task 1: Data — build the two sets, load them

**Files:**
- Create: `topics/02-prompt-vs-workflow-contract-nli/ndaflow/__init__.py` (empty), `ndaflow/models.py`, `ndaflow/data.py`, `ndaflow/build_data.py`
- Create (generated, committed): `topics/02-prompt-vs-workflow-contract-nli/data/main.json`, `data/test.json`, `data/statements.json`, `data/NOTICE.md`
- Modify: `pyproject.toml` (add `"topics/02-prompt-vs-workflow-contract-nli"` to `pythonpath`, `"topics/02-prompt-vs-workflow-contract-nli/evals"` to `testpaths`)
- Test: `topics/02-prompt-vs-workflow-contract-nli/evals/test_nda_data.py`, `evals/nda_helpers.py`

The evals folder has **no `__init__.py`** and every file name starts with `nda_` or `test_nda_`, so it can't clash with topic 1's `evals` package (pytest's default import mode puts the folder on `sys.path`).

**Interfaces:**
- Produces (`ndaflow/models.py`):
  - `LABELS = ("entailment", "contradiction", "not_mentioned")`
  - `@dataclass Statement(sid: str, short: str, text: str)`
  - `@dataclass Contract(doc_id: str, file_name: str, spans: list[str])` (span text, stripped; index = span id)
  - `@dataclass Answer(label: str, evidence: list[int] = [])` (label in LABELS or `"error"`)
  - type alias `Answers = dict[str, Answer]` (by statement id)
- Produces (`ndaflow/data.py`): `DATA: Path`, `SETS = {"main": DATA / "main.json", "test": DATA / "test.json"}`, `load_statements() -> list[Statement]`, `load_contracts(set_name: str) -> list[Contract]`, `load_answer_key(set_name: str) -> dict[str, Answers]`
- Produces (`ndaflow/build_data.py`): `build_set(raw: dict, n: int, seed: int) -> list[dict]`, `main(argv) -> int` with CLI `python -m ndaflow.build_data <path to contract-nli folder>`
- Set file shape: `{"source": ..., "licence": "CC BY 4.0", "split": "dev", "seed": 2026, "contracts": [{"doc_id": "34", "file_name": ..., "url": ..., "spans": [...], "key": {"nda-1": {"label": "entailment", "evidence": [12, 13]}, ...}}]}`

- [ ] **Step 1: Write the failing tests** in `evals/test_nda_data.py`, with a tiny fake raw dataset (3 documents, 2 labels) in `nda_helpers.py`:

```python
def test_build_set_maps_labels_and_span_text():
    out = build_set(FAKE_RAW, n=2, seed=2026)
    assert [c["doc_id"] for c in out] == sorted((c["doc_id"] for c in out), key=int)
    c = next(c for c in out if c["doc_id"] == "1")
    assert c["spans"][0] == "NON-DISCLOSURE AGREEMENT"           # text[s:e].strip()
    assert c["key"]["nda-1"] == {"label": "entailment", "evidence": [1]}
    assert c["key"]["nda-2"] == {"label": "not_mentioned", "evidence": []}

def test_build_set_is_repeatable():
    assert build_set(FAKE_RAW, 2, 2026) == build_set(FAKE_RAW, 2, 2026)

def test_committed_sets_have_30_contracts_each_and_do_not_overlap():
    main, test = load_contracts("main"), load_contracts("test")
    assert len(main) == len(test) == 30
    assert not {c.doc_id for c in main} & {c.doc_id for c in test}

def test_every_key_covers_the_17_statements_with_valid_evidence():
    ids = [s.sid for s in load_statements()]
    assert ids == STATEMENT_IDS                     # the 17 ids from Global Constraints, in order
    for set_name in SETS:
        contracts = {c.doc_id: c for c in load_contracts(set_name)}
        for doc_id, answers in load_answer_key(set_name).items():
            assert list(answers) == ids
            for a in answers.values():
                assert a.label in LABELS
                assert (a.label == "not_mentioned") == (a.evidence == [])
                assert all(0 <= i < len(contracts[doc_id].spans) for i in a.evidence)
```

- [ ] **Step 2: Run** `.venv\Scripts\python -m pytest topics/02-prompt-vs-workflow-contract-nli/evals -q` — Expected: FAIL (`ModuleNotFoundError: ndaflow`).
- [ ] **Step 3: Implement** `models.py`, `build_data.py` (label map `Entailment→entailment, Contradiction→contradiction, NotMentioned→not_mentioned`; `statements.json` is written from the raw `labels` in the Global Constraints order; NOTICE.md gives citation, URL, licence and "60 of 607 NDAs, unchanged text"), and `data.py`.
- [ ] **Step 4: Generate the data:** `.venv\Scripts\python -m ndaflow.build_data <scratchpad>\contractnli-dl\x\contract-nli` — Expected: prints `main: 30 contracts (dev)`, `test: 30 contracts (test)`.
- [ ] **Step 5: Run the tests** — Expected: PASS (topic 1's suite still passes too: `.venv\Scripts\python -m pytest -q`).
- [ ] **Step 6: Commit** `Topic 2: ContractNLI sets (30 dev + 30 test NDAs) and loaders`.

### Task 2: Prompts, answer parsing, level 0

**Files:**
- Create: `ndaflow/prompts.py`, `ndaflow/levels.py`
- Test: `evals/test_nda_levels.py`, extend `evals/nda_helpers.py` with `fake_llm(monkeypatch, responses)` (same contract as topic 1's: patches `ndaflow.levels.llm_call`, answers by the longest label prefix, records calls) and `ctx()`

**Interfaces:**
- Produces (`prompts.py`): `render_contract(c: Contract, span_ids: list[int] | None = None) -> str` (lines `[12] text`; `None` = all spans; empty spans skipped, numbering kept); `statements_text(statements) -> str`; `LEVEL0_SYSTEM(statements) -> str` (role, label rules, the 17 statements, answer format: one `<nda-N><label>…</label><evidence>ids or none</evidence></nda-N>` block per statement).
- Produces (`levels.py`):
  - `@dataclass Ctx(statements: list[Statement], model: str, tracker: Tracker)`
  - `normalize_label(raw: str) -> str | None` (case, spaces, hyphens and `notmentioned` tolerated)
  - `parse_span_ids(raw: str, valid: set[int]) -> list[int]` (all integers via `re.findall(r"\d+")`, keep those in `valid`, unique, sorted; `none`/empty → `[]`)
  - `parse_answer(block: str, valid: set[int]) -> Answer` (unreadable label → `Answer("error")`; `not_mentioned` → evidence `[]`)
  - `parse_answers(text: str, sids: list[str], valid: dict[str, set[int]]) -> Answers` (missing tag → `error`)
  - `run_level0(contract: Contract, ctx: Ctx) -> Answers` (one call, label `"level0"`, system cached)

- [ ] **Step 1: Write the failing tests:**

```python
@pytest.mark.parametrize("raw", ["NotMentioned", "Not mentioned", "not-mentioned", " not_mentioned "])
def test_normalize_label_reads_spelling_variants(raw):
    assert normalize_label(raw) == "not_mentioned"

def test_parse_span_ids_drops_made_up_numbers():
    assert parse_span_ids("[3], 7, 7, 99", valid={3, 7, 8}) == [3, 7]
    assert parse_span_ids("none", valid={1}) == []

def test_level0_reads_17_answers_and_a_missing_tag_is_an_error(monkeypatch):
    text = "".join(f"<{s}><label>entailment</label><evidence>1</evidence></{s}>" for s in STATEMENT_IDS[:-1])
    calls = fake_llm(monkeypatch, {"level0": text})
    out = run_level0(SMALL_CONTRACT, ctx())
    assert len(calls) == 1 and out["nda-1"] == Answer("entailment", [1])
    assert out[STATEMENT_IDS[-1]].label == "error"

def test_level0_prompt_shows_numbered_spans_and_caches_the_statements(monkeypatch):
    calls = fake_llm(monkeypatch, {"level0": ""})
    run_level0(SMALL_CONTRACT, ctx())
    assert "[1] " + SMALL_CONTRACT.spans[1] in calls[0].prompt
    assert "nda-20" in calls[0].kwargs["cached_system"]
```

- [ ] **Step 2: Run** `pytest topics/02-prompt-vs-workflow-contract-nli/evals/test_nda_levels.py -q` — Expected: FAIL (import error).
- [ ] **Step 3: Implement** `prompts.py` and the listed `levels.py` functions. Label rules in the prompt: entailment = the contract says it; contradiction = the contract says the opposite or forbids it; not_mentioned = the contract does not address it; evidence = every span that supports the label.
- [ ] **Step 4: Run** — Expected: PASS.
- [ ] **Step 5: Commit** `Topic 2: prompts, answer parsing, level 0`.

### Task 3: Route + level 1

**Files:** Modify `ndaflow/prompts.py`, `ndaflow/levels.py`; Test `evals/test_nda_levels.py`

**Interfaces:**
- Produces: `ROUTE_SYSTEM(statements) -> str` (answer: one `<nda-N>span ids or none</nda-N>` per statement); `route(contract, ctx) -> dict[str, list[int] | None]` (label `"route"`; `None` = tag missing; ids filtered to the contract's spans); `DECIDE_SYSTEM -> str`; `run_level1(contract, ctx) -> Answers`.
- Level 1 rule: `None` → `error`; `[]` → `not_mentioned` with no call; the rest go to **one** decide call (label `"decide"`) that shows, per statement, only its picked spans. Evidence valid set per statement = its picked spans.

- [ ] **Step 1: Write the failing tests:**

```python
def test_level1_router_gap_is_an_error_not_a_silent_not_mentioned(monkeypatch): ...
    # route answers tags for all but nda-20 → out["nda-20"].label == "error"
def test_level1_nothing_picked_means_all_not_mentioned_and_no_decide_call(monkeypatch): ...
    # route answers "none" for all 17 → every label not_mentioned, labels called == ["route"]
def test_level1_decide_sees_only_picked_spans(monkeypatch): ...
    # route picks [1] for nda-1 only → decide prompt contains span 1's text, not span 2's;
    # decide answers evidence "1, 2" → out["nda-1"].evidence == [1]  (2 was not picked)
```

- [ ] **Step 2: Run** — Expected: FAIL (`route` / `run_level1` not defined).
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** — Expected: PASS.
- [ ] **Step 5: Commit** `Topic 2: router picks spans, level 1`.

### Task 4: Level 2 — one call per statement, in parallel

**Files:** Modify `prompts.py`, `levels.py`; Test `evals/test_nda_levels.py`

**Interfaces:**
- Consumes: `route`, `parse_answer`.
- Produces: `parallel(fn, items, n_workers=8) -> list` (input order kept, as topic 1); `DECIDE_ONE_SYSTEM -> str` (answer: `<label>…</label><evidence>ids or none</evidence>`); `run_level2(contract, ctx) -> Answers` (labels `"one:nda-N"`, one call per statement that has picked spans; same `None`/`[]` rules as level 1).

- [ ] **Step 1: Write the failing tests:** `test_level2_makes_one_call_per_routed_statement` (route picks spans for 3 statements → exactly 3 `one:` calls, each prompt holds only its statement's text and spans) and `test_level2_keeps_statement_order` (answers come back keyed correctly even though calls finish in any order).
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** — Expected: PASS.
- [ ] **Step 5: Commit** `Topic 2: level 2, statements checked in parallel`.

### Task 5: Level 3 — evidence first, then the label

**Files:** Modify `prompts.py`, `levels.py`; Test `evals/test_nda_levels.py`

**Interfaces:**
- Produces: `EVIDENCE_SYSTEM -> str` (answer `<evidence>ids or none</evidence>`: which shown spans speak to the statement, for or against); `LABEL_SYSTEM -> str` (answer `<label>entailment, contradiction or not_mentioned</label>`, given only the evidence spans); `run_level3(contract, ctx) -> Answers`.
- Per statement (statements run in `parallel`): step A label `"evidence:nda-N"` → `parse_span_ids(valid = picked spans)`; empty → `not_mentioned`, no step B. Step B label `"label:nda-N"` → `entailment`/`contradiction` keeps the step-A evidence; `not_mentioned` → evidence `[]`; unreadable → `error`.
  - Ruling carried from the design: step B may answer `not_mentioned` (the spans turned out not to decide it). The spec says "entailment or contradiction?"; allowing the third answer avoids forcing a wrong yes/no.

- [ ] **Step 1: Write the failing tests:** `test_level3_no_evidence_skips_the_label_call`, `test_level3_evidence_outside_the_picked_spans_is_dropped` (step A answers `"1, 9"`, picked `[1, 2]` → evidence `[1]`), `test_level3_label_step_sees_only_the_evidence_spans`, `test_level3_unreadable_label_is_an_error`.
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** — Expected: PASS.
- [ ] **Step 5: Commit** `Topic 2: level 3 chain, evidence then label`.

### Task 6: Scoring

**Files:** Create `ndaflow/score.py`; Test `evals/test_nda_score.py`

**Interfaces:**
- Produces: `@dataclass Scores(n_pairs: int, label_right: float, f1_entailment: float, f1_contradiction: float, evidence_recall: float, evidence_precision: float, errors: int)` with `as_dict()`; `score(results: dict[str, Answers], key: dict[str, Answers]) -> Scores`.
- Pairs = every (doc, statement) in the key whose doc is in `results`.
- F1 for class c: `2·tp / (2·tp + fp + fn)`, 0.0 when the denominator is 0.
- Evidence recall (micro): over pairs whose **key** label is not `not_mentioned`: Σ|pred ∩ key| / Σ|key|.
- Evidence precision (micro): over pairs with predicted evidence: Σ|pred ∩ key| / Σ|pred|; 0.0 when nothing was predicted.
- `error` counts as a wrong label and in `errors`.

- [ ] **Step 1: Write the failing tests:** a hand-made 2-doc key and result where you can count by hand: `label_right == 0.75`, `f1_entailment == 2/3`, `evidence_recall == 0.5`, `evidence_precision == 1/3`, `errors == 1`; plus `test_no_contradictions_gives_f1_zero_not_a_crash`.
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** — Expected: PASS.
- [ ] **Step 5: Commit** `Topic 2: scoring (accuracy, F1 per label, evidence)`.

### Task 7: Runner and report

**Files:** Create `ndaflow/run.py`, `ndaflow/report.py`, `topics/02-prompt-vs-workflow-contract-nli/results.md` (generated "Not run yet"); Test `evals/test_nda_run.py`

**Interfaces:**
- Produces (`run.py`): `RUNS_DIR`, `LEVELS = {"0","1","2","3","0+"}` → run functions (0+ = `run_level0`), `model_for(level)`, `estimate_cost_usd(level, contracts, model, repeats) -> float`, `main(argv) -> int`. Same flags as topic 1 (`--level --repeats --limit --budget --workers --yes --dry-run --runs-dir --set main|test`). The test set saves to `runs_dir / "test"`. Run file: `{"level", "model", "set", "created", "contracts", "repeats": [{"results": {doc_id: {"answers": {sid: {"label", "evidence"}}, "seconds", "calls", "cost_usd"}}, "scores": {...}}]}`.
  - An exception inside one contract → all 17 answers `error`, the run continues.
  - Estimate (upper side, no cache discount): calls per contract `{"0":1, "0+":1, "1":2, "2":18, "3":35}`; every call costs `(len(render_contract(c)) + 4000) / 4` input tokens and 1,500 output tokens.
- Produces (`report.py`): `build_results(runs_dir) -> str` with `## Main set` and `## Test set (held out)` sections, columns: Level | Model | Label right | F1 entailment | F1 contradiction | Evidence found | Evidence precision | Seconds / contract | $ / contract | Calls / contract | Cached input | Errors / repeat. Re-scores against the current key (as topic 1). Smoke runs live in `runs/smoke/` and are never read by the report.

- [ ] **Step 1: Write the failing tests** (copy topic 1's `test_score_run.py` patterns): run on the main set with a fake level writes a run file with 17 answers per contract; `--set test` writes under `runs/test`; an exception inside a level gives 17 `error` answers; `--dry-run` makes no call; the report has both sections and re-scores against the key; `model_for("0+") == "gpt-6.1-sol"` with no env.
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement; generate** `results.md` with `python -m ndaflow.report`.
- [ ] **Step 4: Run the whole suite** `.venv\Scripts\python -m pytest -q` — Expected: all pass (topic 1's 73 plus topic 2's).
- [ ] **Step 5: Commit** `Topic 2: runner and report`.

### Task 8: Diagram and README skeleton

**Files:** Create `design/process-diagram.html`, `design/process-diagram.png`, `topics/02-prompt-vs-workflow-contract-nli/README.md`

- [ ] **Step 1:** Diagram in topic 1's style: NDA + 17 statements → route (pick spans per statement) → parallel (one check per statement) → chain (evidence → code checks span ids → label). PNG via headless Chrome screenshot, cropped as in topic 1.
- [ ] **Step 2:** README with topic 1's section order (Why → Spoiler/bottom line → What I did → The use case + diagram → KPIs → What's in the folder → Results: main → Observations: test set → When to use what → Caveats → Next time → How to run). "Found" sections hold only `<!-- notes, filled from real runs -->` and "Not run yet". Data credit (ContractNLI, CC BY 4.0) in the use-case section.
- [ ] **Step 3: Commit** `Topic 2: process diagram and README skeleton`.

### Task 9: Smoke run (real API, about $0.10) — then stop for the author

- [ ] **Step 1:** `--dry-run` for every level on both sets; Expected: total estimate under $10.
- [ ] **Step 2:** Level 0 and level 3, main set, `--limit 2 --repeats 1 --yes --runs-dir topics/02-prompt-vs-workflow-contract-nli/runs/smoke`. Expected: 0 errors; read the raw answers of both contracts by eye for parsing problems.
- [ ] **Step 3:** Ledger the spend and what the smoke run showed. **Stop and ask the author** before the full runs (real money).

### Task 10: Full runs and results (after the author's OK)

- [ ] **Step 1:** All five levels × main set × 3 repeats; read the errors and any glue failures. Fixes on the main set only, each with a failing test first, and each fix + rerun ledgered.
- [ ] **Step 2:** All five levels × test set × 3 repeats. No prompt changes after this point.
- [ ] **Step 3:** `python -m ndaflow.report`; fill the README's "found" sections with short notes from `results.md` only, for the author to rewrite.
- [ ] **Step 4: Commit** `Topic 2: results`.
