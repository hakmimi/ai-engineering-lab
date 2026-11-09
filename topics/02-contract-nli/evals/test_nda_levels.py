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


# ---------------------------------------------------------------- route + level 1
from ndaflow.levels import route, run_level1  # noqa: E402


def route_text(picks: dict[str, str]) -> str:
    return "\n".join(f"<{sid}>{ids}</{sid}>" for sid, ids in picks.items())


def test_route_reads_picks_and_drops_spans_the_contract_does_not_have(monkeypatch):
    picks = {sid: "none" for sid in STATEMENT_IDS}
    picks["nda-5"] = "1, 2, 3, 77"
    fake_llm(monkeypatch, {"route": route_text(picks)})
    out = route(SMALL_CONTRACT, ctx())
    assert out["nda-5"] == [1, 2]  # 3 is empty, 77 does not exist
    assert out["nda-1"] == []


def test_level1_router_gap_is_an_error_not_a_silent_not_mentioned(monkeypatch):
    picks = {sid: "none" for sid in STATEMENT_IDS[:-1]}
    fake_llm(monkeypatch, {"route": route_text(picks)})
    out = run_level1(SMALL_CONTRACT, ctx())
    assert out["nda-20"] == Answer("error", [])
    assert out["nda-1"] == Answer("not_mentioned", [])


def test_level1_nothing_picked_means_all_not_mentioned_and_no_decide_call(monkeypatch):
    calls = fake_llm(monkeypatch, {"route": route_text({sid: "none" for sid in STATEMENT_IDS})})
    out = run_level1(SMALL_CONTRACT, ctx())
    assert [c.label for c in calls] == ["route"]
    assert all(a == Answer("not_mentioned", []) for a in out.values())
    assert list(out) == STATEMENT_IDS


def test_level1_decide_sees_only_picked_spans(monkeypatch):
    picks = {sid: "none" for sid in STATEMENT_IDS}
    picks["nda-5"] = "1"
    calls = fake_llm(monkeypatch, {"route": route_text(picks), "decide": tags({"nda-5": "entailment|1, 2"})})
    out = run_level1(SMALL_CONTRACT, ctx())
    decide = calls[1]
    assert SMALL_CONTRACT.spans[1] in decide.prompt and SMALL_CONTRACT.spans[2] not in decide.prompt
    assert "nda-5" in decide.prompt and "nda-1 " not in decide.prompt
    assert out["nda-5"] == Answer("entailment", [1])  # 2 was not picked for nda-5
    assert out["nda-1"] == Answer("not_mentioned", [])


# ---------------------------------------------------------------- level 2
import random  # noqa: E402
import time  # noqa: E402

from ndaflow.levels import run_level2  # noqa: E402


def test_level2_makes_one_call_per_routed_statement(monkeypatch):
    picks = {sid: "none" for sid in STATEMENT_IDS}
    picks.update({"nda-5": "1", "nda-7": "2", "nda-8": "1, 2"})
    calls = fake_llm(monkeypatch, {"route": route_text(picks), "one:": "<label>entailment</label><evidence>1, 2</evidence>"})
    out = run_level2(SMALL_CONTRACT, ctx())
    one = sorted((c for c in calls if c.label.startswith("one:")), key=lambda c: c.label)
    assert [c.label for c in one] == ["one:nda-5", "one:nda-7", "one:nda-8"]
    nda5 = next(c for c in one if c.label == "one:nda-5")
    assert "nda-5" in nda5.prompt and "nda-7" not in nda5.prompt
    assert SMALL_CONTRACT.spans[1] in nda5.prompt and SMALL_CONTRACT.spans[2] not in nda5.prompt
    assert out["nda-5"] == Answer("entailment", [1])
    assert out["nda-8"] == Answer("entailment", [1, 2])
    assert out["nda-1"] == Answer("not_mentioned", [])


def test_level2_keeps_statement_order(monkeypatch):
    picks = {sid: "1" for sid in STATEMENT_IDS}
    picks["nda-20"] = None  # router gap

    def answer(label, prompt):
        time.sleep(random.random() / 200)  # finish in any order
        sid = label.split(":")[1]
        return f"<label>{'contradiction' if sid in ('nda-3', 'nda-17') else 'entailment'}</label><evidence>1</evidence>"

    text = route_text({sid: ids for sid, ids in picks.items() if ids})
    fake_llm(monkeypatch, {"route": text, "one:": answer})
    out = run_level2(SMALL_CONTRACT, ctx())
    assert list(out) == STATEMENT_IDS
    assert out["nda-3"].label == out["nda-17"].label == "contradiction"
    assert out["nda-5"].label == "entailment"
    assert out["nda-20"].label == "error"


def test_level2_unreadable_answer_is_an_error(monkeypatch):
    picks = {sid: "none" for sid in STATEMENT_IDS}
    picks["nda-5"] = "1"
    fake_llm(monkeypatch, {"route": route_text(picks), "one:": "I think it is fine."})
    assert run_level2(SMALL_CONTRACT, ctx())["nda-5"] == Answer("error", [])
