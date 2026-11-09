import pytest
from nda_helpers import SMALL_CONTRACT, ctx, fake_llm, tags

from ndaflow.levels import normalize_label, parse_span_ids, run_level0
from ndaflow.models import STATEMENT_IDS, Answer
from ndaflow.prompts import render_contract


# ---------------------------------------------------------------- parsing
@pytest.mark.parametrize("raw", ["NotMentioned", "Not mentioned", "not-mentioned", " not_mentioned ", "NOT MENTIONED"])
def test_normalize_label_reads_spelling_variants(raw):
    assert normalize_label(raw) == "not_mentioned"


def test_normalize_label_rejects_other_words():
    assert normalize_label("ENTAILMENT") == "entailment"
    assert normalize_label("maybe") is None


def test_parse_span_ids_drops_made_up_numbers():
    assert parse_span_ids("[3], 7, 7, 99", valid={3, 7, 8}) == [3, 7]
    assert parse_span_ids("none", valid={1}) == []
    assert parse_span_ids("", valid={1}) == []


def test_render_contract_numbers_spans_and_skips_empty_ones():
    text = render_contract(SMALL_CONTRACT)
    assert text.splitlines()[1] == "[1] " + SMALL_CONTRACT.spans[1]
    assert "[3]" not in text  # empty span
    assert render_contract(SMALL_CONTRACT, [2]).splitlines() == ["[2] " + SMALL_CONTRACT.spans[2]]


# ---------------------------------------------------------------- level 0
def test_level0_reads_17_answers_and_a_missing_tag_is_an_error(monkeypatch):
    answers = {sid: "entailment|1" for sid in STATEMENT_IDS[:-1]}
    answers["nda-1"] = "Not mentioned|1"  # evidence is dropped for not_mentioned
    calls = fake_llm(monkeypatch, {"level0": tags(answers)})
    out = run_level0(SMALL_CONTRACT, ctx())
    assert len(calls) == 1
    assert list(out) == STATEMENT_IDS
    assert out["nda-2"] == Answer("entailment", [1])
    assert out["nda-1"] == Answer("not_mentioned", [])
    assert out[STATEMENT_IDS[-1]].label == "error"


def test_level0_unreadable_label_is_an_error(monkeypatch):
    fake_llm(monkeypatch, {"level0": tags({"nda-1": "probably|1"})})
    assert run_level0(SMALL_CONTRACT, ctx())["nda-1"] == Answer("error", [])


def test_level0_evidence_outside_the_contract_is_dropped(monkeypatch):
    fake_llm(monkeypatch, {"level0": tags({"nda-1": "entailment|1, 3, 40"})})
    assert run_level0(SMALL_CONTRACT, ctx())["nda-1"] == Answer("entailment", [1])  # 3 is empty, 40 does not exist


def test_level0_prompt_shows_numbered_spans_and_caches_the_statements(monkeypatch):
    calls = fake_llm(monkeypatch, {"level0": ""})
    run_level0(SMALL_CONTRACT, ctx())
    assert "[1] " + SMALL_CONTRACT.spans[1] in calls[0].prompt
    assert "nda-20" in calls[0].kwargs["cached_system"]
