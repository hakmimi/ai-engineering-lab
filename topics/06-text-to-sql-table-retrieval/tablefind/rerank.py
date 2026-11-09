"""The re-ranker: an LLM reads the top-20 table cards and picks the 7 a SQL query needs (the article's step)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from shared.llm import extract_xml

K = 7

SYSTEM = """You help a data analyst find tables in a large company data warehouse.

You get a question and a list of candidate tables (name and columns, sometimes with column descriptions).
Pick the 7 tables a SQL query that answers the question is most likely to need, including tables needed only
for joins. Use only tables from the list, written exactly as `database.table`.

Answer with one table per line, most needed first, inside tags:
<tables>
database.table
...
</tables>"""


@dataclass
class Picks:
    ids: list[str] = field(default_factory=list)
    made_up: list[str] = field(default_factory=list)
    status: str = "ok"  # "ok" | "error" (no <tables> tag)


def rerank_prompt(question: str, cards: list[str]) -> str:
    body = "\n\n".join(cards)
    return f"## Question\n\n{question}\n\n## Candidate tables ({len(cards)})\n\n{body}\n\nPick the {K} tables."


def _clean(line: str) -> str:
    line = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line)
    return line.replace('"', "").replace("`", "").replace("'", "").strip().lower()


def parse_picks(text: str, shown: list[str], k: int = K) -> Picks:
    if "<tables>" not in text:
        return Picks([], [], "error")
    shown_set = set(shown)
    dbs = {s.split(".", 1)[0] for s in shown}
    by_table: dict[str, list[str]] = {}
    for s in shown:
        by_table.setdefault(s.split(".", 1)[1], []).append(s)
    ids, made_up = [], []
    for raw in extract_xml(text, "tables").splitlines():
        name = _clean(raw)
        if not name:
            continue
        parts = name.split(".")
        full = ".".join(parts[-2:]) if len(parts) >= 2 else None
        if full in shown_set:
            hit = full
        elif (len(parts) == 1 or parts[-2] not in dbs) and len(by_table.get(parts[-1], [])) == 1:  # bare or schema prefix
            hit = by_table[parts[-1]][0]
        else:
            if name not in made_up:
                made_up.append(name)
            continue
        if hit not in ids:
            ids.append(hit)
    return Picks(ids[:k], made_up, "ok")


def fill(picks: list[str], ranked: list[str], k: int = K) -> tuple[list[str], int]:
    """Top up to k from the search order; returns (ids, how many were added)."""
    out = list(picks[:k])
    for r in ranked:
        if len(out) >= k:
            break
        if r not in out:
            out.append(r)
    return out, len(out) - min(len(picks), k)
