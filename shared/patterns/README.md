# shared/patterns: the agentic workflow patterns as building blocks

Five small, tested building blocks for the patterns in Anthropic's "Building effective agents" and Safe Software's
"AI Agentic Workflows" guide. None of them knows about a task, a prompt or a model: you pass in your own model calls
(usually `shared.llm.llm_call` with your prompt) and your own answer readers.

Topic 09 (`topics/09-agentic-patterns-bird/agentflow/levels.py`) uses all of them for text-to-SQL.

| Pattern | Use it when | Block | What you pass in |
|---|---|---|---|
| **Routing** | inputs fall into clear groups that need different handling | `route(call, read)` | one model call, and a reader that turns its answer into an option |
| **Handoff to a person** | a wrong route is costly and the router can say "not sure" | `route(..., allow_human=True, human=...)` | who answers when the router says `HUMAN` |
| **Parallelization** | the same task can be tried several times, or split into independent parts | `parallel(fns)`, `vote(items, key)` | the calls; a key that says which results agree (`None` = invalid) |
| **Orchestrator-worker** | you can't know in advance how many parts the task has | `orchestrate(plan, work, combine, original)` | a planner, a worker, a combiner |
| **Evaluator-optimizer** | there is a clear standard to check an answer against | `refine(write, grade, max_rounds)` | a writer that reads earlier feedback; a grader returning `(passed, feedback)` |
| **Free agent** | the steps can't be fixed in advance | `agent_loop(call, parse, tools, max_steps)` | one model call per step, a parser, tools that return text or `Final(value)` |

## What each block decides for you

- **route:** `HUMAN` is only accepted with `allow_human=True`; otherwise it reads as "no route". Returns `Route(choice, handoff, raw)`.
- **parallel:** one thread per call, results in the same order, the first error is raised.
- **vote:** the largest group of equal keys wins; ties go to the earliest; invalid items never win unless all are invalid.
- **orchestrate:** a plan of 0 or 1 parts means "no split": one worker gets the original task and its result is final, no combine call. Workers run at once.
- **refine:** stops on pass (`"pass"`), on an unreadable grade (`"grade_unreadable"`) or after `max_rounds` (`"cap"`); `grade=None` is a single write (`"one_shot"`).
- **agent_loop:** a missing or unknown tool is shown back to the agent and counts as a step; a tool can refuse to finish by returning text; after `max_steps` the run stops with `final=None` (`"cap"`). `last=True` is passed on the final step so your prompt can say so.

## A small example

```python
from shared.llm import llm_call, extract_xml
from shared.patterns import route, refine

team = route(lambda: llm_call(f"Which team handles this ticket? <team></team>\n{ticket}"),
             read=lambda t: extract_xml(t, "team").lower() or None)

reply = refine(
    write=lambda history: llm_call(draft_prompt(ticket, team.choice, history)),
    grade=lambda draft: read_grade(llm_call(grade_prompt(ticket, draft))),  # -> (passed, feedback)
    max_rounds=3,
)
print(reply.final, reply.stop, len(reply.rounds))
```

Tests: `tests/test_patterns.py` (offline, no model calls).
