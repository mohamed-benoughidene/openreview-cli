"""Prompt templates for the extraction and QA agents."""

from __future__ import annotations

import json
from typing import Any


def _parse_json(raw: str, fallback: dict[str, Any]) -> dict[str, Any]:
    """Shared JSON parser with fallback for extraction and QA responses."""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return fallback
    return data  # type: ignore[no-any-return]


def build_qa_messages(
    clause_text: str,
    extracted_position: str,
    confidence: float,
    citation: str,
    category_id: str,
    category_name: str,
    preferred_desc: str,
    preferred_exemplars: list[str],
    acceptable_desc: str,
    acceptable_exemplars: list[str],
    walkaway_desc: str,
    walkaway_exemplars: list[str],
) -> list[dict[str, str]]:
    """Build messages for the QA verification agent.

    The QA agent receives the extraction output and verifies each dimension:
    position correctness, category match, citation accuracy, confidence
    appropriateness.
    """
    system = (
        "You are a senior legal review QA analyst. Your job is to verify "
        "an extraction agent's clause assessment. Check for errors in "
        "position assignment, category matching, citation accuracy, and "
        "confidence calibration. Respond ONLY with valid JSON."
    )

    pref_ex = "\n".join(f'  - "{e}"' for e in preferred_exemplars)
    acc_ex = "\n".join(f'  - "{e}"' for e in acceptable_exemplars)
    walk_ex = "\n".join(f'  - "{e}"' for e in walkaway_exemplars)

    user = (
        f"## Category: {category_name}\n"
        f"### Preferred\n{preferred_desc}\nExemplars:\n{pref_ex}\n\n"
        f"### Acceptable\n{acceptable_desc}\nExemplars:\n{acc_ex}\n\n"
        f"### Walkaway\n{walkaway_desc}\nExemplars:\n{walk_ex}\n\n"
        f"## Extraction agent's assessment\n"
        f"- Position: {extracted_position}\n"
        f"- Confidence: {confidence}\n"
        f'- Citation: "{citation}"\n'
        f"- Category: {category_id}\n\n"
        f"## Clause text\n```\n{clause_text}\n```\n\n"
        "Verify each check:\n"
        "1. Citation check: does the cited text appear verbatim in the clause?\n"
        "2. Position check: does the clause text support the assigned position?\n"
        "3. Category check: does the clause belong to this category?\n"
        "4. Confidence check: is the confidence score appropriate?\n\n"
        "Return JSON:\n"
        "{\n"
        '  "verdict": "agree" | "disagree" | "uncertain",\n'
        '  "revised_position": "preferred" | "acceptable" | "walkaway" | null,\n'
        '  "rationale": "brief explanation of disagreement or uncertainty",\n'
        '  "citation_valid": true | false,\n'
        '  "position_valid": true | false,\n'
        '  "category_valid": true | false,\n'
        '  "confidence_valid": true | false\n'
        "}"
    )

    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def parse_extraction_response(raw: str) -> dict[str, Any]:
    """Parse the extraction agent's JSON response.

    Returns a dict with keys: position, confidence, citation, category_match.
    On parse failure, returns a default uncertain response.
    """
    fallback: dict[str, Any] = {
        "position": "no-match",
        "confidence": 0.0,
        "citation": "",
        "category_match": False,
    }
    data = _parse_json(raw, fallback)
    if data is fallback:
        return fallback

    for key in ("position", "confidence", "citation"):
        if key not in data:
            return fallback

    return {
        "position": str(data["position"]),
        "confidence": float(data["confidence"]),
        "citation": str(data["citation"]),
        "category_match": bool(data.get("category_match", False)),
    }


