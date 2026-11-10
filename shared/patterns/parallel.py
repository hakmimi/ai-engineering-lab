"""Parallelization: run independent calls at once, then (optionally) vote on the results."""

from __future__ import annotations

from collections.abc import Callable, Hashable
from concurrent.futures import ThreadPoolExecutor
from typing import TypeVar

T = TypeVar("T")


def parallel(fns: list[Callable[[], T]], max_workers: int | None = None) -> list[T]:
    """Run every function in its own thread; results in the same order. The first error is raised."""
    if not fns:
        return []
    with ThreadPoolExecutor(max_workers=max_workers or len(fns)) as pool:
        return list(pool.map(lambda f: f(), fns))


def vote(items: list[T], key: Callable[[T], Hashable | None]) -> int:
    """Index of the winner: the largest group with the same key; ties go to the earliest.
    A key of None marks an invalid item, which never wins unless every item is invalid (then the first)."""
    groups: dict[Hashable, list[int]] = {}
    for i, item in enumerate(items):
        k = key(item)
        if k is not None:
            groups.setdefault(k, []).append(i)
    if not groups:
        return 0
    return max(groups.values(), key=lambda idx: (len(idx), -idx[0]))[0]
