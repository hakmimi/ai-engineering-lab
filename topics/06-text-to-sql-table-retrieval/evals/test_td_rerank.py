from tablefind.rerank import SYSTEM, Picks, fill, parse_picks, rerank_prompt

SHOWN = ["archeology_scan_large.projects", "archeology_scan_large.sites", "archeology_scan_large.scans",
         "solar_panel_large.plants"]


def test_prompt_has_question_and_every_card():
    p = rerank_prompt("Which sites?", ["Table: a.b\n- x text", "Table: c.d\n- y text"])
    assert "Which sites?" in p and "Table: a.b" in p and "Table: c.d" in p
    assert "<tables>" in SYSTEM and "7" in SYSTEM


def test_parse_matches_case_quotes_and_bare_names():
    text = '<tables>\n1. Archeology_Scan_Large."Projects"\n- `sites`\n</tables>'
    assert parse_picks(text, SHOWN) == Picks(["archeology_scan_large.projects", "archeology_scan_large.sites"], [], "ok")


def test_parse_dedupes_and_cuts_to_k():
    text = "<tables>\n" + "\n".join(["projects", "PROJECTS", "sites", "scans", "solar_panel_large.plants"]) + "\n</tables>"
    p = parse_picks(text, SHOWN, k=3)
    assert p.ids == ["archeology_scan_large.projects", "archeology_scan_large.sites", "archeology_scan_large.scans"]


def test_parse_flags_unshown_names_as_made_up():
    text = "<tables>\narcheology_scan_large.projects\narcheology_scan_large.personnel\nghost_table\n</tables>"
    p = parse_picks(text, SHOWN)
    assert p.ids == ["archeology_scan_large.projects"]
    assert p.made_up == ["archeology_scan_large.personnel", "ghost_table"]


def test_parse_without_tag_is_error():
    assert parse_picks("I think projects and sites.", SHOWN) == Picks([], [], "error")


def test_fill_tops_up_from_search_order():
    ids, filled = fill(["c"], ["a", "c", "b", "d"], k=3)
    assert ids == ["c", "a", "b"] and filled == 2
    assert fill(["a", "b"], ["a", "b"], k=2) == (["a", "b"], 0)


def test_wrong_database_prefix_is_made_up_but_schema_prefix_is_not():
    p = parse_picks("<tables>\nsolar_panel_large.sites\npublic.projects\n</tables>", SHOWN)
    assert p.ids == ["archeology_scan_large.projects"]
    assert p.made_up == ["solar_panel_large.sites"]


def test_cut_off_answer_without_closing_tag_is_error():
    p = parse_picks("<tables>\narcheology_scan_large.projects\narcheology_scan_large.si", SHOWN)
    assert p.status == "error" and p.ids == []


def test_last_tables_block_is_read():
    text = "Format: <tables>database.table</tables>\nAnswer:\n<tables>\nsites\n</tables>"
    assert parse_picks(text, SHOWN).ids == ["archeology_scan_large.sites"]


def test_notes_after_a_name_and_comma_lists_are_parsed():
    text = "<tables>\narcheology_scan_large.projects -- the main table\nsites, scans\n</tables>"
    p = parse_picks(text, SHOWN)
    assert p.ids == ["archeology_scan_large.projects", "archeology_scan_large.sites", "archeology_scan_large.scans"]
    assert p.made_up == []


def test_known_database_not_among_shown_is_made_up():
    p = parse_picks("<tables>\nfake_account_large.projects\n</tables>", SHOWN, dbs={"fake_account_large", "archeology_scan_large"})
    assert p.ids == [] and p.made_up == ["fake_account_large.projects"]
