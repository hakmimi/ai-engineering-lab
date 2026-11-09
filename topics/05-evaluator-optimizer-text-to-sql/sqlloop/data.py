"""Load the drawn sets and find the databases."""

from __future__ import annotations

import json
from pathlib import Path

from sqlloop.models import Question

TOPIC_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = TOPIC_DIR / "data"
RAW_DIR = DATA_DIR / "raw"  # git-ignored: the BIRD Mini-Dev SQLite files
SETS = ("main", "test")


def load_set(name: str) -> list[Question]:
    rows = json.loads((DATA_DIR / f"{name}.json").read_text(encoding="utf-8"))
    return [Question(**r) for r in rows]


def db_path(db_id: str) -> Path:
    return RAW_DIR / "dev_databases" / db_id / f"{db_id}.sqlite"
