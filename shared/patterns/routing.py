"""Routing, with an optional handoff to a person.

A router is one model call whose answer names one of a fixed set of options (a database, a team, a tool...).
With `allow_human`, the router may answer HUMAN when it is unsure; `human()` then stands in for the person
(in an experiment, a function that knows the right option; in a product, a queue).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

HUMAN = "HUMAN"


@dataclass
class Route:
    choice: str | None  # None: unreadable, or handed off with no one to answer
    handoff: bool
    raw: str


def route(call: Callable[[], str], read: Callable[[str], str | None], *, allow_human: bool = False,
          human: Callable[[], str] | None = None) -> Route:
    """call() makes the router's model call; read(text) turns its answer into an option, HUMAN or None."""
    raw = call()
    choice = read(raw)
    if choice == HUMAN:
        if not allow_human:
            return Route(None, False, raw)
        return Route(human() if human else None, True, raw)
    return Route(choice, False, raw)
