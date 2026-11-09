"""Compare a level's answers with the dataset's labels, pair by pair (contract × statement)."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from ndaflow.models import Answers


@dataclass
class Scores:
    n_pairs: int
    label_right: float
    f1_entailment: float
    f1_contradiction: float
    evidence_recall: float  # of the key's evidence spans (on entailment/contradiction pairs): share named
    evidence_precision: float  # of the spans named: share that are in the key
    errors: int

    def as_dict(self) -> dict:
        return asdict(self)


def _share(hits: int, total: int) -> float:
    return hits / total if total else 0.0


def _f1(pairs, label: str) -> float:
    tp = sum(p.label == label and k.label == label for k, p in pairs)
    fp = sum(p.label == label and k.label != label for k, p in pairs)
    fn = sum(p.label != label and k.label == label for k, p in pairs)
    return _share(2 * tp, 2 * tp + fp + fn)


def score(results: dict[str, Answers], key: dict[str, Answers]) -> Scores:
    pairs = [(k, results[doc][sid]) for doc in key if doc in results for sid, k in key[doc].items()]
    with_evidence = [(k, p) for k, p in pairs if k.label != "not_mentioned"]
    named = [(k, p) for k, p in pairs if p.evidence]
    return Scores(
        n_pairs=len(pairs),
        label_right=_share(sum(p.label == k.label for k, p in pairs), len(pairs)),
        f1_entailment=_f1(pairs, "entailment"),
        f1_contradiction=_f1(pairs, "contradiction"),
        evidence_recall=_share(sum(len(set(k.evidence) & set(p.evidence)) for k, p in with_evidence), sum(len(k.evidence) for k, _ in with_evidence)),
        evidence_precision=_share(sum(len(set(k.evidence) & set(p.evidence)) for k, p in named), sum(len(p.evidence) for _, p in named)),
        errors=sum(p.label == "error" for _, p in pairs),
    )
