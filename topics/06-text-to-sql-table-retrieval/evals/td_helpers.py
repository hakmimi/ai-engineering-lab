"""Test helpers for topic 06: a tiny fake raw folder shaped like the real one. No network."""

from __future__ import annotations

import json
from pathlib import Path

ALPHA_SCHEMA = '''CREATE TABLE "Projects" (
arcregistry text NOT NULL,
"VesselTag" text NULL,
3d_score real NULL,
fund_flux character varying NULL,
    PRIMARY KEY (arcregistry)
);

First 3 rows:
arcregistry  VesselTag
PR1          Project Happy
...


CREATE TABLE sites (
zone_ref text NOT NULL,
geo jsonb NULL,
    FOREIGN KEY (zone_ref) REFERENCES "Projects"(arcregistry)
);

First 3 rows:
zone_ref geo
Z1       {}
'''

BETA_SCHEMA = '''CREATE TABLE plants (
plant_key bigint NOT NULL,
plant_label text NULL
);
'''

ALPHA_MEANINGS = {
    "alpha_large|projects|arcregistry": "TEXT. Project registration id.",
    "alpha_large|Projects|VesselTag": "TEXT. Project name.",
    "alpha_large|sites|geo": {"column_meaning": "JSONB column. Site position.", "fields_meaning": {"lat": "latitude"}},
}
BETA_MEANINGS = {"beta_large|plants|plant_label": "TEXT. Name of the solar plant."}

QUESTIONS = [  # (instance_id, db, text, gold tables as in the qrels)
    ("alpha_1", "alpha_large", "Which projects are at site Z1?", ["alpha_large__projects", "alpha_large__sites"]),
    ("alpha_2", "alpha_large", "List project names.", ["alpha_large__projects"]),
    ("beta_1", "beta_large", "How many plants are there?", ["beta_large__plants"]),
]


def make_raw(tmp: Path, questions=QUESTIONS) -> Path:
    raw = tmp / "raw"
    big = raw / "livesqlbench_large_v1"
    for db, schema, meanings in (("alpha_large", ALPHA_SCHEMA, ALPHA_MEANINGS), ("beta_large", BETA_SCHEMA, BETA_MEANINGS)):
        (big / db).mkdir(parents=True)
        (big / db / f"{db}_schema.txt").write_text(schema, encoding="utf-8")
        (big / db / f"{db}_column_meaning_base.json").write_text(json.dumps(meanings), encoding="utf-8")
    rows = [{"instance_id": i, "selected_database": db, "query": t, "sol_sql": "[]", "category": "Query"} for i, db, t, _ in questions]
    (big / "livesqlbench_large_v1_data.jsonl").write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    snow = raw / "livesqlbench_large_table"
    (snow / "qrels").mkdir(parents=True)
    (snow / "queries.jsonl").write_text("\n".join(json.dumps({"_id": i, "text": t}) for i, _, t, _ in questions), encoding="utf-8")
    lines = ["query-id\tcorpus-id\tscore"] + [f"{i}\t{g}\t1" for i, _, _, gold in questions for g in gold]
    (snow / "qrels" / "test.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return raw
