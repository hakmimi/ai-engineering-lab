import pytest

from shared.llm import Tracker
from tablefind import levels
from tablefind.data import Column, Question, Table
from tablefind.levels import Ctx, prepare, run_level

WORDS = ["project", "site", "plant", "scan", "staff"]


class FakeEmbedder:
    """Vector = word counts over WORDS, plus a tiny constant so no vector is all zeros."""

    cost_usd = 0.0

    def __init__(self):
        self.seen = []

    def embed(self, texts):
        self.seen.extend(texts)
        return [[t.lower().count(w) + 0.01 for w in WORDS] for t in texts]


def _tables(n_filler=20):
    ts = [Table("a.projects", "a", "Projects", (Column("project_name", "text", "TEXT. Project name."),)),
          Table("a.sites", "a", "sites", (Column("site_zone", "text", "TEXT. Zone of the site."),)),
          Table("b.plants", "b", "plants", (Column("plant_label", "text", "TEXT. Name of the solar plant."),))]
    ts += [Table(f"c.t{i:02d}", "c", f"t{i:02d}", (Column(f"col{i}", "text", "TEXT. Filler."),)) for i in range(n_filler)]
    return ts


@pytest.fixture
def ctx():
    c = Ctx(_tables(), FakeEmbedder(), "gpt-6-luna", Tracker())
    prepare(c)
    return c


def _fake_llm(answer, seen):
    def call(prompt, **kw):
        seen.append((prompt, kw))
        return answer
    return call


def test_level0_returns_7(ctx):
    out = run_level("0", Question("m-001", "Which project names?"), ctx)
    assert len(out["picks"]) == 7 and out["picks"][0] == "a.projects"
    assert out["status"] == "ok" and out["top20"] is None


def test_level1_uses_question_embedding(ctx):
    out = run_level("1", Question("m-001", "How many plants per plant type?"), ctx)
    assert out["picks"][0] == "b.plants" and len(out["picks"]) == 7
    assert "How many plants per plant type?" in ctx.embedder.seen


def test_level2_reranks_only_top20_plain_cards(ctx, monkeypatch):
    seen = []
    monkeypatch.setattr(levels, "llm_call", _fake_llm("<tables>\na.sites\na.projects\n</tables>", seen))
    out = run_level("2", Question("m-002", "Projects at each site"), ctx)
    prompt, kw = seen[0]
    assert prompt.count("Table: ") == 20 and " — " not in prompt
    assert kw["label"] == "l2:m-002" and kw["model"] == "gpt-6-luna"
    assert out["picks"][:2] == ["a.sites", "a.projects"] and len(out["picks"]) == 7
    assert out["filled"] == 5 and len(out["top20"]) == 20 and out["made_up"] == []


def test_level3_shows_descriptions(ctx, monkeypatch):
    seen = []
    monkeypatch.setattr(levels, "llm_call", _fake_llm("<tables>\nb.plants\n</tables>", seen))
    run_level("3", Question("m-003", "Solar plant names"), ctx)
    assert "plant_label text — Name of the solar plant." in seen[0][0]


def test_unreadable_answer_finds_nothing(ctx, monkeypatch):
    monkeypatch.setattr(levels, "llm_call", _fake_llm("projects, I guess", []))
    out = run_level("2", Question("m-004", "Projects"), ctx)
    assert out["picks"] == [] and out["status"] == "error"
