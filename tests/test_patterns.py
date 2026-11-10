"""shared.patterns: the five workflow patterns and a tool agent, with no task inside them."""

import threading
import time

import pytest

from shared.patterns import HUMAN, Final, agent_loop, orchestrate, parallel, refine, route, vote


# --- routing (+ handoff to a person) ---

def test_route_picks_a_known_option():
    r = route(lambda: "<pick>Billing</pick>", read=lambda t: "billing" if "Billing" in t else None)
    assert (r.choice, r.handoff, r.raw) == ("billing", False, "<pick>Billing</pick>")


def test_route_unreadable_is_none():
    assert route(lambda: "??", read=lambda t: None).choice is None


def test_route_handoff_only_when_allowed():
    read = lambda t: t
    assert route(lambda: HUMAN, read=read).choice is None
    r = route(lambda: HUMAN, read=read, allow_human=True)
    assert (r.choice, r.handoff) == (None, True)
    r = route(lambda: HUMAN, read=read, allow_human=True, human=lambda: "sales")
    assert (r.choice, r.handoff) == ("sales", True)


# --- parallelization ---

def test_parallel_keeps_order_and_overlaps():
    def slow(i):
        time.sleep(0.2)
        return i * 10
    start = time.perf_counter()
    assert parallel([lambda i=i: slow(i) for i in range(4)]) == [0, 10, 20, 30]
    assert time.perf_counter() - start < 0.6


def test_parallel_raises_the_first_error():
    def boom():
        raise ValueError("x")
    with pytest.raises(ValueError):
        parallel([lambda: 1, boom])


def test_parallel_empty():
    assert parallel([]) == []


def test_vote_majority_ties_and_invalid():
    key = lambda v: v  # None = invalid
    assert vote(["a", "b", "b"], key) == 1
    assert vote(["a", "b", "c"], key) == 0
    assert vote([None, "b", None], key) == 1
    assert vote([None, "a", "b"], key) == 1
    assert vote([None, None], key) == 0


# --- orchestrator-worker ---

def test_orchestrate_one_task_is_one_worker_on_the_original():
    seen = []
    out = orchestrate(plan=lambda: ["only"], work=lambda i, t: seen.append((i, t)) or f"r-{t}",
                      combine=lambda ts, rs: pytest.fail("no combine for one task"), original="Q")
    assert seen == [(0, "Q")] and out.final == "r-Q" and out.tasks == ["Q"]


def test_orchestrate_empty_plan_counts_as_one():
    out = orchestrate(plan=lambda: [], work=lambda i, t: t, combine=lambda ts, rs: None, original="Q")
    assert out.final == "Q" and out.tasks == ["Q"]


def test_orchestrate_many_tasks_then_combine():
    out = orchestrate(plan=lambda: ["a", "b", "c"], work=lambda i, t: f"{i}{t}",
                      combine=lambda ts, rs: "+".join(rs), original="Q")
    assert (out.final, out.tasks, out.results) == ("0a+1b+2c", ["a", "b", "c"], ["0a", "1b", "2c"])


def test_orchestrate_workers_run_at_once():
    lock, live, peak = threading.Lock(), [0], [0]

    def work(i, t):
        with lock:
            live[0] += 1
            peak[0] = max(peak[0], live[0])
        time.sleep(0.1)
        with lock:
            live[0] -= 1
        return t
    orchestrate(plan=lambda: ["a", "b", "c"], work=work, combine=lambda ts, rs: rs, original="Q")
    assert peak[0] == 3


# --- evaluator-optimizer ---

def test_refine_stops_on_pass_and_feeds_back():
    writes = []

    def write(history):
        writes.append(list(history))
        return f"v{len(history) + 1}"
    grades = iter([(False, "too long"), (True, "")])
    out = refine(write, lambda a: next(grades), max_rounds=3)
    assert out.final == "v2" and out.stop == "pass" and len(out.rounds) == 2
    assert writes == [[], [("v1", "too long")]]


def test_refine_cap_and_unreadable_grade():
    out = refine(lambda h: "x", lambda a: (False, "again"), max_rounds=3)
    assert (out.stop, len(out.rounds), out.final) == ("cap", 3, "x")
    out = refine(lambda h: "x", lambda a: (None, ""), max_rounds=3)
    assert (out.stop, len(out.rounds)) == ("grade_unreadable", 1)


def test_refine_without_a_grader_is_one_shot():
    out = refine(lambda h: "x", None, max_rounds=3)
    assert (out.stop, len(out.rounds)) == ("one_shot", 1)


# --- tool agent ---

def parse(text):
    name, _, arg = text.partition(":")
    return (name or None), {"arg": arg}


def test_agent_uses_tools_until_a_final_answer():
    replies = iter(["look:x", "answer:42"])
    histories = []

    def call(n, history, last):
        histories.append(list(history))
        return next(replies)
    tools = {"look": lambda a: f"saw {a['arg']}", "answer": lambda a: Final(a["arg"])}
    out = agent_loop(call, parse, tools, max_steps=5)
    assert (out.final, out.stop, out.steps) == ("42", "final", 2)
    assert histories == [[], [("look:x", "saw x")]]
    assert out.trace == [{"tool": "look", "arg": "x"}, {"tool": "answer", "arg": "42"}]


def test_agent_unknown_tool_is_an_observation():
    replies = iter(["dance:", "answer:1"])
    histories = []

    def call(n, history, last):
        histories.append(list(history))
        return next(replies)
    out = agent_loop(call, parse, {"answer": lambda a: Final(a["arg"])}, max_steps=5, bad_action="Use a tool.")
    assert histories[1] == [("(no tool call)", "Use a tool.")]
    assert out.trace[0] == {"tool": None, "raw": "dance:"} and out.final == "1"


def test_agent_tool_may_refuse_to_finish():
    replies = iter(["answer:", "answer:7"])
    tools = {"answer": lambda a: Final(a["arg"]) if a["arg"] else "Your answer was empty."}
    out = agent_loop(lambda n, h, last: next(replies), parse, tools, max_steps=5)
    assert (out.final, out.steps) == ("7", 2)


def test_agent_cap_and_last_step_flag():
    lasts = []

    def call(n, history, last):
        lasts.append(last)
        return "look:"
    out = agent_loop(call, parse, {"look": lambda a: "nothing"}, max_steps=3)
    assert (out.final, out.stop, out.steps) == (None, "cap", 3)
    assert lasts == [False, False, True]
