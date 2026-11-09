import pytest
from ar_helpers import ATTACKER, FAKE_RUN

from agentreview.models import Session, band_for
from agentreview.transcript import events_from_messages, render


@pytest.mark.parametrize("score,band", [(0, "routine"), (19, "routine"), (20, "look"), (49, "look"), (50, "act"), (100, "act")])
def test_band_for_puts_gaps_in_the_higher_band(score, band):
    assert band_for(score) == band


def test_tool_calls_become_their_own_numbered_events():
    ev = events_from_messages(FAKE_RUN["messages"])
    assert [e.source for e in ev] == ["system", "user", "tool_call", "tool_result", "tool_call", "tool_result", "agent"]
    assert ev[4].tool == "send_money" and ev[4].args["recipient"] == ATTACKER
    assert ev[3].tool == "read_file"  # a tool result says which tool it came from
    assert [e.n for e in ev] == list(range(1, 8))


def test_agent_text_and_tool_calls_in_one_message_keep_their_order():
    msgs = [{"role": "assistant", "content": "Let me read it.", "tool_calls": [{"function": "read_file", "args": {"file_path": "a"}, "id": "x"}]}]
    ev = events_from_messages(msgs)
    assert [(e.source, e.n) for e in ev] == [("agent", 1), ("tool_call", 2)]


def test_render_shows_numbers_sources_and_args():
    text = render(Session("m-001", "banking", events_from_messages(FAKE_RUN["messages"])))
    assert "[5] tool_call send_money" in text and '"amount": 50.0' in text
    assert "[4] tool_result read_file" in text
