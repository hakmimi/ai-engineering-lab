import random

import pytest

from ndaflow.models import Contract, Statement
from ndaspeed.packs import (
    PING, Question, est_tokens, instructions, long_questions, make_pack, question_text, read_answer, short_questions, stack_to,
)


def _c(doc_id: str, n_spans: int = 4, width: int = 40) -> Contract:
    return Contract(doc_id, f"{doc_id}.pdf", [f"span {i} " + "x" * width for i in range(n_spans)])


STATEMENTS = [Statement(f"nda-{i}", f"short {i}", f"statement {i}") for i in range(1, 18)]


def test_make_pack_numbers_contracts_and_keeps_span_ids():
    pack = make_pack("p", [_c("10"), _c("20")])
    assert pack.codes == ["C01", "C02"]
    assert "## Contract C02" in pack.text
    assert "[3] span 3" in pack.text
    assert pack.est_tokens == est_tokens(pack.text) == len(pack.text) // 4


def test_stack_to_stops_at_first_prefix_over_target():
    contracts = [_c(str(i), n_spans=10, width=400) for i in range(10)]
    target = est_tokens(make_pack("x", contracts[:2]).text) + 1  # just over two contracts
    out = stack_to(contracts, target)
    assert len(out) == 3
    assert est_tokens(make_pack("x", out).text) >= target


def test_stack_to_raises_when_too_few():
    with pytest.raises(ValueError, match="180000"):
        stack_to([_c("1")], 180_000)


def test_long_questions_distinct_contracts_and_repeatable():
    pack = make_pack("long", [_c(str(i)) for i in range(30)])
    a = long_questions(pack, STATEMENTS, 17, random.Random(2026))
    b = long_questions(pack, STATEMENTS, 17, random.Random(2026))
    assert a == b
    assert len({q.code for q in a}) == 17
    assert all(q.doc_id == pack.contracts[pack.codes.index(q.code)].doc_id for q in a)


def test_short_questions_are_17_in_dataset_order():
    pack = make_pack("short", [_c("7")])
    qs = short_questions(pack, STATEMENTS)
    assert [q.sid for q in qs] == [s.sid for s in STATEMENTS]
    assert {q.code for q in qs} == {"C01"} and {q.doc_id for q in qs} == {"7"}


def test_instructions_put_nonce_first_and_same_without_nonce_is_stable():
    assert instructions("run-id: abc").startswith("run-id: abc\n")
    assert instructions(None) == instructions(None)
    assert "<answer>" in instructions(None)


def test_question_text_names_contract_code():
    assert question_text(Question("C07", "7", "nda-1", "It may share.")) == "Contract C07: It may share."
    assert PING


def test_read_answer_reads_block_and_drops_unknown_spans():
    c = _c("1", n_spans=4)
    a = read_answer("Sure. <answer><label>Entailment</label><evidence>1, 3, 99</evidence></answer>", c)
    assert (a.label, a.evidence) == ("entailment", [1, 3])


def test_read_answer_without_block_is_error():
    assert read_answer("entailment, see span 2", _c("1")).label == "error"
