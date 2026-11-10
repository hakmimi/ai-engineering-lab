"""Evaluator-optimizer: a writer makes an answer, a grader passes it or sends feedback, up to max_rounds.

write(history) gets the earlier (answer, feedback) pairs. grade(answer) returns (passed, feedback) or
(passed, feedback, info): passed is True, False, or None when the grade could not be read (the loop stops).
Without a grader it is a single write ("one_shot").
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class Refinement:
    final: Any
    rounds: list[dict]  # {"answer", "passed", "feedback", **info}
    stop: str  # pass | cap | grade_unreadable | one_shot


def refine(write: Callable[[list[tuple[Any, str]]], Any], grade: Callable[[Any], tuple] | None,
           max_rounds: int = 3) -> Refinement:
    history: list[tuple[Any, str]] = []
    rounds: list[dict] = []
    for _ in range(1 if grade is None else max_rounds):
        answer = write(list(history))
        if grade is None:
            rounds.append({"answer": answer, "passed": None, "feedback": ""})
            return Refinement(answer, rounds, "one_shot")
        passed, feedback, *rest = grade(answer)
        rounds.append({"answer": answer, "passed": passed, "feedback": feedback, **(rest[0] if rest else {})})
        if passed:
            return Refinement(answer, rounds, "pass")
        if passed is None:
            return Refinement(answer, rounds, "grade_unreadable")
        history.append((answer, feedback))
    return Refinement(rounds[-1]["answer"], rounds, "cap")
