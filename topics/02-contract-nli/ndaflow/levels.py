"""The levels we compare. Each takes a contract and returns an Answer per statement.

Level 0: one big prompt (the whole contract, all 17 statements).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ndaflow import prompts
from ndaflow.models import Answer, Answers, Contract, Statement
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


def parse_span_ids(raw: str, valid: set[int]) -> list[int]:
    """Every number in the text that is a real span id here; made-up numbers are dropped."""
    return sorted({int(n) for n in re.findall(r"\d+", raw)} & valid)


def parse_answer(block: str, valid: set[int]) -> Answer:
    label = normalize_label(extract_xml(block, "label"))
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
