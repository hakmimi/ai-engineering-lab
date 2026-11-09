"""Small statistics for timings: None values (no answer text, errors) are dropped first."""

from __future__ import annotations

import math
import random
import statistics


def values(xs) -> list[float]:
    return [x for x in xs if x is not None]


def median(xs) -> float | None:
    v = values(xs)
    return statistics.median(v) if v else None


def p90(xs) -> float | None:
    """Nearest rank. With 5-10 runs this is about the slowest run."""
    v = sorted(values(xs))
    return v[math.ceil(0.9 * len(v)) - 1] if v else None


def slope_per_100k(tokens: list[int], seconds: list[float]) -> float:
    """Least-squares slope, as extra seconds per 100K input tokens."""
    return statistics.linear_regression(tokens, seconds).slope * 100_000


def bootstrap_diff(a, b, rng: random.Random, n: int = 1000) -> tuple[float, float]:
    """95% interval for median(b) - median(a), resampling each side with replacement."""
    a, b = values(a), values(b)
    diffs = sorted(
        statistics.median(rng.choices(b, k=len(b))) - statistics.median(rng.choices(a, k=len(a))) for _ in range(n)
    )
    return diffs[int(0.025 * n)], diffs[int(0.975 * n) - 1]