def parse_qa_response(raw: str) -> dict[str, Any]:
    """Parse the QA agent's JSON response.

    Returns a dict with keys: verdict, revised_position, rationale,
    citation_valid, position_valid, category_valid, confidence_valid.
    On parse failure, returns an uncertain/default response.
    """
    fallback: dict[str, Any] = {
        "verdict": "uncertain",
        "revised_position": None,
        "rationale": "Could not parse QA response",
        "citation_valid": False,
        "position_valid": False,
        "category_valid": False,
        "confidence_valid": False,
    }
    data = _parse_json(raw, fallback)
    if data is fallback:
        return fallback

    if "verdict" not in data:
        return {
            "verdict": "uncertain",
            "revised_position": None,
            "rationale": "Missing verdict in QA response",
            "citation_valid": False,
            "position_valid": False,
            "category_valid": False,
            "confidence_valid": False,
        }

    return {
        "verdict": str(data.get("verdict", "uncertain")),
        "revised_position": data.get("revised_position"),
        "rationale": str(data.get("rationale", "")),
        "citation_valid": bool(data.get("citation_valid", False)),
        "position_valid": bool(data.get("position_valid", False)),
        "category_valid": bool(data.get("category_valid", False)),
        "confidence_valid": bool(data.get("confidence_valid", False)),
    }


# ── System Prompts ──────────────────────────────────────────────────────────

BASE_SYSTEM_PROMPT = (
    "You are a legal contract analyst{specialization}. Your task is to classify "
    "a single clause from a {domain} against a 3-position playbook. "
    "{vocabulary}"
    "Respond ONLY with valid JSON \u2014 no preamble, no explanation."
)

