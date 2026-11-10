"""Prompt text new in topic 09, and reading the answers.

The SQL writer itself is topic 05's (sqlloop.prompts.render_generate with SCHEMA_INTRO + the schema text), so every
level writes SQL with the same words. What is new: the router, the one-prompt database line, the planner and combiner
of the orchestrator, and the free agent's tools. Written on the main set only.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from shared.llm import extract_xml
from sqlloop.prompts import read_sql

ROUTER_INTRO = """\
You route questions to the right database in a data warehouse. These are all its tables, as database.table with their
columns:

"""

ROUTER = """\
Which one database holds the data to answer this question with one SQLite query?

Hint from the person asking: {evidence}
Question: {question}

Think it through in <thoughts></thoughts>, then put only the database name in <database></database>.
"""

HANDOFF_LINE = """\
If you are not sure which database it is, put HUMAN in <database></database> instead, and a person will choose.
"""

WAREHOUSE_INTRO = """\
You work with a data warehouse of several SQLite databases. Each database's tables, with a few example rows each:

"""

DATABASE_LINE = "Also put the name of the one database the query runs on in <database></database>.\n"

PLAN = """\
You plan the work for SQL writers. Split the question below into the smallest set of sub-questions (at most 4) that
one simple SQLite query on this database can each answer, and that together give the answer. If one query can answer
it directly, give exactly one sub-question: the question itself.

Hint from the person asking: {evidence}
Question: {question}

Think it through in <thoughts></thoughts>, then put each sub-question in its own <subquestion></subquestion>.
"""

COMBINE = """\
Write one SQLite query that answers the question. Workers answered the sub-questions below; use their queries and
results as building blocks.

Hint from the person asking: {evidence}
Question: {question}

{parts}

Think it through in <thoughts></thoughts>, then put only the final query (one SELECT statement) in <sql></sql>.
Return exactly the columns the question asks for, nothing extra.
"""

PART = "<part>\n<subquestion>{sub}</subquestion>\n<sql>{sql}</sql>\n<result>{result}</result>\n</part>"

AGENT_INTRO = """\
You are a data analyst with a data warehouse of SQLite databases. You answer a question by writing one SQLite query.
The databases and their tables:

{db_list}

You work in steps. In each step, call exactly one tool:
<tool>describe</tool><database>name</database>
    shows the database's tables (CREATE TABLE text) with a few example rows
<tool>run_sql</tool><database>name</database><sql>query</sql>
    runs a read-only query and shows the first rows, or the error
<tool>answer</tool><database>name</database><sql>query</sql>
    gives your final query and ends the task
You have at most {max_steps} steps. The final query is one SELECT statement that returns exactly the columns the
question asks for, nothing extra.
"""

AGENT_STEP = """\
Hint from the person asking: {evidence}
Question: {question}
{history}
Step {n} of {max_steps}. {last}Think it through in <thoughts></thoughts>, then call one tool.
"""

AGENT_LAST = "This is your last step: call answer. "
STEP = "<step>\n{action}\n<observation>\n{observation}\n</observation>\n</step>"
BAD_ACTION = ("Could not read a tool call. Use <tool>describe</tool>, <tool>run_sql</tool> or <tool>answer</tool>, "
              "with <database></database> and, for run_sql and answer, <sql></sql>.")

TOOLS = ("describe", "run_sql", "answer")


def read_database(text: str, db_ids: Sequence[str], allow_human: bool = False) -> str | None:
    name = extract_xml(text, "database").strip().strip("`\"'").strip()
    if allow_human and name.upper() == "HUMAN":
        return "HUMAN"
    return {d.lower(): d for d in db_ids}.get(name.lower())


def read_subquestions(text: str, cap: int = 4) -> list[str]:
    found = [s.strip() for s in re.findall(r"<subquestion>(.*?)</subquestion>", text, re.DOTALL)]
    return [s for s in found if s][:cap]


def read_action(text: str) -> tuple[str | None, dict]:
    tool = extract_xml(text, "tool").strip().lower()
    if tool not in TOOLS:
        return None, {}
    sql = read_sql(text) if "<sql>" in text else ""
    return tool, {"database": extract_xml(text, "database").strip(), "sql": sql}


def render_action(tool: str, args: dict) -> str:
    out = f"<tool>{tool}</tool><database>{args.get('database', '')}</database>"
    return out + (f"<sql>{args['sql']}</sql>" if args.get("sql") else "")


def render_db_list(cards) -> str:
    by_db: dict[str, list[str]] = {}
    for c in cards:
        by_db.setdefault(c.db_id, []).append(c.table)
    return "\n".join(f"{db}: {', '.join(tables)}" for db, tables in by_db.items())
