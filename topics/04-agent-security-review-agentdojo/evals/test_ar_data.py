import json
from collections import Counter

import pytest
from ar_helpers import FAKE_RUN, run_without_injection_text, write_fake_runs

from agentreview.build_data import (
    MAIN_STYLES,
    REVIEWER_NOTE,
    TEST_STYLES,
    add_reviewer_note,
    build,
    draw,
    index_runs,
    split_halves,
)
from agentreview.data import DATA, SETS, load_key, load_pairs, load_sessions

FORBIDDEN = ("injections", "security", "utility", "attack_type", "injection_task", "user_task", "pipeline_name", "duration")


@pytest.fixture
def fake_runs(tmp_path):
    return write_fake_runs(tmp_path)


def test_index_skips_dos_variants_injection_task_runs_and_errors(fake_runs):
    refs = index_runs(fake_runs)
    assert {r.style for r in refs} == {"none", *MAIN_STYLES, *TEST_STYLES}
    assert all(r.user_task.startswith("user_task_") for r in refs)
    assert not any(r.injection_task == "injection_task_9" for r in refs)  # the run with an error
    assert Counter(r.kind for r in refs if r.style == "none") == {"clean": 12}


def test_split_halves_is_repeatable_and_rounds_up():
    a, b = split_halves(["u1", "u2", "u3", "u4", "u5"], 2026)
    assert (a, b) == split_halves(["u5", "u4", "u3", "u2", "u1"], 2026)
    assert len(a) == 3 and len(b) == 2 and not (a & b)


def test_draw_is_repeatable_and_spreads_over_suites(fake_runs):
    clean = [r for r in index_runs(fake_runs) if r.kind == "clean"]
    picked = draw(clean, 4, 2026)
    assert picked == draw(clean, 4, 2026)
    assert Counter(r.suite for r in picked) == {"banking": 2, "slack": 2}
    assert len(draw(clean, 99, 2026)) == len(clean)  # asks for more than exists: takes all


def test_main_and_test_never_share_a_user_task_or_an_attack_task(fake_runs):
    out = build(fake_runs, 2026, n=30)
    key = out["key"]["sessions"]
    for suite in ("banking", "slack"):
        main = [k for k in key.values() if k["set"] == "main" and k["suite"] == suite]
        test = [k for k in key.values() if k["set"] == "test" and k["suite"] == suite]
        assert main and test
        assert not {k["user_task"] for k in main} & {k["user_task"] for k in test}
        attacks = lambda ks: {k["injection_task"] for k in ks if k["injection_task"]}  # noqa: E731
        assert not attacks(main) & attacks(test)
    assert {k["style"] for k in key.values() if k["set"] == "main" and k["kind"] != "clean"} == set(MAIN_STYLES)
    assert {k["style"] for k in key.values() if k["set"] == "test" and k["kind"] != "clean"} <= set(TEST_STYLES)


def test_built_sets_hide_labels_and_pair_fooled_copies(fake_runs):
    out = build(fake_runs, 2026, n=30)
    for name in SETS:
        raw = json.dumps(out[name])
        for word in FORBIDDEN:
            assert f'"{word}' not in raw
    pairs = {sid: k["plain_sid"] for sid, k in out["key"]["sessions"].items() if k["set"] == "fooled"}
    test_bad = {sid for sid, k in out["key"]["sessions"].items() if k["set"] == "test" and k["kind"] == "bad"}
    assert set(pairs.values()) <= test_bad and len(pairs) == len(test_bad) - len(out["key"]["skipped"])
    for s in out["fooled"]["sessions"]:
        assert REVIEWER_NOTE in json.dumps(s)


def test_note_goes_after_the_last_line_even_when_blank_lines_differ():
    out = add_reviewer_note(FAKE_RUN, REVIEWER_NOTE)
    tool = out["messages"][3]["content"]
    assert tool.index("</INFORMATION>") < tool.index(REVIEWER_NOTE)
    assert REVIEWER_NOTE not in FAKE_RUN["messages"][3]["content"]  # the input is not changed


def test_two_injection_slots_with_the_same_text_get_one_note():
    run = json.loads(json.dumps(FAKE_RUN))
    run["injections"]["second_slot"] = run["injections"]["injection_bill_text"]
    tool = add_reviewer_note(run, REVIEWER_NOTE)["messages"][3]["content"]
    assert tool.count(REVIEWER_NOTE) == 1


def test_note_that_cannot_be_placed_returns_none():
    assert add_reviewer_note(run_without_injection_text(), REVIEWER_NOTE) is None


# ---------------------------------------------------------------- the committed sets


def test_committed_sets_hide_every_label_field():
    for name in SETS:
        raw = (DATA / f"{name}.json").read_text(encoding="utf-8")
        for word in FORBIDDEN:
            assert f'"{word}' not in raw


def test_committed_sets_have_the_planned_sizes_and_mixed_order():
    for name in ("main", "test"):
        kinds = [load_key(name)[s.sid] for s in load_sessions(name)]
        assert Counter(kinds) == {"bad": 30, "refused": 30, "clean": 30}
        assert kinds[:10] != sorted(kinds[:10])  # not grouped by kind
    skipped = json.loads((DATA / "key.json").read_text(encoding="utf-8"))["skipped"]
    assert len(load_sessions("fooled")) == 30 - len(skipped)
    assert set(load_pairs().values()) <= {sid for sid, kind in load_key("test").items() if kind == "bad"}


def test_say_only_attack_goals_are_left_out():
    # the article reviews actions; an attack whose goal is only to make the agent *say* something is out of scope
    from agentreview.build_data import SAY_ONLY

    assert ("travel", "injection_task_6") in SAY_ONLY
    key = json.loads((DATA / "key.json").read_text(encoding="utf-8"))["sessions"]
    assert not [sid for sid, k in key.items() if (k["suite"], k["injection_task"]) in SAY_ONLY]
