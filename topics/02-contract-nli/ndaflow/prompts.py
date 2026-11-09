"""Prompt text and renderers. Fixed text goes in cached system blocks; the contract goes in the user prompt."""

from __future__ import annotations

from ndaflow.models import Contract, Statement

ROLE = (
    "You review non-disclosure agreements (NDAs) for a legal team. "
    "Judge each statement strictly by what the contract text says. "
    "In a mutual NDA each party is both a Disclosing Party and a Receiving Party."
)

LABEL_RULES = """\
## Labels (use exactly one per statement)
- entailment: the contract says it, or clearly makes it true
- contradiction: the contract says the opposite, or forbids it
- not_mentioned: the contract does not address it

## Evidence
The numbers of every span that supports the label, comma-separated (all of them, even if they repeat the same point).
Write none when the label is not_mentioned.
"""


def render_contract(c: Contract, span_ids: list[int] | None = None) -> str:
    """One line per span, '[12] text'. span_ids=None shows all spans; empty spans are skipped, numbers kept."""
    ids = range(len(c.spans)) if span_ids is None else span_ids
    return "\n".join(f"[{i}] {c.spans[i]}" for i in ids if c.spans[i])


def statements_text(statements: list[Statement]) -> str:
    return "\n".join(f"- {s.sid} ({s.short}): {s.text}" for s in statements)


def contract_prompt(c: Contract) -> str:
    return f"Contract {c.doc_id} (each span starts with its number):\n\n{render_contract(c)}"


# ---------------------------------------------------------------- level 0
def level0_system(statements: list[Statement]) -> str:
    first = statements[0].sid
    return "\n\n".join([
        ROLE,
        "Check the contract against each of these statements:",
        statements_text(statements),
        LABEL_RULES,
        "## Answer format\n"
        "Think it through, then for every statement, in the order above, write one block like this:\n"
        f"<{first}><label>entailment, contradiction or not_mentioned</label><evidence>span numbers, or none</evidence></{first}>",
    ])
