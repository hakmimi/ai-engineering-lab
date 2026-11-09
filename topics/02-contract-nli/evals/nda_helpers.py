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
