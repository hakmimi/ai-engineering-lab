"""The levels we compare. Each takes a claim and returns a Result.

Level 0: one big prompt.
Level 1: route first, then a prompt for that claim type.
Level 2: + check all required documents at the same time.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable, TypeVar

from claimsflow import prompts
from claimsflow.models import Claim, Customer, Policy, Result
from claimsflow.rules import CLAIM_TYPES, DECISIONS, REQUIRED_DOCS, find_policy
from shared.llm import Tracker, extract_xml, llm_call


@dataclass
class Ctx:
    customers: dict[str, Customer]
    wordings: dict[str, str]  # keyed by line: car, home, travel
    model: str
    tracker: Tracker


# ---------------------------------------------------------------- parsing
def normalize_type(label: str) -> str | None:
    key = re.sub(r"[\s\-]+", "_", label.strip().lower())
    return key if key in CLAIM_TYPES else None


def parse_int(text: str) -> int | None:
    digits = re.sub(r"[^\d.]", "", text.replace(",", ""))
    if not digits:
        return None
    try:
        return round(float(digits))
    except ValueError:
        return None


def parse_result(text: str, claim_type: str | None) -> Result:
    decision = extract_xml(text, "decision").strip().lower()
    reason = extract_xml(text, "reason")
    if decision not in DECISIONS:
        return Result("error", 0, [], f"Unreadable answer: {text[:200]}", claim_type)
    amount = parse_int(extract_xml(text, "amount"))
    if amount is None:
        if decision.startswith("approve"):
            return Result("error", 0, [], f"Unreadable amount: {text[:200]}", claim_type)
        amount = 0
    raw_docs = extract_xml(text, "doc_problems").strip()
    docs = [] if raw_docs.lower() in ("", "none") else [d.strip() for d in raw_docs.split(",") if d.strip()]
    return Result(decision, amount, docs, reason, claim_type)


def _call(ctx: Ctx, prompt: str, label: str, cached_system: str) -> str:
    return llm_call(prompt, cached_system=cached_system, model=ctx.model, label=label, tracker=ctx.tracker)


# ---------------------------------------------------------------- level 0
def run_level0(claim: Claim, ctx: Ctx) -> Result:
    customer = ctx.customers[claim.customer_id]
    system = prompts.level0_system(ctx.wordings, CLAIM_TYPES)
    prompt = prompts.render_customer(customer, customer.policies) + "\n\n" + prompts.render_claim(claim)
    text = _call(ctx, prompt, "level0", system)
    raw_type = extract_xml(text, "claim_type")
    claim_type = normalize_type(raw_type)
    result = parse_result(text, claim_type)
    if claim_type is None and result.decision != "error":
        result.decision = "hand_to_person" if raw_type.strip().lower() in ("unclear", "") else result.decision
    return result


# ---------------------------------------------------------------- level 1
def route(claim: Claim, ctx: Ctx) -> str | None:
    text = _call(ctx, f"Customer's description:\n{claim.description}", "route", prompts.ROUTE_SYSTEM)
    return normalize_type(extract_xml(text, "claim_type"))


def _route_and_policy(claim: Claim, ctx: Ctx):
    """Shared start of levels 1-3. Returns (claim_type, policy, early_result)."""
    claim_type = route(claim, ctx)
    if claim_type is None:
        return None, None, Result("hand_to_person", 0, [], "The claim type is unclear.", None)
    policy = find_policy(ctx.customers[claim.customer_id], claim_type)
    if policy is None:
        return claim_type, None, Result("decline", 0, [], "No matching policy", claim_type)
    return claim_type, policy, None


def _decide(claim: Claim, claim_type: str, policy, ctx: Ctx, docs_verified: bool = False) -> Result:
    customer = ctx.customers[claim.customer_id]
    system = prompts.decide_system(ctx.wordings[policy.line], claim_type, docs_verified)
    prompt = prompts.render_customer(customer, [policy]) + "\n\n" + prompts.render_claim(claim)
    return parse_result(_call(ctx, prompt, "decide", system), claim_type)


def run_level1(claim: Claim, ctx: Ctx) -> Result:
    claim_type, policy, early = _route_and_policy(claim, ctx)
    if early:
        return early
    return _decide(claim, claim_type, policy, ctx)


# ---------------------------------------------------------------- level 2
T = TypeVar("T")
R = TypeVar("R")


def parallel(fn: Callable[[T], R], items: list[T], n_workers: int = 4) -> list[R]:
    """Run fn on every item at the same time; results come back in input order."""
    with ThreadPoolExecutor(max_workers=n_workers) as pool:
        return list(pool.map(fn, items))


def check_documents(claim: Claim, claim_type: str, policy: Policy, ctx: Ctx) -> list[tuple[str, str]]:
    """One call per required document, all at once. Returns (doc_id, problem) for each problem, in REQUIRED_DOCS order."""
    customer_text = prompts.render_customer(ctx.customers[claim.customer_id], [policy])
    claim_text = prompts.render_claim(claim)

    def check(doc_id: str):
        prompt = prompts.doc_check_prompt(doc_id, customer_text, claim_text)
        text = _call(ctx, prompt, f"doc:{doc_id}", prompts.DOC_CHECK_SYSTEM)
        status = extract_xml(text, "status").lower()
        if status == "ok":
            return None
        problem = extract_xml(text, "problem") or f"{doc_id}: unclear answer from the document check"
        return doc_id, problem

    return [p for p in parallel(check, REQUIRED_DOCS[claim_type]) if p]


def _docs_or_none(claim: Claim, claim_type: str, policy: Policy, ctx: Ctx) -> Result | None:
    problems = check_documents(claim, claim_type, policy, ctx)
    if not problems:
        return None
    reason = " ".join(problem for _, problem in problems)
    return Result("request_documents", 0, [d for d, _ in problems], reason, claim_type)


def run_level2(claim: Claim, ctx: Ctx) -> Result:
    claim_type, policy, early = _route_and_policy(claim, ctx)
    if early:
        return early
    return _docs_or_none(claim, claim_type, policy, ctx) or _decide(claim, claim_type, policy, ctx, docs_verified=True)
