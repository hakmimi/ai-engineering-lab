"""Prompt text and renderers. Fixed text goes in cached system blocks; the claim goes in the user prompt."""

from __future__ import annotations

import json

from claimsflow.models import Claim, Customer, Policy
from claimsflow.rules import REQUIRED_DOCS

ROLE = "You are a claims handler at Meridian Mutual, a made-up insurer. Decide claims strictly by the policy wording and schedule you are given."

DOC_DESCRIPTIONS = {
    "claim_form": "a signed claim form for this event, in the policyholder's name",
    "drivers_license": "the driver's license of the person who drove at the time of the event",
    "damage_photos": "photos of the damage from this event",
    "assessor_report": "an assessor's report with the approved repair cost (a garage quote does not count)",
    "plumber_finding": "a plumber's finding that states where the water came from and why",
    "repair_quote": "a repair quote for the damaged home",
    "medical_summary": "a medical summary from the treating doctor with the diagnosis and date, for the insured",
    "receipts": "receipts for the treatment, issued in the insured's name",
    "cancellation_proof": "proof of the reason for cancelling (for example a medical certificate or a call-up order)",
    "payment_receipts": "receipts for what was paid in advance for the trip",
    "supplier_refund_letters": "letters from the airline, hotel or agency showing what they refunded",
}

DECISION_RULES = """\
## How to decide

Decisions (use exactly one):
- approve_full: covered, and paid in full after the deductible
- approve_partial: covered, but paid less than the recognized amount for a reason other than the deductible: the cap, a private-provider rate below 100%, or part of the claim excluded
- decline: no matching policy, not covered, or excluded
- request_documents: a required document is missing, or attached but wrong (not the right kind of document, another person's name, details that do not match this claim)
- hand_to_person: the claim is too unclear to tell what kind of claim it is

Rules:
1. Documents only answer "is the paperwork complete and does it belong to this claim?". If a document is missing or wrong, the decision is request_documents and the amount is 0.
2. Whether the event date is inside the policy period, and whether the driver was listed and old enough, are coverage questions: they lead to decline, not request_documents.
3. Where the recognized amount comes from: car = the assessor's report; water damage = the assessor's report if there is one, otherwise the repair quote; travel medical = the receipts; travel cancellation = paid in advance minus supplier refunds.
4. Amount = recognized amount, times the private rate if a private provider was used, then limited by the cap, then minus the deductible. Never below 0. Whole shekels.
5. A deductible alone never makes a decision approve_partial.
"""

OUTPUT_FORMAT = """\
## Answer format

Think it through, then answer with these tags only:
<decision>one decision from the list</decision>
<amount>whole shekels, digits only; 0 unless approved</amount>
<doc_problems>comma-separated ids of missing or wrong documents, or none</doc_problems>
<reason>one or two plain sentences</reason>
"""


def required_docs_text(claim_types) -> str:
    lines = ["## Required documents by claim type (use these ids)"]
    for t in claim_types:
        docs = ", ".join(f"{d} ({DOC_DESCRIPTIONS[d]})" for d in REQUIRED_DOCS[t])
        lines.append(f"- {t}: {docs}")
    return "\n".join(lines)


def render_policy(p: Policy) -> str:
    data = {
        "policy_number": p.policy_number,
        "line": p.line,
        "start": p.start.isoformat(),
        "end": p.end.isoformat(),
        "deductible": p.deductible,
        "cap": p.cap,
        "caps_by_claim_type": p.caps_by_type or None,
        "private_rate": p.private_rate,
        "addons": p.addons,
        "listed_drivers": p.listed_drivers or None,
        "min_driver_age": p.min_driver_age,
    }
    return json.dumps({k: v for k, v in data.items() if v is not None}, ensure_ascii=False)


def render_customer(c: Customer, policies: list[Policy]) -> str:
    lines = [f"Customer: {c.name} (ID {c.customer_id})", "Policy schedule:"]
    lines += [f"- {render_policy(p)}" for p in policies] or ["- (no policies)"]
    return "\n".join(lines)


def render_claim(claim: Claim) -> str:
    parts = [f"Claim {claim.claim_id}, submitted {claim.submitted.isoformat()}", f"Description: {claim.description}", "Attachments:"]
    if not claim.attachments:
        parts.append("(none)")
    for a in claim.attachments:
        parts.append(f"--- {a.filename} ---\n{a.text}")
    return "\n".join(parts)


# ---------------------------------------------------------------- level 0
def level0_system(wordings: dict[str, str], claim_types) -> str:
    return "\n\n".join(
        [
            ROLE,
            "Classify the claim as one of: car, water_damage, travel_medical, travel_cancellation. "
            "Find the customer's policy for that line (car, home, travel). "
            "If the customer has no policy for that line, decline with the reason 'No matching policy'.",
            DECISION_RULES,
            required_docs_text(claim_types),
            OUTPUT_FORMAT.replace(
                "<decision>", "<claim_type>car, water_damage, travel_medical, travel_cancellation, or unclear</claim_type>\n<decision>", 1
            ),
            "## Policy wordings",
            *wordings.values(),
        ]
    )


# ---------------------------------------------------------------- level 1+
ROUTE_SYSTEM = """\
You sort incoming insurance claims at Meridian Mutual.
Read the customer's description and choose the claim type:
- car: damage to the customer's car
- water_damage: water damage in the customer's home
- travel_medical: medical treatment during a trip abroad
- travel_cancellation: a trip cancelled before departure
- unclear: you cannot tell what happened or what was damaged
Answer with <claim_type>one value</claim_type> only.
"""


