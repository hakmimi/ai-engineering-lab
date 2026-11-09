"""Contract packs (the big, fixed part of every prompt), the questions asked about them, and answer reading."""

from __future__ import annotations

import random
from dataclasses import dataclass

from ndaflow import data
from ndaflow.levels import parse_answer
from ndaflow.models import Answer, Contract, Statement
from ndaflow.prompts import LABEL_RULES, ROLE, render_contract
from shared.llm import extract_xml

PING = "Reply with OK."  # tests 0, 1 and the test 3 warm-up: the shortest useful question


def est_tokens(text: str) -> int:
    """Planning estimate only (about 4 characters per token); real counts come from the API's usage."""
    return len(text) // 4


@dataclass
class Pack:
    name: str
    contracts: list[Contract]
    codes: list[str]  # C01, C02, ... in pack order
    text: str

    @property
    def est_tokens(self) -> int:
        return est_tokens(self.text)

    def contract(self, code: str) -> Contract:
        return self.contracts[self.codes.index(code)]


def make_pack(name: str, contracts: list[Contract]) -> Pack:
    codes = [f"C{i:02d}" for i in range(1, len(contracts) + 1)]
    text = "\n\n".join(f"## Contract {code}\n{render_contract(c)}" for code, c in zip(codes, contracts))
    return Pack(name, list(contracts), codes, text)


def all_contracts() -> list[Contract]:
    """Main set, then the held-out set, each in stored order (only used as reading material in test 1)."""
    return data.load_contracts("main") + data.load_contracts("test")


def stack_to(contracts: list[Contract], target_tokens: int) -> list[Contract]:
    for n in range(1, len(contracts) + 1):
        if est_tokens(make_pack("stack", contracts[:n]).text) >= target_tokens:
            return contracts[:n]
    raise ValueError(f"not enough NDAs for {target_tokens} tokens")


@dataclass
class Question:
    code: str
    doc_id: str
    sid: str
    text: str


def short_questions(pack: Pack, statements: list[Statement]) -> list[Question]:
    c = pack.contracts[0]
    return [Question(pack.codes[0], c.doc_id, s.sid, s.text) for s in statements]


def long_questions(pack: Pack, statements: list[Statement], n: int, rng: random.Random) -> list[Question]:
    picks = rng.sample(range(len(pack.contracts)), n)
    out = []
    for i in picks:
        s = rng.choice(statements)
        out.append(Question(pack.codes[i], pack.contracts[i].doc_id, s.sid, s.text))
    return out


ANSWER_FORMAT = (
    "## Answer format\n"
    "Each question names one contract from the pack and one statement. Judge only that contract. Answer with one block:\n"
    "<answer><label>entailment, contradiction or not_mentioned</label><evidence>span numbers, or none</evidence></answer>"
)


def instructions(nonce: str | None) -> str:
    """Fixed system text. A nonce line, when given, goes first so it changes the whole prompt start (no cache match)."""
    body = "\n\n".join([ROLE, "The user message holds a pack of NDAs; each span starts with its number.", LABEL_RULES, ANSWER_FORMAT])
    return f"{nonce}\n{body}" if nonce else body


def question_text(q: Question) -> str:
    return f"Contract {q.code}: {q.text}"


def read_answer(text: str, contract: Contract) -> Answer:
    block = extract_xml(text, "answer")
    if not block:
        return Answer("error")
    return parse_answer(block, {i for i, s in enumerate(contract.spans) if s})
