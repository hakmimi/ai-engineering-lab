"""Compare a level's results with the answer key."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from claimsflow.models import Result


@dataclass
class Scores:
    n: int
    decision_right: float
    amount_right: float
    doc_caught: float  # of claims whose key has document problems: share flagged with the same documents
    doc_false_alarms: float  # of claims whose key has no document problems: share wrongly flagged
    errors: int

    def as_dict(self) -> dict:
        return asdict(self)


def _share(hits: int, total: int) -> float:
    return hits / total if total else 0.0


def score(results: dict[str, Result], key: dict[str, Result]) -> Scores:
    ids = [cid for cid in key if cid in results]
    with_docs = [cid for cid in ids if key[cid].doc_problems]
    without_docs = [cid for cid in ids if not key[cid].doc_problems]
    return Scores(
        n=len(ids),
        decision_right=_share(sum(results[c].decision == key[c].decision for c in ids), len(ids)),
        amount_right=_share(sum(results[c].decision != "error" and results[c].amount == key[c].amount for c in ids), len(ids)),
        doc_caught=_share(
            sum(
                results[c].decision == "request_documents" and set(results[c].doc_problems) == set(key[c].doc_problems)
                for c in with_docs
            ),
            len(with_docs),
        ),
        doc_false_alarms=_share(sum(results[c].decision == "request_documents" for c in without_docs), len(without_docs)),
        errors=sum(results[c].decision == "error" for c in ids),
    )
