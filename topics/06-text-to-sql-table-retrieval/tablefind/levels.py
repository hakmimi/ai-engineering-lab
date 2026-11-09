"""The four levels. Every level searches the whole pool and hands 7 tables to the (imagined) query writer.

0 keyword search · 1 embedding search · 2 embedding top 20 → LLM picks 7 · 3 same as 2 with column descriptions
"""

from __future__ import annotations

from dataclasses import dataclass, field

from shared.llm import Tracker, llm_call
from tablefind.cards import card
from tablefind.data import Question, Table
from tablefind.embed import cosine_top_k, normalize
from tablefind.rerank import K, SYSTEM, fill, parse_picks, rerank_prompt
from tablefind.search import BM25, tokens, top_k

SHORTLIST = 20
RERANK_MAX_TOKENS = 2000  # OpenAI counts reasoning tokens in this limit


@dataclass
class Ctx:
    tables: list[Table]
    embedder: object  # .embed(texts) -> vectors, .cost_usd
    model: str
    tracker: Tracker
    index: dict = field(default_factory=dict)


def prepare(ctx: Ctx, embed: bool = True) -> None:
    """Build the search indexes once: BM25 on plain cards, and (embed=True) embeddings of plain and description cards."""
    ids = [t.id for t in ctx.tables]
    plain = [card(t, with_desc=False) for t in ctx.tables]
    rich = [card(t, with_desc=True) for t in ctx.tables]
    ctx.index = {
        "ids": ids,
        "cards": {False: dict(zip(ids, plain)), True: dict(zip(ids, rich))},
        "bm25": BM25([tokens(c) for c in plain]),
        "dbs": {t.db for t in ctx.tables},
    }
    if embed:
        ctx.index["vecs"] = {False: [normalize(v) for v in ctx.embedder.embed(plain)],
                             True: [normalize(v) for v in ctx.embedder.embed(rich)]}


def _answer(picks: list[str], top20=None, made_up=None, filled=0, status="ok") -> dict:
    return {"picks": picks, "top20": top20, "made_up": made_up or [], "filled": filled, "status": status}


def run_level(level: str, q: Question, ctx: Ctx) -> dict:
    ix = ctx.index
    if level == "0":
        return _answer(top_k(ix["bm25"].scores(tokens(q.text)), ix["ids"], K))
    qvec = ctx.embedder.embed([q.text])[0]
    if level == "1":
        return _answer(cosine_top_k(qvec, ix["vecs"][False], ix["ids"], K, normalized=True))
    with_desc = level == "3"
    top20 = cosine_top_k(qvec, ix["vecs"][with_desc], ix["ids"], SHORTLIST, normalized=True)
    cards = [ix["cards"][with_desc][i] for i in top20]
    text = llm_call(rerank_prompt(q.text, cards), cached_system=SYSTEM, label=f"l{level}:{q.qid}",
                    model=ctx.model, tracker=ctx.tracker, max_tokens=RERANK_MAX_TOKENS)
    p = parse_picks(text, top20, dbs=ix["dbs"])
    if p.status != "ok":
        return _answer([], top20, p.made_up, 0, p.status)
    picks, filled = fill(p.ids, top20)
    return _answer(picks, top20, p.made_up, filled)
