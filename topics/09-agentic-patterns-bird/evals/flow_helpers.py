"""Two tiny SQLite databases for offline tests: a 'shop' and a 'zoo' (no table name repeats)."""

import sqlite3
from pathlib import Path


def make_dbs(tmp: Path) -> dict[str, Path]:
    scripts = {
        "shop": """
            CREATE TABLE Customer (id INTEGER PRIMARY KEY, name TEXT);
            INSERT INTO Customer VALUES (1, 'Ann'), (2, 'Bob');
            CREATE TABLE orders (oid INTEGER PRIMARY KEY, cid INTEGER, total REAL);
            INSERT INTO orders VALUES (10, 1, 9.5), (11, 1, 3.0);
        """,
        "zoo": """
            CREATE TABLE animal (id INTEGER PRIMARY KEY, kind TEXT, keeper_id INTEGER);
            INSERT INTO animal VALUES (1, 'lion', 1);
            CREATE TABLE keeper (id INTEGER PRIMARY KEY, name TEXT);
            INSERT INTO keeper VALUES (1, 'Kim');
        """,
    }
    paths = {}
    for name, script in scripts.items():
        p = tmp / f"{name}.sqlite"
        con = sqlite3.connect(p)
        con.executescript(script)
        con.commit()
        con.close()
        paths[name] = p
    return paths


class FakeLLM:
    """Answers by call label: `replies[label]` is a string, a list (one per call, in order) or a function of the prompt.
    Records every call as (label, prompt, cached_system)."""

    def __init__(self, replies: dict):
        import threading

        self.replies = {k: (list(v) if isinstance(v, list) else v) for k, v in replies.items()}
        self.calls: list[tuple[str, str, str]] = []
        self._lock = threading.Lock()

    def __call__(self, prompt, *, cached_system="", system="", model=None, label="", tracker=None, **kw):
        with self._lock:
            self.calls.append((label, prompt, cached_system))
            key = label if label in self.replies else label.rsplit("-", 1)[0]
            r = self.replies[key]
            if isinstance(r, list):
                r = r.pop(0)
        if isinstance(r, Exception):
            raise r
        return r(prompt) if callable(r) else r

    def labels(self) -> list[str]:
        return [c[0] for c in self.calls]
