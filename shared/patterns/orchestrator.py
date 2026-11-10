"""Orchestrator-worker: a planner splits the task, one worker per part (at once), a combiner joins them.

The number of workers is decided at run time by the plan. A plan of zero or one part means the task needs no
split: one worker takes the original task and its result is final (no combine call).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from shared.patterns.parallel import parallel


@dataclass
class Orchestration:
    final: Any
    tasks: list  # what the workers were given
    results: list  # one per task
    planned: list = field(default_factory=list)  # the plan as written


def orchestrate(plan: Callable[[], list], work: Callable[[int, Any], Any], combine: Callable[[list, list], Any],
                original: Any) -> Orchestration:
    """plan() -> parts; work(i, part) -> result; combine(parts, results) -> final."""
    planned = plan()
    if len(planned) <= 1:
        result = work(0, original)
        return Orchestration(result, [original], [result], planned)
    results = parallel([lambda i=i, t=t: work(i, t) for i, t in enumerate(planned)])
    return Orchestration(combine(planned, results), list(planned), results, planned)
