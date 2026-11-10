"""Reusable building blocks for the agentic workflow patterns. No task, prompt or model inside: a topic passes
in its own model calls and readers, so the same blocks serve SQL, classification, review or anything else.

| Pattern             | Block                                  |
|---------------------|----------------------------------------|
| routing + handoff   | route(call, read, allow_human, human)  |
| parallelization     | parallel(fns), vote(items, key)        |
| orchestrator-worker | orchestrate(plan, work, combine, ...)  |
| evaluator-optimizer | refine(write, grade, max_rounds)       |
| free agent (tools)  | agent_loop(call, parse, tools, ...)    |

See shared/patterns/README.md for when to use which, and topics/09-agentic-patterns-bird for all of them at work.
"""

from shared.patterns.agent import AgentRun, Final, agent_loop
from shared.patterns.evaluator import Refinement, refine
from shared.patterns.orchestrator import Orchestration, orchestrate
from shared.patterns.parallel import parallel, vote
from shared.patterns.routing import HUMAN, Route, route

__all__ = ["HUMAN", "AgentRun", "Final", "Orchestration", "Refinement", "Route", "agent_loop", "orchestrate",
           "parallel", "refine", "route", "vote"]
