"""Level 4: hand over the LLM's 7 picks plus 3 tables joined to them by a foreign key (10 in all).

The control (4c) hands over the same 7 picks plus the next 3 from the search order, also 10, so any gain
comes from the join links, not from handing over more tables. Both are computed from the saved level 3
answers: no extra model calls.
"""

from __future__ import annotations

JOIN_EXTRA = 3


def add_joins(picks: list[str], top20: list[str], links: dict[str, set[str]], extra: int = JOIN_EXTRA) -> list[str]:
    """Picks, then up to `extra` linked tables: linked to the most picks first, then to the best-ranked pick, then by id."""
    chosen = set(picks)
    best: dict[str, list] = {}
    for rank, p in enumerate(picks):
        for n in links.get(p, ()):
            if n in chosen:
                continue
            count, first = best.get(n, [0, rank])
            best[n] = [count + 1, min(first, rank)]
    order = sorted(best, key=lambda n: (-best[n][0], best[n][1], n))
    return list(picks) + order[:extra]


def add_search(picks: list[str], top20: list[str], extra: int = JOIN_EXTRA) -> list[str]:
    return list(picks) + [t for t in top20 if t not in set(picks)][:extra]
