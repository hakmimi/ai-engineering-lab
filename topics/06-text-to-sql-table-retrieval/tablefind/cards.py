"""A table card: what search indexes and what the re-ranker reads. Name and columns; optionally descriptions."""

from __future__ import annotations

import re

from tablefind.data import Table

_TYPE_PREFIX = re.compile(r"^[A-Z][A-Z0-9 _()]*(?: column)?\.\s+")  # "TEXT. ", "JSONB column. "


def _desc(text: str) -> str:
    return _TYPE_PREFIX.sub("", text).strip()


def card(t: Table, with_desc: bool) -> str:
    lines = [f"Table: {t.db}.{t.name}"]
    for c in t.columns:
        line = f"- {c.name} {c.type}"
        if with_desc and c.desc:
            line += f" — {_desc(c.desc)}"
        lines.append(line)
    return "\n".join(lines)
