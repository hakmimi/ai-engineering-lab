"""The data shapes."""

from __future__ import annotations

from dataclasses import dataclass

DIFFICULTIES = ("simple", "moderate", "challenging")


@dataclass(frozen=True)
class Question:
    qid: int  # BIRD's question_id
    db_id: str
    question: str
    evidence: str  # BIRD's hint, shown to the model
    gold_sql: str  # never shown to the model
    difficulty: str  # never shown to the model