MODE_VOCABULARY: dict[str, dict[str, str]] = {
    "precheck": {
        "specialization": "",
        "domain": "Non-Disclosure Agreement",
        "vocabulary": "",
    },
    "licensecheck": {
        "specialization": " specializing in SaaS and software license agreements",
        "domain": "SaaS license agreement",
        "vocabulary": (
            "Domain vocabulary: SaaS, license grant, royalty, subscription, "
            "auto-renewal, liability cap, IP ownership, indemnification. "
        ),
    },
    "leasecheck": {
        "specialization": " specializing in commercial lease agreements",
        "domain": "commercial lease",
        "vocabulary": (
            "Domain vocabulary: commercial lease, rent escalation, CAM charges, "
            "triple-net, subletting, security deposit, termination for convenience. "
        ),
    },
    "privacycheck": {
        "specialization": " specializing in data protection and privacy law",
        "domain": "Data Processing Agreement (DPA)",
        "vocabulary": (
            "Domain vocabulary: data controller, data processor, processing purpose, "
            "sub-processor, breach notification, data retention, DPA. "
        ),
    },
    "privacycheck_v2": {
        "specialization": " specializing in data protection and privacy law",
        "domain": "Data Processing Agreement (DPA) v2",
        "vocabulary": (
            "Domain vocabulary: data controller, data processor, processing purpose, "
            "sub-processor, breach notification, data retention, cross-border transfer, "
            "transfer impact assessment, sub-processor change notification, DPA. "
        ),
    },
    "dealcheck": {
        "specialization": " specializing in commercial vendor and service agreements",
        "domain": "vendor/service agreement",
        "vocabulary": (
            "Domain vocabulary: payment terms, deliverables, milestone, "
            "termination for convenience, liability cap, indemnification, "
            "confidentiality, governing law. "
        ),
    },
    "hirecheck": {
        "specialization": " specializing in employment agreements",
        "domain": "employment agreement",
        "vocabulary": (
            "Domain vocabulary: compensation, bonus, equity, severance, "
            "IP assignment, non-compete, non-solicit, confidentiality, "
            "arbitration, at-will employment. "
        ),
    },
    "indemnitycheck": {
        "specialization": " specializing in indemnification agreements",
        "domain": "indemnification agreement",
        "vocabulary": (
            "Domain vocabulary: indemnify, hold harmless, defense, liability cap, "
            "survival, third-party claim, broad form, limited form, mutual, sole, "
            "duty to defend, settlement, obligation to indemnify. "
        ),
    },
    "consultcheck": {
        "specialization": " specializing in consulting services agreements",
        "domain": "consulting services agreement",
        "vocabulary": (
            "Domain vocabulary: statement of work, deliverable, milestone, "
            "hourly rate, fixed fee, IP ownership, work product, pre-existing "
            "materials, expense reimbursement, termination for convenience, "
            "scope of work, acceptance criteria, change order. "
        ),
    },
    "workcheck": {
        "specialization": " specializing in independent contractor and work-for-hire agreements",
        "domain": "independent contractor / work-for-hire agreement",
        "vocabulary": (
            "Domain vocabulary: independent contractor, work-for-hire, "
            "worker classification, IP assignment, pre-existing materials, "
            "non-compete, non-solicit, payment milestone, invoice, benefits, "
            "termination for convenience, scope of work. "
        ),
    },
    "loicheck": {
        "specialization": " specializing in letters of intent and MOUs",
        "domain": "letter of intent / memorandum of understanding",
        "vocabulary": (
            "Domain vocabulary: letter of intent, non-binding, exclusivity, "
            "no-shop, breakup fee, reverse breakup fee, due diligence, "
            "definitive agreement, good faith negotiation, fiduciary-out, "
            "expiration, tail period, material adverse change. "
        ),
    },
    "subcheck": {
        "specialization": " specializing in subcontractor agreements",
        "domain": "subcontractor agreement",
        "vocabulary": (
            "Domain vocabulary: subcontractor, prime contract, flow-down, "
            "incorporation by reference, pay-when-paid, pay-if-paid, retainage, "
            "change order, broad-form indemnity, backcharge, demobilization, "
            "termination for convenience, scope of work. "
        ),
    },
    "settlementcheck": {
        "specialization": " specializing in settlement and release agreements",
        "domain": "settlement and release agreement",
        "vocabulary": (
            "Domain vocabulary: release, settlement, mutual release, "
            "non-disparagement, waiver of unknown claims, Section 1542, "
            "liquidated damages, acceleration, clawback, reinstatement, "
            "lump sum, instalments, accrual, consideration. "
        ),
    },
    "settlementcheck_v2": {
        "specialization": " specializing in complex settlement and release agreements",
        "domain": "complex settlement and release agreement",
        "vocabulary": (
            "Domain vocabulary: release, settlement, mutual release, "
            "non-disparagement, waiver of unknown claims, Section 1542, "
            "liquidated damages, acceleration, clawback, reinstatement, "
            "lump sum, instalments, accrual, consideration, "
            "claims administrator, settlement class, Bar date, "
            "opt-out, structured payments, periodic payouts, "
            "true-up, balloon payment, acceleration clause, "
            "cross-indemnity, multi-party release, contribution, "
            "regulatory cooperation, no-admit, no-deny, privilege, "
            "class action, CAFA, Fairness Hearing, settlement fund. "
        ),
    },
    "assetcheck": {
        "specialization": " specializing in asset transfer and assignment agreements",
        "domain": "asset transfer agreement",
        "vocabulary": (
            "Domain vocabulary: asset, assignment, bill of sale, "
            "as-is, warranty, encumbrance, transfer, delivery, "
            "excluded assets, purchase price. "
        ),
    },
    "buycheck": {
        "specialization": " specializing in asset purchase and business acquisition agreements",
        "domain": "asset purchase agreement",
        "vocabulary": (
            "Domain vocabulary: purchase price, asset list, "
            "assumed liabilities, representations, warranties, "
            "indemnification, non-compete, bulk sale, earn-out, "
            "closing conditions. "
        ),
    },
    "engagecheck": {
        "specialization": " specializing in professional services engagement letters",
        "domain": "engagement letter",
        "vocabulary": (
            "Domain vocabulary: scope of services, deliverables, "
            "fees, expenses, IP ownership, work product, "
            "confidentiality, limitation of liability, non-solicit, "
            "termination. "
        ),
    },
    "guaranteecheck": {
        "specialization": " specializing in personal guarantee and suretyship agreements",
        "domain": "personal guarantee",
        "vocabulary": (
            "Domain vocabulary: personal guarantee, limited guarantee, "
            "continuing guarantee, waiver of defenses, subrogation, "
            "confession of judgment, maximum liability, survival. "
        ),
    },
    "loancheck": {
        "specialization": " specializing in loan agreements and promissory notes",
        "domain": "loan agreement",
        "vocabulary": (
            "Domain vocabulary: principal, interest, APR, "
            "maturity, prepayment, default, acceleration, "
            "collateral, security interest, covenant, "
            "cross-default, events of default. "
        ),
    },
    "franchisecheck": {
        "specialization": " specializing in franchise law and franchisor-franchisee agreements",
        "domain": "franchise agreement",
        "vocabulary": (
            "Domain vocabulary: franchise, franchisor, franchisee, FDD, territory, "
            "royalty, advertising fund, renewal, termination, non-compete, transfer, "
            "right of first refusal, franchise fee. "
            "Detect and flag any clauses that suggest this is a franchise relationship "
            "(trademark license + required payment + significant control over operations). "
            "Output: [FRANCHISE_BOUNDARY: yes|no|borderline]"
        ),
    },
    "opcheck": {
        "specialization": " specializing in LLC operating agreements",
        "domain": "Operating Agreement",
        "vocabulary": (
            "Domain vocabulary: operating agreement, LLC, member, manager, "
            "capital contribution, capital call, profit share, distribution, "
            "voting, transfer, buy-sell, dissolution, indemnification, IRC 704(b). "
        ),
    },
    "partnercheck": {
        "specialization": " specializing in partnership agreements",
        "domain": "partnership agreement",
        "vocabulary": (
            "Domain vocabulary: partnership, general partner, limited partner, "
            "capital contribution, profit share, loss allocation, management, "
            "withdrawal, expulsion, dissolution, joint and several liability, "
            "UPA, RUPA, non-compete, non-solicit, mediation, arbitration. "
        ),
    },
    "sponsorcheck": {
        "specialization": " specializing in sponsorship agreements",
        "domain": "sponsorship agreement",
        "vocabulary": (
            "Domain vocabulary: sponsorship, sponsor, organizer, fee, payment, "
            "exclusivity, logo placement, event recognition, trademark license, "
            "termination, force majeure, indemnification, non-disparagement. "
        ),
    },
    "distrocheck": {
        "specialization": " specializing in distribution and reseller agreements",
        "domain": "distribution agreement",
        "vocabulary": (
            "Domain vocabulary: distribution, distributor, manufacturer, territory, "
            "exclusivity, minimum purchase, cure period, pricing, payment, inventory, "
            "returns, trademark license, termination, non-compete, channel restriction, "
            "jurisdiction, venue. "
            "Detect and flag any clauses that suggest this is a franchise relationship "
            "(trademark license + required payment + significant control over operations). "
            "Output: [FRANCHISE_BOUNDARY: yes|no|borderline]"
        ),
    },
}


