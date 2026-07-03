"""Prompt templates for the bilateral comparison agent.

Each template builds system + user messages for the AI Gateway's ``chat()``
method. The comparison agent classifies divergence between two clause texts
using the RCBSF 5-dimension taxonomy (P-14).

Accuracy ceiling: ≤64% F1 for binary discrepancy (P-4, §6.4).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openreview_cli.review.models import Category, ClauseAssessment


RCBSF_DESCRIPTIONS = {
    "category": "Clause types differ between parties (e.g., Party A has 'Confidentiality' while Party B has 'Non-Disclosure')",
    "location": "Same concept appears in different sub-clauses or sections",
    "evidence": "Different evidentiary basis or standard (e.g., 'reasonable efforts' vs 'best efforts')",
    "issue": "Risk assessment differs — one party's position is more favourable than the other's",
    "suggestion": "Remedy or recommended action differs (e.g., 2-year vs 5-year term)",
}

SYSTEM_PROMPT = (
    "You are a contract comparison agent. Your task is to compare two clauses "
    "from two parties' versions of the same contract and detect material "
    "divergences between them.\n\n"
    "Use the RCBSF 5-dimension taxonomy to classify any divergence:\n"
    f"- **category**: {RCBSF_DESCRIPTIONS['category']}\n"
    f"- **location**: {RCBSF_DESCRIPTIONS['location']}\n"
    f"- **evidence**: {RCBSF_DESCRIPTIONS['evidence']}\n"
    f"- **issue**: {RCBSF_DESCRIPTIONS['issue']}\n"
    f"- **suggestion**: {RCBSF_DESCRIPTIONS['suggestion']}\n"
    'If there is no material divergence, use "no_divergence".\n\n'
    "Note: Binary discrepancy detection accuracy is bounded at approximately "
    "64% F1 per published research (P-4). All divergence classifications are "
    "provisional and should not be treated as definitive legal analysis.\n\n"
    "This tool is EXPERIMENTAL. It does not provide legal advice. Do not "
    "prescribe specific actions — describe divergences only. Always use "
    'descriptive language ("Party A requires X while Party B requires Y") '
    'rather than prescriptive language ("this clause should be changed").\n\n'
    "Respond ONLY with valid JSON — no preamble, no explanation:\n"
    "{\n"
    '  "divergence": "category" | "location" | "evidence" | "issue" | '
    '"suggestion" | "no_divergence",\n'
    '  "confidence": 0.0-1.0,\n'
    '  "citations": ["text excerpt from Party A", "text excerpt from Party B"],\n'
    '  "rationale": "explanation of the divergence classification"\n'
    "}"
)


def build_comparison_messages(
    clause_a_text: str,
    clause_b_text: str,
    assessment_a: ClauseAssessment,
    assessment_b: ClauseAssessment,
    category: Category | None = None,
) -> list[dict[str, str]]:
    """Build chat messages for the comparison agent.

    Parameters
    ----------
    clause_a_text : str
        Full text of Party A's clause.
    clause_b_text : str
        Full text of Party B's clause.
    assessment_a : ClauseAssessment
        Single-party extraction + QA assessment for Party A.
    assessment_b : ClauseAssessment
        Single-party extraction + QA assessment for Party B.
    category : Category | None
        The playbook category, if any, for context.

    Returns
    -------
    list[dict[str, str]]
        Two messages: system (role + instructions) and user (clause texts + assessments).
    """
    category_context = ""
    if category is not None:
        category_context = (
            f"## Playbook Category\n"
            f"Category: {category.name} ({category.id})\n"
            f"Description: {category.description}\n\n"
        )

    system = SYSTEM_PROMPT

    user = (
        f"{category_context}"
        f"## Party A's Clause\n"
        f"```\n{clause_a_text}\n```\n\n"
        f"## Party B's Clause\n"
        f"```\n{clause_b_text}\n```\n\n"
        f"## Party A's Assessment\n"
        f"- Position: {assessment_a.position.value}\n"
        f"- Confidence: {assessment_a.confidence}\n"
        f'- Citation: "{assessment_a.citation}"\n\n'
        f"## Party B's Assessment\n"
        f"- Position: {assessment_b.position.value}\n"
        f"- Confidence: {assessment_b.confidence}\n"
        f'- Citation: "{assessment_b.citation}"\n\n'
        "Return JSON:\n"
        "{\n"
        '  "divergence": "category" | "location" | "evidence" | "issue" | '
        '"suggestion" | "no_divergence",\n'
        '  "confidence": 0.0-1.0,\n'
        '  "citations": ["excerpt from A", "excerpt from B"],\n'
        '  "rationale": "explanation of divergence"\n'
        "}"
    )

    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
