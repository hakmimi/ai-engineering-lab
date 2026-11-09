"""The levels we compare. Each takes a contract and returns an Answer per statement.

Level 0: one big prompt (the whole contract, all 17 statements).
Level 1: route first (pick the spans for each statement), then one prompt that sees only the picked spans.
Level 2: + one call per statement, all at the same time, each with only its own picked spans.
Level 3: + per statement, a chain: which picked spans are evidence? (code checks the numbers) -> then the label.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable, TypeVar

from ndaflow import prompts
from ndaflow.models import LABELS, Answer, Answers, Contract, Statement
from shared.llm import Tracker, extract_xml, llm_call

_LABEL_KEYS = {"entailment": "entailment", "contradiction": "contradiction", "notmentioned": "not_mentioned"}


@dataclass
class Ctx:
    statements: list[Statement]
    model: str
    tracker: Tracker


# ---------------------------------------------------------------- parsing
def normalize_label(raw: str) -> str | None:
    return _LABEL_KEYS.get(re.sub(r"[\s\-_]+", "", raw.lower()))


def read_label(text: str) -> str | None:
    """Trust <label> when present; otherwise accept the one label the text names.

    The small model sometimes writes the right label in the wrong tag (<contradiction>), as topic 1's router did.
    Two or more labels named means we can't tell: None.
    """
    tagged = extract_xml(text, "label")
    if tagged:
        return normalize_label(tagged)
    flat = re.sub(r"[\s\-]+", "_", text.lower())
    found = {lab for lab in LABELS if re.search(rf"(?<![a-z]){lab}(?![a-z])", flat)}
    return found.pop() if len(found) == 1 else None


def parse_span_ids(raw: str, valid: set[int]) -> list[int]:
    """Every number in the text that is a real span id here; made-up numbers are dropped."""
    return sorted({int(n) for n in re.findall(r"\d+", raw)} & valid)


def parse_answer(block: str, valid: set[int]) -> Answer:
    label = read_label(block)
    if label is None:
        return Answer("error")
    if label == "not_mentioned":
        return Answer(label)
    return Answer(label, parse_span_ids(extract_xml(block, "evidence"), valid))


def parse_answers(text: str, sids: list[str], valid: dict[str, set[int]]) -> Answers:
    """One <nda-N> block per statement; a missing block is an error, never a quiet default."""
    out = {}
    for sid in sids:
        block = extract_xml(text, sid)
        out[sid] = parse_answer(block, valid[sid]) if block else Answer("error")
    return out


def _filled(c: Contract) -> set[int]:
    return {i for i, s in enumerate(c.spans) if s}


def _call(ctx: Ctx, prompt: str, label: str, cached_system: str) -> str:
    return llm_call(prompt, cached_system=cached_system, model=ctx.model, label=label, tracker=ctx.tracker)


# ---------------------------------------------------------------- level 0
def run_level0(contract: Contract, ctx: Ctx) -> Answers:
    text = _call(ctx, prompts.contract_prompt(contract), "level0", prompts.level0_system(ctx.statements))
    sids = [s.sid for s in ctx.statements]
    every = _filled(contract)
    return parse_answers(text, sids, {sid: every for sid in sids})


# ---------------------------------------------------------------- level 1
Routes = dict[str, "list[int] | None"]  # None = the router left the statement out


def route(contract: Contract, ctx: Ctx) -> Routes:
    """Ask which spans matter for each statement. Missing tag -> None; 'none' -> []."""
    text = _call(ctx, prompts.contract_prompt(contract), "route", prompts.route_system(ctx.statements))
    every = _filled(contract)
    out: Routes = {}
    for s in ctx.statements:
        # Close at the next </nda-N> of any number: the router sometimes echoes a span number there (<nda-7>11</nda-11>).
        m = re.search(rf"<{s.sid}>(.*?)</nda-\d+>", text, re.DOTALL)
        out[s.sid] = parse_span_ids(m.group(1), every) if m else None
    return out


def _early(routes: Routes) -> Answers:
    """Answers code can give without another call: router gap -> error, nothing picked -> not_mentioned."""
    return {sid: Answer("error") if ids is None else Answer("not_mentioned") for sid, ids in routes.items() if not ids}


def run_level1(contract: Contract, ctx: Ctx) -> Answers:
    routes = route(contract, ctx)
    out = _early(routes)
    todo = [s for s in ctx.statements if s.sid not in out]
    if todo:
        prompt = f"Contract {contract.doc_id}\n\n" + "\n\n".join(prompts.routed_section(contract, s, routes[s.sid]) for s in todo)
        text = _call(ctx, prompt, "decide", prompts.DECIDE_SYSTEM)
        out.update(parse_answers(text, [s.sid for s in todo], {s.sid: set(routes[s.sid]) for s in todo}))
    return {s.sid: out[s.sid] for s in ctx.statements}


# ---------------------------------------------------------------- level 2
T = TypeVar("T")
R = TypeVar("R")


def parallel(fn: Callable[[T], R], items: list[T], n_workers: int = 8) -> list[R]:
    """Run fn on every item at the same time; results come back in input order."""
    if not items:
        return []
    with ThreadPoolExecutor(max_workers=n_workers) as pool:
        return list(pool.map(fn, items))


def run_level2(contract: Contract, ctx: Ctx) -> Answers:
    routes = route(contract, ctx)
    out = _early(routes)
    todo = [s for s in ctx.statements if s.sid not in out]

    def decide_one(s: Statement) -> Answer:
        text = _call(ctx, prompts.routed_section(contract, s, routes[s.sid]), f"one:{s.sid}", prompts.DECIDE_ONE_SYSTEM)
        return parse_answer(text, set(routes[s.sid]))

    out.update(zip([s.sid for s in todo], parallel(decide_one, todo)))
    return {s.sid: out[s.sid] for s in ctx.statements}


# ---------------------------------------------------------------- level 3
def run_level3(contract: Contract, ctx: Ctx) -> Answers:
    routes = route(contract, ctx)
    out = _early(routes)
    todo = [s for s in ctx.statements if s.sid not in out]

    def chain(s: Statement) -> Answer:
        picked = routes[s.sid]
        text = _call(ctx, prompts.routed_section(contract, s, picked), f"evidence:{s.sid}", prompts.EVIDENCE_SYSTEM)
        if not re.search(r"<evidence>.*?</evidence>", text, re.DOTALL):
            return Answer("error")
        evidence = parse_span_ids(extract_xml(text, "evidence"), set(picked))  # code keeps only real, picked spans
        if not evidence:
            return Answer("not_mentioned")
        text = _call(ctx, prompts.routed_section(contract, s, evidence), f"label:{s.sid}", prompts.LABEL_SYSTEM)
        label = read_label(text)
        if label is None:
            return Answer("error")
        return Answer(label, [] if label == "not_mentioned" else evidence)

    out.update(zip([s.sid for s in todo], parallel(chain, todo)))
    return {s.sid: out[s.sid] for s in ctx.statements}