def _build_extraction_messages_common(
    clause_text: str,
    category_id: str,
    category_name: str,
    category_description: str,
    preferred_desc: str,
    preferred_exemplars: list[str],
    acceptable_desc: str,
    acceptable_exemplars: list[str],
    walkaway_desc: str,
    walkaway_exemplars: list[str],
    default_position: str,
    mode: str = "precheck",
) -> list[dict[str, str]]:
    """Common extraction message builder — shared by all mode-specific prompts.

    Builds the user message with category and position data, using a
    mode-specific system prompt derived from ``MODE_VOCABULARY[mode]``.
    """
    vocab = MODE_VOCABULARY[mode]
    system_prompt = BASE_SYSTEM_PROMPT.format(**vocab)

    pref_ex = "\n".join(f'  - "{e}"' for e in preferred_exemplars)
    acc_ex = "\n".join(f'  - "{e}"' for e in acceptable_exemplars)
    walk_ex = "\n".join(f'  - "{e}"' for e in walkaway_exemplars)

    user = (
        f"## Category: {category_name}\n"
        f"{category_description}\n\n"
        f"### Preferred\n"
        f"{preferred_desc}\n"
        f"Exemplars:\n{pref_ex}\n\n"
        f"### Acceptable\n"
        f"{acceptable_desc}\n"
        f"Exemplars:\n{acc_ex}\n\n"
        f"### Walkaway\n"
        f"{walkaway_desc}\n"
        f"Exemplars:\n{walk_ex}\n\n"
        f"### Default position (if no specific indicators match)\n"
        f"{default_position}\n\n"
        f"## Clause to classify\n"
        f"```\n{clause_text}\n```\n\n"
        "Return JSON:\n"
        "{\n"
        '  "position": "preferred" | "acceptable" | "walkaway" | "no-match",\n'
        '  "confidence": 0.0-1.0,\n'
        '  "citation": "exact quoted text from the clause supporting your assessment",\n'
        '  "category_match": true | false\n'
        "}"
    )

    return [{"role": "system", "content": system_prompt}, {"role": "user", "content": user}]
