"""Load the built data. The run code reads questions and tables; only scoring reads the key."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
SETS = ("main", "test")


@dataclass(frozen=True)
class Column:
    name: str
    type: str
    desc: str = ""


@dataclass(frozen=True)
class Table:
    id: str  # db.table, lowercase table name
    db: str
    name: str  # as written in the schema
    columns: tuple[Column, ...]


@dataclass(frozen=True)
class Question:
    qid: str
    text: str


def _read(name: str):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def load_tables() -> list[Table]:
    return [Table(t["id"], t["db"], t["name"], tuple(Column(**c) for c in t["columns"])) for t in _read("tables.json")]


def load_questions(set_name: str) -> list[Question]:
    return [Question(q["qid"], q["text"]) for q in _read(f"{set_name}.json")]


def load_links() -> dict[str, set[str]]:
    """Foreign-key links between tables (level 4 only)."""
    return {t: set(ls) for t, ls in _read("links.json").items()}


def load_summaries() -> dict[str, str]:
    """Level 5: the LLM-written summary of every table (data/summaries.json). Every table must have one."""
    summaries = _read("summaries.json")
    missing = [t["id"] for t in _read("tables.json") if t["id"] not in summaries]
    if missing:
        raise ValueError(f"no summary for {len(missing)} tables, e.g. {', '.join(missing[:3])}; run tablefind.summarize")
    return summaries


def load_key(set_name: str) -> dict[str, set[str]]:
    return {qid: set(ts) for qid, ts in _read("key.json")[set_name].items()}
