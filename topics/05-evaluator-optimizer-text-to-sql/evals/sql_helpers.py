"""A tiny SQLite database for offline tests."""

import sqlite3
from pathlib import Path


def make_db(path: Path) -> Path:
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE school (id INTEGER PRIMARY KEY, name TEXT, county TEXT, enrollment INTEGER, free_meals INTEGER, logo BLOB);
        INSERT INTO school VALUES (1, 'Oak High', 'Alameda', 1000, 250, X'0102');
        INSERT INTO school VALUES (2, 'Pine Middle', 'Alameda', 400, 300, NULL);
        INSERT INTO school VALUES (3, 'Elm Elementary', 'Fresno', 200, 20, NULL);
        INSERT INTO school VALUES (4, 'A school with a very long name that goes on and on and on for sure', 'Fresno', 50, 5, NULL);
        CREATE TABLE score (school_id INTEGER, year INTEGER, avg_math REAL);
        INSERT INTO score VALUES (1, 2020, 510.5), (2, 2020, 480.0);
        """
    )
    con.commit()
    con.close()
    return path
