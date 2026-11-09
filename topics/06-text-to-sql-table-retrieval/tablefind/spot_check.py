r"""Write spot-check.md: 20 main-set questions with the tables the key says they need, for the author to check.

    $env:PYTHONPATH = "../..;."
    python -m tablefind.spot_check
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

from tablefind.cards import card
from tablefind.data import load_key, load_questions, load_tables

TOPIC = Path(__file__).resolve().parent.parent
TARGET = {"1": 7, "2": 7, "3+": 6}


def _bucket(n: int) -> str:
    return str(n) if n < 3 else "3+"


def draw(key: dict[str, set[str]], seed: int = 2026) -> list[str]:
    rng = random.Random(seed)
    picked = []
    for b, n in TARGET.items():
        pool = sorted(q for q, g in key.items() if _bucket(len(g)) == b)
        picked += sorted(rng.sample(pool, min(n, len(pool))))
    return picked


def main() -> int:
    key = load_key("main")
    text = {q.qid: q.text for q in load_questions("main")}
    tables = {t.id: t for t in load_tables()}
    picked = draw(key)
    out = ["# Topic 06 spot check: 20 main-set questions and the tables they need", "",
           "**What to check:** for each question, would a SQL query that answers it need **these** tables (and no fewer)? "
           "The gold tables come from Snowflake's parse of the BIRD team's SQL. Mark **You** with ✓ or ✗, and add a note for every ✗.",
           "The key itself is not changed; disagreements go in the README's limitations.", "",
           "| # | Question | Needs | Gold tables | You | Note |", "|---|---|---|---|---|---|"]
    for i, q in enumerate(picked, 1):
        names = ", ".join(f"`{t}`" for t in sorted(key[q]))
        out.append(f"| {i} | [{q}](#{q}) | {len(key[q])} | {names} |  |  |")
    out.append("")
    for q in picked:
        out += ["---", "", f"## {q}", "", f"> {text[q]}", ""]
        for t in sorted(key[q]):
            out += ["```", card(tables[t], with_desc=True), "```", ""]
    (TOPIC / "spot-check.md").write_text("\n".join(out), encoding="utf-8")
    print(f"Wrote spot-check.md with {len(picked)} questions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
