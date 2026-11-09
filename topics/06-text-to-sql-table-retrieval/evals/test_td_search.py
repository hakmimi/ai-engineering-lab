from tablefind.cards import card
from tablefind.data import Column, Table
from tablefind.search import BM25, tokens, top_k

T = Table("alpha_large.projects", "alpha_large", "Projects",
          (Column("arcregistry", "text", "TEXT. Project registration id."), Column("VesselTag", "text", "TEXT. Project name.")))


def test_tokens_split_camel_and_snake():
    assert tokens("ArtifactTag fund_flux") == ["artifact", "tag", "fund", "flux"]
    assert tokens("3d_score HTTPServer") == ["3", "d", "score", "http", "server"]


def test_card_with_and_without_desc():
    plain = card(T, with_desc=False)
    assert plain.splitlines() == ["Table: alpha_large.Projects", "- arcregistry text", "- VesselTag text"]
    rich = card(T, with_desc=True)
    assert "- VesselTag text — Project name." in rich.splitlines()


def test_bm25_prefers_matching_doc():
    docs = [tokens("solar plant output"), tokens("project vessel tag"), tokens("site zone geo")]
    s = BM25(docs).scores(tokens("which project names"))
    assert s.index(max(s)) == 1
    assert s[0] == 0.0


def test_top_k_stable_ties():
    assert top_k([1.0, 2.0, 2.0, 0.5], ["d", "c", "b", "a"], 2) == ["b", "c"]
    assert top_k([0.1, 0.2], ["x", "y"], 5) == ["y", "x"]
