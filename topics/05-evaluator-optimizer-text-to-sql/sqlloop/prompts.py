"""All prompt text, and reading the answers.

Tags follow the cookbook page: the generator answers in <thoughts> and <response> (here <sql>),
the grader in <evaluation> (PASS / NEEDS_IMPROVEMENT / FAIL) and <feedback>.
The page grades code for correctness, complexity and style; for SQL only correctness matters.
"""

from __future__ import annotations

import html
import re

from shared.llm import extract_xml

VERDICTS = ("PASS", "NEEDS_IMPROVEMENT", "FAIL")

SCHEMA_INTRO = "You work with this SQLite database. Its tables, with a few example rows each:\n\n"

GENERATE = """\
Write one SQLite query that answers the question.

Hint from the person asking: {evidence}
Question: {question}
{history}
Think it through in <thoughts></thoughts>, then put only the final query (one SELECT statement) in <sql></sql>.
Return exactly the columns the question asks for, nothing extra.
"""

HISTORY = """
Your earlier attempts and the feedback on each. Use the feedback to write a better query:
{attempts}
"""

ATTEMPT = "<attempt>\n<sql>{sql}</sql>\n<feedback>{feedback}</feedback>\n</attempt>"

GRADE = """\
Evaluate this SQLite query written for the question below. Check that it answers exactly what is asked:
the right tables and joins, the right filters and values, the right columns and calculations, and the
hint used correctly. It must be valid SQLite. You should be evaluating only, not writing the query yourself.

Hint from the person asking: {evidence}
Question: {question}

<sql>{sql}</sql>
{result}
Output PASS only if the query is correct and needs no change. Otherwise output NEEDS_IMPROVEMENT or FAIL
and explain what to change.

<evaluation>PASS, NEEDS_IMPROVEMENT or FAIL</evaluation>
<feedback>What is wrong and how to fix it</feedback>
"""

RESULT_ROWS = "\nWhen run on the database, it returned {n} rows. {shown}\n{table}\n"
RESULT_ERROR = "\nWhen run on the database, it failed with this error: {error}\n"

FEEDBACK_ERROR = "Running it on the database gave this error: {error}"
FEEDBACK_EMPTY = "Running it on the database returned no rows. Check the filters and the exact values against the example rows."


def render_generate(question: str, evidence: str, attempts: list[tuple[str, str]]) -> str:
    history = ""
    if attempts:
        history = HISTORY.format(attempts="\n".join(ATTEMPT.format(sql=s, feedback=f) for s, f in attempts))
    return GENERATE.format(question=question, evidence=evidence or "(none)", history=history)


def _cell(v, max_cell: int = 60) -> str:
    t = "NULL" if v is None else str(v)
    return t if len(t) <= max_cell else t[:max_cell] + "..."


def render_result(rows, n_rows: int, error: str, show: int = 10) -> str:
    if error:
        return RESULT_ERROR.format(error=error)
    shown = f"The first {min(show, n_rows)}:" if n_rows else ""
    table = "\n".join(" | ".join(_cell(v) for v in r) for r in (rows or [])[:show])
    return RESULT_ROWS.format(n=n_rows, shown=shown, table=table)


def render_grade(question: str, evidence: str, sql: str, result: str = "") -> str:
    return GRADE.format(question=question, evidence=evidence or "(none)", sql=sql, result=result)


def read_sql(text: str) -> str:
    sql = extract_xml(text, "sql")
    if not sql:
        m = re.search(r"```(?:sql)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
        sql = m.group(1) if m else ""
    sql = re.sub(r"^```(?:sql)?\s*|```$", "", sql.strip(), flags=re.IGNORECASE).strip()
    return html.unescape(sql)  # the model sometimes writes &gt; / &lt; inside the tag


def _verdict(s: str) -> str:
    return s.strip().upper().replace(" ", "_").replace("-", "_")


def read_grade(text: str) -> tuple[str | None, str]:
    tagged = extract_xml(text, "evaluation")
    if tagged:
        v = _verdict(tagged)
        return (v if v in VERDICTS else None), extract_xml(text, "feedback")
    # No tags: some models answer just "PASS", or a verdict line followed by the feedback.
    first, _, rest = text.strip().partition("\n")
    v = _verdict(first)
    return (v, extract_xml(text, "feedback") or rest.strip()) if v in VERDICTS else (None, "")
