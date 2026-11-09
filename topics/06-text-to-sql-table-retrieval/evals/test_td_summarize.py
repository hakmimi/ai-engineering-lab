import json

import pytest

from shared.llm import CallRecord
from tablefind.cards import summary_card
from tablefind.data import Column, Table
from tablefind.summarize import SUMMARY_PROMPT, summarize_all, summary_prompt

T1 = Table("a.projects", "a", "Projects", (Column("vesseltag", "text", "TEXT. Project name."),))
T2 = Table("a.sites", "a", "sites", (Column("zone", "text", "TEXT. Site zone."),))


def _fake(seen, cost_tokens=1000):
    def call(prompt, **kw):
        seen.append((prompt, kw))
        kw["tracker"].add(CallRecord(kw["label"], kw["model"], 0.1, cost_tokens, 100, 0, 0))
        return f"  Summary for {kw['label']}.  "
    return call


def test_prompt_is_pinterests_with_schema_and_no_sample_queries():
    p = summary_prompt(T1)
    assert "You are a data analyst that can help summarize SQL tables." in p
    assert "- vesseltag text — Project name." in p
    assert "===Sample Queries\n(none available)" in p
    assert "Do not use any adjective to describe the table." in SUMMARY_PROMPT


def test_summaries_are_cached_and_cost_counted_once(tmp_path):
    seen = []
    out, cost = summarize_all([T1, T2], "gpt-6-luna", tmp_path, budget=1.0, workers=1, llm=_fake(seen))
    assert out == {"a.projects": "Summary for sum:a.projects.", "a.sites": "Summary for sum:a.sites."}
    assert cost > 0 and len(seen) == 2
    again, cost2 = summarize_all([T1, T2], "gpt-6-luna", tmp_path, budget=1.0, workers=1, llm=_fake(seen))
    assert again == out and cost2 == 0 and len(seen) == 2


def test_budget_stops_new_calls(tmp_path):
    seen = []
    out, cost = summarize_all([T1, T2], "gpt-6-luna", tmp_path, budget=0.00001, workers=1, llm=_fake(seen))
    assert len(seen) == 1 and list(out) == ["a.projects"]


def test_failed_call_is_left_out_not_cached(tmp_path):
    def boom(prompt, **kw):
        raise RuntimeError("timeout")
    out, _ = summarize_all([T1], "gpt-6-luna", tmp_path, budget=1.0, workers=1, llm=boom)
    assert out == {}
    assert not any(tmp_path.iterdir()) or all(p.read_text(encoding="utf-8") == "" for p in tmp_path.iterdir())


def test_summary_card_has_name_and_summary_only():
    assert summary_card(T1, "Holds projects.") == "Table: a.Projects\nSummary: Holds projects."
