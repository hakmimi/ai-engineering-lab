"""Load the made-up policies, customers, claims and answer key from data/."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from claimsflow.models import Attachment, Claim, Customer, Figures, Policy, Result

DATA = Path(__file__).resolve().parent.parent / "data"

_WORDING_FILES = {"car": "car.md", "home": "water_damage.md", "travel": "travel.md"}


def _read_json(name: str, data_dir: Path):
    return json.loads((data_dir / name).read_text(encoding="utf-8"))


def load_wordings(data_dir: Path = DATA) -> dict[str, str]:
    return {line: (data_dir / "policies" / f).read_text(encoding="utf-8") for line, f in _WORDING_FILES.items()}


def _policy(p: dict) -> Policy:
    return Policy(
        policy_number=p["policy_number"],
        line=p["line"],
        start=date.fromisoformat(p["start"]),
        end=date.fromisoformat(p["end"]),
        deductible=p["deductible"],
        cap=p["cap"],
        private_rate=p["private_rate"],
        addons=p["addons"],
        listed_drivers=p["listed_drivers"],
        min_driver_age=p["min_driver_age"],
        caps_by_type=p.get("caps_by_type", {}),
    )


def load_customers(data_dir: Path = DATA) -> dict[str, Customer]:
    raw = _read_json("customers.json", data_dir)
    return {cid: Customer(cid, c["name"], [_policy(p) for p in c["policies"]]) for cid, c in raw.items()}


def load_claims(data_dir: Path = DATA) -> list[Claim]:
    return [
        Claim(
            claim_id=c["claim_id"],
            customer_id=c["customer_id"],
            submitted=date.fromisoformat(c["submitted"]),
            description=c["description"],
            attachments=[Attachment(a["filename"], a["text"]) for a in c["attachments"]],
        )
        for c in _read_json("claims.json", data_dir)
    ]


def load_answer_key(data_dir: Path = DATA) -> dict[str, Result]:
    out = {}
    for cid, r in _read_json("answer_key.json", data_dir).items():
        figures = Figures(**r["figures"]) if r.get("figures") else None
        out[cid] = Result(r["decision"], r["amount"], r["doc_problems"], r["reason"], r["claim_type"], figures)
    return out
