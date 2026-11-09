import json

from shared.llm import Tracker
from tablefind import data, levels, run
from tablefind.data import Question
from tablefind.levels import Ctx, prepare, run_level
from test_td_levels import FakeEmbedder, _fake_llm, _tables


def _summaries(tables):
    s = {t.id: f"Filler table {t.name}." for t in tables}
    s["b.plants"] = "Solar plant names and labels; answers questions about each plant."
    s["a.projects"] = "Project registrations and project names."
    return s


def test_level5_searches_and_shows_summary_cards(monkeypatch):
    tables = _tables()
    ctx = Ctx(tables, FakeEmbedder(), "gpt-6-luna", Tracker())
    prepare(ctx, summaries=_summaries(tables))
    seen = []
    monkeypatch.setattr(levels, "llm_call", _fake_llm("<tables>\nb.plants\n</tables>", seen))
    out = run_level("5", Question("m-005", "Which solar plant names?"), ctx)
    prompt = seen[0][0]
    assert "Summary: Solar plant names and labels" in prompt and "plant_label text" not in prompt
    assert prompt.count("Table: ") == 20
    assert out["picks"][0] == "b.plants" and out["top20"][0] == "b.plants"
    assert seen[0][1]["label"] == "l5:m-005"


def test_load_summaries_requires_every_table(tmp_path, monkeypatch):
    monkeypatch.setattr(data, "DATA", tmp_path)
    (tmp_path / "tables.json").write_text(json.dumps([{"id": "a.x", "db": "a", "name": "x", "columns": []},
                                                      {"id": "a.y", "db": "a", "name": "y", "columns": []}]), encoding="utf-8")
    (tmp_path / "summaries.json").write_text(json.dumps({"a.x": "X."}), encoding="utf-8")
    try:
        data.load_summaries()
    except ValueError as e:
        assert "a.y" in str(e)
    else:
        raise AssertionError("missing summary not caught")


def test_level5_is_a_runner_choice():
    assert "5" in run.LEVELS
