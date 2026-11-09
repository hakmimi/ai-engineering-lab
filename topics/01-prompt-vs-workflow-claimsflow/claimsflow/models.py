"""The shapes every level reads and returns."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class Attachment:
    filename: str
    text: str


@dataclass
class Claim:
    claim_id: str
    customer_id: str
    submitted: date
    description: str
    attachments: list[Attachment]


@dataclass
class Policy:
    policy_number: str
    line: str  # car | home | travel
    start: date
    end: date
    deductible: int
    cap: int | None
    private_rate: float
    addons: list[str]
    listed_drivers: list[dict]
    min_driver_age: int | None
    caps_by_type: dict[str, int] = field(default_factory=dict)  # travel: separate caps per claim type


@dataclass
class Customer:
    customer_id: str
    name: str
    policies: list[Policy]


@dataclass
class Figures:
    recognized_amount: int
    provider: str | None = None  # network | private | None


@dataclass
class Result:
    decision: str
    amount: int
    doc_problems: list[str] = field(default_factory=list)  # [] means documents complete
    reason: str = ""
    claim_type: str | None = None
    figures: Figures | None = None  # answer key only: the numbers behind the amount
