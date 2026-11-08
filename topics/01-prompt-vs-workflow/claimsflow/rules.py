"""Plain-code rules: claim types, required documents, policy lookup and payout math."""

from __future__ import annotations

from dataclasses import replace

from claimsflow.models import Customer, Figures, Policy

DECISIONS = ("approve_full", "approve_partial", "decline", "request_documents", "hand_to_person")

CLAIM_TYPES = ("car", "water_damage", "travel_medical", "travel_cancellation")

LINE_FOR_TYPE = {
    "car": "car",
    "water_damage": "home",
    "travel_medical": "travel",
    "travel_cancellation": "travel",
}

REQUIRED_DOCS: dict[str, list[str]] = {
    "car": ["claim_form", "drivers_license", "damage_photos", "assessor_report"],
    "water_damage": ["claim_form", "damage_photos", "plumber_finding", "repair_quote"],
    "travel_medical": ["claim_form", "medical_summary", "receipts"],
    "travel_cancellation": ["claim_form", "cancellation_proof", "payment_receipts", "supplier_refund_letters"],
}


def find_policy(customer: Customer, claim_type: str) -> Policy | None:
    """The customer's policy for this claim type, with the cap that applies to this type."""
    line = LINE_FOR_TYPE[claim_type]
    policy = next((p for p in customer.policies if p.line == line), None)
    if policy is None or claim_type not in policy.caps_by_type:
        return policy
    return replace(policy, cap=policy.caps_by_type[claim_type])


def compute_payout(policy: Policy, figures: Figures) -> tuple[int, str]:
    """Rate, then cap, then deductible. Partial only when a rate below 1 or the cap cut the amount."""
    rate = policy.private_rate if figures.provider == "private" else 1.0
    base = round(figures.recognized_amount * rate)
    capped = min(base, policy.cap) if policy.cap else base
    amount = max(0, capped - policy.deductible)
    decision = "approve_partial" if rate < 1.0 or capped < base else "approve_full"
    return amount, decision
