"""A free agent: the model picks a tool each step, sees what it returned, and decides when it is done.

    call(n, history, last) -> text      one model call; history is [(action, observation), ...]; last = final step
    parse(text) -> (tool name | None, args)
    tools[name](args) -> observation text, or Final(value) to end

A missing or unknown tool is not an error: the agent is told so (bad_action) and the step counts.
A tool can refuse to finish (for example an answer with no content) by returning an observation instead of Final.
After max_steps without a Final, the agent stops with no answer ("cap").
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

NO_TOOL = "(no tool call)"


@dataclass
class Final:
    value: Any


@dataclass
class AgentRun:
    final: Any  # None when the agent never finished
    stop: str  # final | cap
    steps: int
    trace: list[dict] = field(default_factory=list)


def agent_loop(call: Callable[[int, list, bool], str], parse: Callable[[str], tuple[str | None, dict]],
               tools: dict[str, Callable[[dict], Any]], max_steps: int,
               render: Callable[[str, dict, str], str] | None = None,
               bad_action: str = "Could not read a tool call.") -> AgentRun:
    """render(tool, args, text) is how an action is shown back in the history (default: the model's text)."""
    history: list[tuple[str, str]] = []
    trace: list[dict] = []
    for n in range(1, max_steps + 1):
        text = call(n, list(history), n == max_steps)
        name, args = parse(text)
        if name not in tools:
            trace.append({"tool": None, "raw": text[-500:]})
            history.append((NO_TOOL, bad_action))
            continue
        trace.append({"tool": name, **args})
        out = tools[name](args)
        if isinstance(out, Final):
            return AgentRun(out.value, "final", n, trace)
        history.append((render(name, args, text) if render else text, out))
    return AgentRun(None, "cap", max_steps, trace)
