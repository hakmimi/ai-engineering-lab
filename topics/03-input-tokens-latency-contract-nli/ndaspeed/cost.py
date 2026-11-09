"""What each call cost, and the budget stop."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ndaspeed.timer import Timing
from shared.llm import PRICES


def cost_of(t: Timing, model: str) -> float:
    p = PRICES[model]
    uncached = t.input_tokens - t.cached_tokens
    return (uncached * p["input"] + t.cached_tokens * p["cache_read"] + t.output_tokens * p["output"]) / 1_000_000


class BudgetExceeded(Exception):
    pass


@dataclass
class Budget:
    limit_usd: float
    spent_usd: float = 0.0

    def before(self, estimate_usd: float) -> None:
        """Stop before a call that could pass the limit."""
        if self.spent_usd + estimate_usd > self.limit_usd:
            raise BudgetExceeded(f"next call (~${estimate_usd:.4f}) would pass the ${self.limit_usd:.2f} budget "
                                 f"(spent ${self.spent_usd:.4f})")

    def add(self, usd: float) -> None:
        self.spent_usd += usd


def spent_in_runs(runs_dir: Path) -> float:
    if not runs_dir.exists():
        return 0.0
    return sum(json.loads(p.read_text(encoding="utf-8")).get("spent_usd", 0.0) for p in runs_dir.glob("test*.json"))
