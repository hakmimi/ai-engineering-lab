"""Build the topic's data from the pinned raw downloads.

    python -m tablefind.build_data            # downloads into data/raw/ if missing, then builds
    python -m tablefind.build_data --no-fetch

Writes data/tables.json (the 971-table pool), data/main.json and data/test.json (questions with opaque ids),
data/build_log.json, and data/key.json (gold tables; git-ignored). Gold SQL is never fetched.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

TOPIC = Path(__file__).resolve().parent.parent
DATA = TOPIC / "data"
SEED = 2026
BIRD_REPO, BIRD_SHA = "birdsql/livesqlbench-large-v1", "a418e108d5cbb4cf9b783a928eff5e924ad2460d"
SNOW_REPO, SNOW_SHA = "Snowflake/SQL-Schema-Retrieval", "e60c65cf9aeab052f0747902d31db1807099fa23"

_CREATE = re.compile(r'CREATE TABLE\s+"?([^\s"(]+)"?\s*\((.*?)\n\);', re.S)
_COLUMN = re.compile(r'^\s*("[^"]+"|\S+)\s+(.+?)(?:\s+(?:NOT\s+)?NULL\b.*|\s+DEFAULT\b.*)?,?\s*$')
# Table constraints, not columns. Keyword + "(" for CHECK/UNIQUE so columns like checkpoint_location survive.
_NOT_COLUMN = re.compile(r"^(?:PRIMARY\s+KEY|FOREIGN\s+KEY|CONSTRAINT\b|UNIQUE\s*\(|CHECK\s*\()", re.I)


def parse_schema(text: str) -> dict[str, list[tuple[str, str]]]:
    """Table name as written -> [(column, type)], from the CREATE TABLE blocks only (sample rows are skipped)."""
    tables: dict[str, list[tuple[str, str]]] = {}
    for name, body in _CREATE.findall(text):
        cols = []
        for line in body.splitlines():
            s = line.strip()
            if not s or _NOT_COLUMN.match(s):
                continue
            m = _COLUMN.match(s)
            if m:
                cols.append((m.group(1).strip('"'), m.group(2).rstrip(",").strip()))
        tables[name] = cols
    return tables


def parse_meanings(d: dict) -> dict[tuple[str, str], str]:
    """(table lower, column lower) -> description. JSONB columns keep only their column_meaning."""
    out = {}
    for k, v in d.items():
        _, table, column = k.split("|", 2)
        if isinstance(v, dict):
            v = v.get("column_meaning", "")
        out[(table.lower(), column.lower())] = str(v).strip()
    return out


def split_dbs(dbs: list[str], seed: int = SEED) -> tuple[list[str], list[str]]:
    order = sorted(dbs)
    random.Random(seed).shuffle(order)
    half = len(order) // 2
    return sorted(order[:half]), sorted(order[half:])


def _table_id(db: str, name: str) -> str:
    return f"{db}.{name.lower()}"


def build(raw: Path, out: Path) -> dict:
    big = raw / "livesqlbench_large_v1"
    pool, tables = set(), []
    db_dirs = sorted(p for p in big.iterdir() if p.is_dir())
    for d in db_dirs:
        db = d.name
        schema = parse_schema((d / f"{db}_schema.txt").read_text(encoding="utf-8"))
        meanings = parse_meanings(json.loads((d / f"{db}_column_meaning_base.json").read_text(encoding="utf-8")))
        for name, cols in schema.items():
            tid = _table_id(db, name)
            pool.add(tid)
            tables.append({"id": tid, "db": db, "name": name, "columns": [
                {"name": c, "type": t, "desc": meanings.get((name.lower(), c.lower()), "")} for c, t in cols]})

    db_of = {}
    for line in (big / "livesqlbench_large_v1_data.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            db_of[r["instance_id"]] = r["selected_database"]
    snow = raw / "livesqlbench_large_table"
    texts = {}
    for line in (snow / "queries.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            q = json.loads(line)
            texts[q["_id"]] = q["text"]
    gold: dict[str, set[str]] = defaultdict(set)
    for line in (snow / "qrels" / "test.tsv").read_text(encoding="utf-8").splitlines():
        p = line.split("\t")
        if len(p) == 3 and p[2].strip().isdigit() and int(p[2]) > 0:
            db, table = p[1].split("__", 1)
            gold[p[0]].add(_table_id(db, table))
    missing = sorted(t for g in gold.values() for t in g if t not in pool)
    if missing:
        raise ValueError(f"gold tables not in the pool: {', '.join(missing)}")

    group_a, group_b = split_dbs([d.name for d in db_dirs])
    sets: dict[str, list] = {"main": [], "test": []}
    key: dict[str, dict] = {"main": {}, "test": {}}
    sources: dict[str, str] = {}
    for src in sorted(gold):
        set_name = "main" if db_of[src] in group_a else "test"
        qid = f"{set_name[0]}-{len(sets[set_name]) + 1:03d}"
        sets[set_name].append({"qid": qid, "text": texts[src]})
        key[set_name][qid] = sorted(gold[src])
        sources[qid] = src

    out.mkdir(parents=True, exist_ok=True)

    def write(name: str, obj) -> None:
        (out / name).write_text(json.dumps(obj, indent=1, ensure_ascii=False), encoding="utf-8")

    write("tables.json", tables)
    write("main.json", sets["main"])
    write("test.json", sets["test"])
    write("key.json", key)
    counts = {"tables": len(tables), "main": len(sets["main"]), "test": len(sets["test"])}
    write("build_log.json", {"seed": SEED, "group_a_main": group_a, "group_b_test": group_b, "counts": counts,
                             "pins": {BIRD_REPO: BIRD_SHA, SNOW_REPO: SNOW_SHA}, "sources": sources})
    return counts


def fetch(raw: Path) -> None:
    """Download the pinned files that are missing. Gold SQL is not part of either release."""
    def get(repo: str, sha: str, path: str, dest: Path) -> None:
        if dest.exists():
            return
        dest.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(f"https://huggingface.co/datasets/{repo}/resolve/{sha}/{path}", dest)

    for f in ("queries.jsonl", "qrels/test.tsv"):
        get(SNOW_REPO, SNOW_SHA, f"livesqlbench_large_table/{f}", raw / "livesqlbench_large_table" / f)
    with urllib.request.urlopen(f"https://huggingface.co/api/datasets/{BIRD_REPO}/revision/{BIRD_SHA}") as r:
        files = [s["rfilename"] for s in json.load(r)["siblings"]]
    for f in files:
        if f.endswith(("_schema.txt", "_column_meaning_base.json")) or f == "livesqlbench_large_v1_data.jsonl":
            get(BIRD_REPO, BIRD_SHA, f, raw / "livesqlbench_large_v1" / f)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--no-fetch", action="store_true")
    a = p.parse_args(argv)
    raw = DATA / "raw"
    if not a.no_fetch:
        fetch(raw)
    print(build(raw, DATA))
    return 0


if __name__ == "__main__":
    sys.exit(main())
