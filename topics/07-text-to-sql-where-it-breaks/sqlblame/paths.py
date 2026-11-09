"""Where topic 07 keeps its files. Questions and databases come from topic 05 (sqlloop.data)."""

from pathlib import Path

TOPIC_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = TOPIC_DIR / "data"
RUNS_DIR = TOPIC_DIR / "runs"
