"""Load the two ContractNLI sets and the 17 statements from data/."""

from __future__ import annotations

import json
from pathlib import Path

from ndaflow.models import Answer, Answers, Contract, Statement

DATA = Path(__file__).resolve().parent.parent / "data"
SETS = {"main": DATA / "main.json", "test": DATA / "test.json"}  # test = held out, never tuned on


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_statements() -> list[Statement]:
    return [Statement(s["sid"], s["short"], s["text"]) for s in _read(DATA / "statements.json")]


def load_contracts(set_name: str) -> list[Contract]:
    return [Contract(c["doc_id"], c["file_name"], c["spans"]) for c in _read(SETS[set_name])["contracts"]]


def load_answer_key(set_name: str) -> dict[str, Answers]:
    return {
        c["doc_id"]: {sid: Answer(a["label"], a["evidence"]) for sid, a in c["key"].items()}
        for c in _read(SETS[set_name])["contracts"]
    }
