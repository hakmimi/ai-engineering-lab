import json

from tablefind import data
from tablefind.build_data import build, parse_links
from tablefind.joins import add_joins, add_search
from td_helpers import ALPHA_SCHEMA, make_raw

LINKS = {"d.a": {"d.b", "d.c"}, "d.b": {"d.a", "d.x"}, "d.c": {"d.a", "d.x"}, "d.x": {"d.b", "d.c"}, "d.y": {"d.z"},
         "d.z": {"d.y"}}


def test_parse_links_reads_foreign_keys_both_ways_and_skips_self():
    text = ALPHA_SCHEMA + '\nCREATE TABLE "Loop" (\nid text NULL,\n    FOREIGN KEY (id) REFERENCES "Loop"(id)\n);\n'
    assert parse_links(text) == {"sites": {"projects"}, "projects": {"sites"}}


def test_build_writes_links_file(tmp_path, monkeypatch):
    out = tmp_path / "data"
    build(make_raw(tmp_path), out)
    links = json.loads((out / "links.json").read_text(encoding="utf-8"))
    assert links["alpha_large.sites"] == ["alpha_large.projects"]
    monkeypatch.setattr(data, "DATA", out)
    assert data.load_links()["alpha_large.projects"] == {"alpha_large.sites"}


def test_add_joins_prefers_tables_linked_to_more_picks():
    # x links to both picks b and c; nothing else is linked to two picks
    assert add_joins(["b", "c"], ["b", "c"], {"b": {"x", "a"}, "c": {"x"}, "a": set(), "x": set()}, extra=1) == ["b", "c", "x"]


def test_add_joins_breaks_ties_by_rank_of_the_pick_then_id():
    links = {"d.a": {"d.q", "d.p"}, "d.b": {"d.m"}}
    assert add_joins(["d.a", "d.b"], [], links, extra=3) == ["d.a", "d.b", "d.p", "d.q", "d.m"]


def test_add_joins_adds_at_most_extra_and_never_repeats():
    out = add_joins(["d.a"], [], LINKS, extra=3)
    assert out == ["d.a", "d.b", "d.c"]


def test_add_search_takes_next_from_shortlist():
    assert add_search(["b", "d"], ["a", "b", "c", "d", "e", "f"], extra=3) == ["b", "d", "a", "c", "e"]
