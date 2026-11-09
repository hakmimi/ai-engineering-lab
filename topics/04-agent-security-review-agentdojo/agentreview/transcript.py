"""Turn an AgentDojo chat into numbered events, and show a session as text for the reviewer."""

from __future__ import annotations

import json

from agentreview.models import Event, Session

_ROLE_TO_SOURCE = {"system": "system", "user": "user", "assistant": "agent", "tool": "tool_result"}


def events_from_messages(messages: list[dict]) -> list[Event]:
    """One event per message; each tool call of an agent message becomes its own event after the agent's text."""
    events: list[Event] = []

    def add(source: str, text: str, tool: str = "", args: dict | None = None) -> None:
        events.append(Event(len(events) + 1, source, text, tool, args or {}))

    for m in messages:
        role = m.get("role", "")
        text = m.get("content") or ""
        if role == "assistant":
            if text:
                add("agent", text)
            for call in m.get("tool_calls") or []:
                add("tool_call", "", call.get("function", ""), dict(call.get("args") or {}))
        elif role == "tool":
            # AgentDojo shows the agent `error or content`: a failed call's message lives in "error"
            add("tool_result", m.get("error") or text, (m.get("tool_call") or {}).get("function", ""))
        else:
            add(_ROLE_TO_SOURCE.get(role, role), text)
    return events


def event_body(e: Event) -> str:
    """The text a reviewer sees for one event (tool calls show their args as JSON)."""
    if e.source == "tool_call":
        return json.dumps(e.args, ensure_ascii=False)
    return e.text


def render(session: Session) -> str:
    blocks = []
    for e in session.events:
        header = f"[{e.n}] {e.source}" + (f" {e.tool}" if e.tool else "")
        blocks.append(f"{header}\n{event_body(e)}")
    return "\n\n".join(blocks)
