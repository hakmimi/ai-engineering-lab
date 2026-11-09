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
