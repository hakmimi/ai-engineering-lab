import json
from pathlib import Path

import pytest

from tablefind import data
from tablefind.build_data import build, parse_meanings, parse_schema, split_dbs
from td_helpers import ALPHA_SCHEMA, QUESTIONS, make_raw

REPO = Path(__file__).resolve().parents[3]


def test_parse_schema_skips_sample_rows():
    tables = parse_schema(ALPHA_SCHEMA)
    assert list(tables) == ["Projects", "sites"]
    assert tables["Projects"] == [("arcregistry", "text"), ("VesselTag", "text"), ("3d_score", "real"),
                                  ("fund_flux", "character varying")]
    assert tables["sites"] == [("zone_ref", "text"), ("geo", "jsonb")]


def test_parse_meanings_handles_jsonb_dict():
    m = parse_meanings({"a|Projects|VesselTag": "TEXT. Project name.",
                        "a|sites|geo": {"column_meaning": "JSONB column. Site position.", "fields_meaning": {}}})
    assert m[("projects", "vesseltag")] == "TEXT. Project name."
    assert m[("sites", "geo")] == "JSONB column. Site position."


def test_split_dbs_is_seeded_and_disjoint():
    dbs = [f"db{i}" for i in range(18)]
    a, b = split_dbs(dbs)
    assert (a, b) == split_dbs(list(reversed(dbs)))
    assert len(a) == 9 and len(b) == 9 and not set(a) & set(b)


def test_build_ids_are_opaque_and_key_is_separate(tmp_path):
    out = tmp_path / "data"
    counts = build(make_raw(tmp_path), out)
    assert counts["tables"] == 3
    tables = json.loads((out / "tables.json").read_text(encoding="utf-8"))
    projects = next(t for t in tables if t["id"] == "alpha_large.projects")
    assert projects["name"] == "Projects"
    assert projects["columns"][1] == {"name": "VesselTag", "type": "text", "desc": "TEXT. Project name."}
    assert projects["columns"][2]["desc"] == ""
    qs = {s: json.loads((out / f"{s}.json").read_text(encoding="utf-8")) for s in ("main", "test")}
    for s, items in qs.items():
        for q in items:
            assert set(q) == {"qid", "text"} and q["qid"].startswith(s[0] + "-")
    assert sum(len(v) for v in qs.values()) == 3
    key = json.loads((out / "key.json").read_text(encoding="utf-8"))
    alpha_set = next(s for s in qs if any("site" in q["text"] for q in qs[s]))
    qid = next(q["qid"] for q in qs[alpha_set] if "site" in q["text"])
    assert sorted(key[alpha_set][qid]) == ["alpha_large.projects", "alpha_large.sites"]


def test_build_fails_when_a_gold_table_is_not_in_the_pool(tmp_path):
    bad = QUESTIONS + [("beta_2", "beta_large", "Ghost?", ["beta_large__ghosts"])]
    with pytest.raises(ValueError, match="beta_large.ghosts"):
        build(make_raw(tmp_path, bad), tmp_path / "data")


def test_loaders_read_built_files(tmp_path, monkeypatch):
    out = tmp_path / "data"
    build(make_raw(tmp_path), out)
    monkeypatch.setattr(data, "DATA", out)
    assert len(data.load_tables()) == 3
    assert data.load_tables()[0].columns[0].name
    total = len(data.load_questions("main")) + len(data.load_questions("test"))
    assert total == 3
    for s in ("main", "test"):
        assert set(data.load_key(s)) == {q.qid for q in data.load_questions(s)}


def test_key_and_raw_are_gitignored():
    ignore = (REPO / ".gitignore").read_text(encoding="utf-8").split()
    assert "topics/06-text-to-sql-table-retrieval/data/raw/" in ignore
    assert "topics/06-text-to-sql-table-retrieval/data/key.json" in ignore


def test_columns_named_like_keywords_are_kept_and_not_null_default_is_stripped():
    text = ('CREATE TABLE t (\ncheckpoint_location text NULL,\nunique_visitor_cnt bigint NOT NULL DEFAULT 0,\n'
            'checksum_sha256 text NOT NULL,\n    CHECK (unique_visitor_cnt >= 0),\n    UNIQUE (checksum_sha256),\n'
            '    CONSTRAINT pk PRIMARY KEY (checkpoint_location)\n);')
    assert parse_schema(text)["t"] == [("checkpoint_location", "text"), ("unique_visitor_cnt", "bigint"),
                                       ("checksum_sha256", "text")]