def decide_system(wording: str, claim_type: str, docs_verified: bool = False) -> str:
    note = (
        "The documents were already checked: all required documents are attached and belong to this claim. "
        "Do not request documents; decide on coverage, exclusions and the amount."
        if docs_verified
        else ""
    )
    return "\n\n".join(
        p
        for p in [ROLE, f"This is a {claim_type} claim.", note, DECISION_RULES, required_docs_text([claim_type]), OUTPUT_FORMAT, "## Policy wording", wording]
        if p
    )


# ---------------------------------------------------------------- level 2: document check
# How the checker tells that a document belongs to THIS claim. A checker sees one document at a time,
# so it applies this rule literally: write what a claims handler actually looks at for each document.
# In the data, quotes and reports name the car (plate) or the home address, not the person.
BELONGS_TO_CLAIM: dict[str, str] = {
    "claim_form": "it is in the policyholder's name and describes this event",
    "drivers_license": "it is in the name of the driver named in the claim",
    "medical_summary": "the patient is the insured and the treatment date matches the claim",
    "receipts": "they are issued to the insured for the treatment in the claim",
    # These name a car, an address or a supplier, not a person. A missing name is not a problem.
    "damage_photos": "they show damage that fits what happened in the claim",
    "assessor_report": "it is an assessor's report (not a garage quote) on the damage described in the claim, dated on or after the event; "
    "it names the car, not the person",
    "plumber_finding": "it states where the water came from and why, for the damage described in the claim; it names the plumber and the address, not the person",
    "repair_quote": "the work it describes fits the damage in the claim; it names the address of works, not the person",
    "cancellation_proof": "it states the reason for cancelling that the claim gives, for the person the claim names; "
    "whether that reason is covered is decided later, so a personal letter still counts as stating it",
    "payment_receipts": "they show what was paid in advance for the trip in the claim; they name suppliers, not the person",
    "supplier_refund_letters": "they show what the trip's suppliers refunded; they name suppliers, not the person",
}

DOC_CHECK_SYSTEM = """\
You check one required document for an insurance claim at Meridian Mutual.
You only answer: is this document attached, and is it the right one for this claim?
- ok: a matching document is attached, it is the right kind of document, it passes the matching rule given with it, and its details (dates, amounts, places) match the claim
- missing: no attachment is this kind of document
- wrong: an attachment looks like this document but it is the wrong kind, it fails the matching rule, or its details do not match the claim
Do not ask for anything the matching rule does not ask for.
Do not judge coverage, policy dates, driver age or exclusions. Those are checked later.
Answer with these tags only:
<status>ok, missing or wrong</status>
<problem>one sentence, or none</problem>
"""


def doc_check_prompt(doc_id: str, customer_text: str, claim_text: str) -> str:
    return (
        f"Required document: {doc_id} = {DOC_DESCRIPTIONS[doc_id]}\n"
        f"Matching rule (how to tell it belongs to this claim): {BELONGS_TO_CLAIM[doc_id]}\n\n"
        f"{customer_text}\n\n{claim_text}"
    )


# ---------------------------------------------------------------- level 3: the chain
def covered_system(wording: str, claim_type: str) -> str:
    return "\n\n".join([
        ROLE,
        f"This is a {claim_type} claim. Answer one question only: is this event a covered event under this policy?",
        "Check: the event date is inside the policy period; any add-on the cover needs is in the schedule; "
        "the kind of event is one the wording covers. Do not check exclusions or amounts here.",
        "Answer with these tags only:\n<covered>yes or no</covered>\n<reason>one sentence</reason>",
        "## Policy wording", wording,
    ])


def excluded_system(wording: str, claim_type: str) -> str:
    return "\n\n".join([
        ROLE,
        f"This is a {claim_type} claim that is a covered event. Answer one question only: does an exclusion in the wording apply?",
        "Check the exclusions and the conditions on who may drive, pre-existing conditions, and the cancellation reason. "
        "Use the policy schedule (listed drivers, birth dates, minimum age, add-ons) and the documents. Do not compute amounts.",
        "Answer with these tags only:\n<excluded>yes or no</excluded>\n<reason>one sentence</reason>",
        "## Policy wording", wording,
    ])


FIGURES_SOURCE = {
    "car": "recognized_amount = the approved repair cost in the assessor's report.",
    "water_damage": "recognized_amount = the total in the assessor's report if there is one, otherwise the total in the repair quote. "
    "provider = network if the plumber is in the Meridian network, otherwise private.",
    "travel_medical": "recognized_amount = the total of the receipts. "
    "provider = network if the clinic or hospital is in the Meridian network, otherwise private.",
    "travel_cancellation": "paid = the total paid in advance; refunds = the total the suppliers refunded.",
}


def figures_system(claim_type: str) -> str:
    tags = (
        "<paid>digits only</paid>\n<refunds>digits only</refunds>\n<provider>none</provider>"
        if claim_type == "travel_cancellation"
        else "<recognized_amount>digits only</recognized_amount>\n<provider>network, private or none</provider>"
    )
    return "\n\n".join([
        ROLE,
        f"This is an approved {claim_type} claim. Read the numbers from the documents. Do not apply the deductible, cap or rate: code does that.",
        FIGURES_SOURCE[claim_type],
        f"Answer with these tags only:\n{tags}",
    ])
