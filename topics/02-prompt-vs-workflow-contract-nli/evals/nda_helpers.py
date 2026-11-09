"""Test helpers for topic 2: a tiny fake ContractNLI file and small builders. No network."""


def _doc(doc_id: int, parts: list[str], annotations: dict) -> dict:
    text, spans = "", []
    for p in parts:
        start = len(text)
        text += p
        spans.append([start, start + len(p)])
        text += "\n"
    return {
        "id": doc_id,
        "file_name": f"nda-{doc_id}.pdf",
        "text": text,
        "document_type": "search-pdf",
        "url": f"https://example.com/{doc_id}.pdf",
        "spans": spans,
        "annotation_sets": [{"annotations": annotations}],
    }


FAKE_RAW = {
    "documents": [
        _doc(
            3,
            ["  MUTUAL NDA  ", "Recipient shall not reverse engineer anything.", "This Agreement ends after 2 years."],
            {"nda-1": {"choice": "NotMentioned", "spans": []}, "nda-2": {"choice": "Contradiction", "spans": [1]}},
        ),
        _doc(
            1,
            ["NON-DISCLOSURE AGREEMENT", "The Recipient may share it with its employees.", "Notice is required."],
            {"nda-1": {"choice": "Entailment", "spans": [1]}, "nda-2": {"choice": "NotMentioned", "spans": []}},
        ),
        _doc(
            2,
            ["CONFIDENTIALITY AGREEMENT", "All information must be marked confidential."],
            {"nda-1": {"choice": "Entailment", "spans": [1]}, "nda-2": {"choice": "NotMentioned", "spans": []}},
        ),
    ],
    "labels": {
        "nda-1": {"short_description": "Explicit identification", "hypothesis": "All Confidential Information shall be expressly identified."},
        "nda-2": {"short_description": "Technical only", "hypothesis": "Confidential Information shall only include technical information."},
    },
}


# ---------------------------------------------------------------- levels
from types import SimpleNamespace  # noqa: E402

from ndaflow.data import load_statements  # noqa: E402
from ndaflow.models import Contract  # noqa: E402
from shared.llm import Tracker  # noqa: E402

SMALL_CONTRACT = Contract(
    "T1",
    "t1.pdf",
    [
        "NON-DISCLOSURE AGREEMENT",
        "The Recipient may share Confidential Information with its employees.",
        "This Agreement is governed by the laws of Delaware.",
        "",
    ],
)


def fake_llm(monkeypatch, responses: dict[str, str]):
    """Replace ndaflow.levels.llm_call. Answers by the longest label prefix that matches; records every call."""
    calls = []

    def _fake(prompt, *, label="", **kwargs):
        calls.append(SimpleNamespace(label=label, prompt=prompt, kwargs=kwargs))
        matches = [k for k in responses if label.startswith(k)]
        if not matches:
            raise AssertionError(f"unexpected llm call with label {label!r}")
        answer = responses[max(matches, key=len)]
        return answer(label, prompt) if callable(answer) else answer

    monkeypatch.setattr("ndaflow.levels.llm_call", _fake)
    return calls


def ctx():
    from ndaflow.levels import Ctx

    return Ctx(load_statements(), "gpt-6-luna", Tracker())


def tags(answers: dict[str, str]) -> str:
    """Level-0 style answer text: {sid: "label|1, 2"} -> <sid><label>..</label><evidence>..</evidence></sid>."""
    out = []
    for sid, value in answers.items():
        label, _, ev = value.partition("|")
        out.append(f"<{sid}><label>{label}</label><evidence>{ev or 'none'}</evidence></{sid}>")
    return "\n".join(out)
