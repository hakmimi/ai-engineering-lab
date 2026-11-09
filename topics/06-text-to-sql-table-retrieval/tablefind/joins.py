"""Level 4: hand over the LLM's 7 picks plus 3 tables joined to them by a foreign key (10 in all).

The control (4c) hands over the same 7 picks plus search ranks 21-23, also 10 and also from outside the 20 the
LLM saw, so any gain at level 4 comes from the join links, not from handing over more tables. (An earlier control
took the next 3 from inside the 20: tables the LLM had already turned down, which could never win.)
Both are computed from saved answers: no extra model calls.
"""

from __future__ import annotations

from tablefind.embed import cosine_top_k

JOIN_EXTRA = 3
SHORTLIST = 20


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


def add_search(picks: list[str], more: list[str], extra: int = JOIN_EXTRA) -> list[str]:
    """Picks, then the first `extra` tables of `more` that aren't already picked."""
    return list(picks) + [t for t in more if t not in set(picks)][:extra]


def next_after_shortlist(qvec: list[float], vecs: list[list[float]], ids: list[str], start: int = SHORTLIST,
                         extra: int = JOIN_EXTRA, normalized: bool = False) -> list[str]:
    """Search ranks start+1 .. start+extra (21-23): the closest tables the LLM was never shown."""
    return cosine_top_k(qvec, vecs, ids, start + extra, normalized=normalized)[start:]
