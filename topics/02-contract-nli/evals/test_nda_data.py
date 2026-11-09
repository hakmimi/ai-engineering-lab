from nda_helpers import FAKE_RAW

from ndaflow.build_data import build_set
from ndaflow.data import SETS, load_answer_key, load_contracts, load_statements
from ndaflow.models import LABELS, STATEMENT_IDS


def test_build_set_maps_labels_and_span_text():
    out = build_set(FAKE_RAW, n=3, seed=2026)
    assert [c["doc_id"] for c in out] == ["1", "2", "3"]  # sorted by dataset id
    one = out[0]
    assert one["spans"][0] == "NON-DISCLOSURE AGREEMENT"
    assert out[2]["spans"][0] == "MUTUAL NDA"  # text[s:e].strip()
    assert one["key"]["nda-1"] == {"label": "entailment", "evidence": [1]}
    assert one["key"]["nda-2"] == {"label": "not_mentioned", "evidence": []}
    assert out[2]["key"]["nda-2"] == {"label": "contradiction", "evidence": [1]}


def test_build_set_draws_n_and_is_repeatable():
    first = build_set(FAKE_RAW, n=2, seed=2026)
    assert len(first) == 2
    assert first == build_set(FAKE_RAW, n=2, seed=2026)


def test_committed_sets_have_30_contracts_each_and_do_not_overlap():
    main, test = load_contracts("main"), load_contracts("test")
    assert len(main) == len(test) == 30
    assert not {c.doc_id for c in main} & {c.doc_id for c in test}


def test_every_key_covers_the_17_statements_with_valid_evidence():
    ids = [s.sid for s in load_statements()]
    assert ids == STATEMENT_IDS and len(ids) == 17
    for set_name in SETS:
        contracts = {c.doc_id: c for c in load_contracts(set_name)}
        key = load_answer_key(set_name)
        assert set(key) == set(contracts)
        for doc_id, answers in key.items():
            assert list(answers) == ids
            for a in answers.values():
                assert a.label in LABELS
                assert (a.label == "not_mentioned") == (a.evidence == [])
                assert all(0 <= i < len(contracts[doc_id].spans) for i in a.evidence)
