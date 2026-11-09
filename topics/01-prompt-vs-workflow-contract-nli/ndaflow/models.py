"""The shapes every level reads and returns."""

from __future__ import annotations

from dataclasses import dataclass, field

LABELS = ("entailment", "contradiction", "not_mentioned")

# The dataset's 17 statement ids, in the order every prompt and file uses.
STATEMENT_IDS = [
    "nda-1", "nda-2", "nda-3", "nda-4", "nda-5", "nda-7", "nda-8", "nda-10", "nda-11",
    "nda-12", "nda-13", "nda-15", "nda-16", "nda-17", "nda-18", "nda-19", "nda-20",
]


@dataclass
class Statement:
    sid: str  # nda-1 ... nda-20
    short: str  # "Sharing with employees"
    text: str  # the hypothesis to check


@dataclass
class Contract:
    doc_id: str
    file_name: str
    spans: list[str]  # span text; the list index is the span id


@dataclass
class Answer:
    label: str  # one of LABELS, or "error" when the answer could not be read
    evidence: list[int] = field(default_factory=list)  # span ids


Answers = dict[str, Answer]  # by statement id
