r"""Write data/search_next3.json: search ranks 21-23 for every question, for level 4c (the control for level 4).

Uses level 3's search (description cards) and only cached embeddings: it refuses to call the API.

    $env:PYTHONPATH = "../..;."
    python -m tablefind.next_search
"""

from __future__ import annotations

import json
import sys

from tablefind.cards import card
from tablefind.data import DATA, SETS, load_questions, load_tables
from tablefind.embed import Embedder, normalize
from tablefind.joins import next_after_shortlist
from tablefind.run import CACHE_DIR


def build(embedder: Embedder) -> dict[str, list[str]]:
    tables = load_tables()
    ids = [t.id for t in tables]
    vecs = [normalize(v) for v in embedder.embed([card(t, with_desc=True) for t in tables])]
    out = {}
    for s in SETS:
        qs = load_questions(s)
        for q, v in zip(qs, embedder.embed([q.text for q in qs])):
            out[q.qid] = next_after_shortlist(v, vecs, ids, normalized=True)
    return out


def main() -> int:
    out = build(Embedder(CACHE_DIR, cache_only=True))
    (DATA / "search_next3.json").write_text(json.dumps(out, indent=1, sort_keys=True), encoding="utf-8")
    print(f"Wrote search_next3.json for {len(out)} questions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
