"""Test helpers: a fake llm_call and small claim builders. No network."""

from datetime import date
from types import SimpleNamespace

from claimsflow.data import load_customers, load_wordings
from claimsflow.levels import Ctx
from claimsflow.models import Attachment, Claim
from shared.llm import Tracker

FULL_APPROVE_XML = (
    "<decision>approve_full</decision><amount>10500</amount><doc_problems>none</doc_problems><reason>ok</reason>"
)
FULL_APPROVE_XML_WITH_TYPE = "<claim_type>car</claim_type>" + FULL_APPROVE_XML

CAR_CUSTOMER = "C001"  # car (deductible 1,500), home, travel (cancellation cap 5,000, no deductible)
CUSTOMER_WITHOUT_HOME = "C011"  # car only
TRAVEL_CUSTOMER = "C008"  # car + travel


def fake_llm(monkeypatch, responses: dict[str, str]):
    """Replace claimsflow.levels.llm_call. Answers by the longest label prefix that matches."""
    calls = []

    def _fake(prompt, *, label="", **kwargs):
        calls.append(SimpleNamespace(label=label, prompt=prompt, kwargs=kwargs))
        matches = [k for k in responses if label.startswith(k)]
        if not matches:
            raise AssertionError(f"unexpected llm call with label {label!r}")
        return responses[max(matches, key=len)]

    monkeypatch.setattr("claimsflow.levels.llm_call", _fake)
    return calls


def ctx():
    return Ctx(load_customers(), load_wordings(), "claude-haiku-5-5", Tracker())


def claim_for(customer_id: str) -> Claim:
    return Claim(
        f"T-{customer_id}",
        customer_id,
        date(2026, 5, 1),
        "Test claim.",
        [Attachment("claim_form.txt", "CLAIM FORM\nSigned.")],
    )


def claim_with_no_attachments(customer_id: str) -> Claim:
    c = claim_for(customer_id)
    c.attachments = []
    return c
