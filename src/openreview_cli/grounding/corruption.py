"""Corruption strategy generators for grounding accuracy testing.

Adapts P-6's four corruption strategies from court citations to contract clauses:
  - clause_swap:    Replace clause ID with a different clause from the same document
  - category_swap:  Replace playbook category while keeping clause text
  - hallucination:  Generate claim text with no support in any clause
  - anachronism:    Cite a non-existent clause ID
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openreview_cli.parsing.models import Clause


def clause_swap(claim: str, clauses: list[Clause], original_clause_id: str) -> str:
    """Replace clause ID in a claim with a different clause ID from the same document.

    Args:
        claim: The original claim text (contains original_clause_id).
        clauses: All clauses from the source document.
        original_clause_id: The clause ID currently cited in the claim.

    Returns:
        Claim text with a different (random) clause ID substituted in.
        Returns the original claim unchanged if no candidate clause exists.
    """
    candidates = [c for c in clauses if c.id != original_clause_id]
    if not candidates:
        return claim
    # Pick deterministically by hash for reproducibility
    idx = hash(claim + original_clause_id) % len(candidates)
    replacement = candidates[idx].id
    return claim.replace(original_clause_id, replacement)


def category_swap(claim: str, original_category: str, categories: list[str]) -> str:
    """Replace the playbook category label while keeping clause text unchanged.

    Args:
        claim: Claim text that may reference the playbook category.
        original_category: The current category label.
        categories: All available category labels.

    Returns:
        Claim text with a different category substituted in.
        Returns the original claim unchanged if no other category exists.
    """
    candidates = [c for c in categories if c != original_category]
    if not candidates:
        return claim
    idx = hash(claim + original_category) % len(candidates)
    replacement = candidates[idx]
    return claim.replace(original_category, replacement)


def hallucination(claim: str) -> str:
    """Generate a claim with no support in any clause of the source document.

    Args:
        claim: The original claim text (used as seed for deterministic selection).

    Returns:
        A fabricated claim text unrelated to any source clause.
    """
    fabrications: list[str] = [
        "The receiving party shall pay liquidated damages of $1,000,000 per breach.",
        "All disputes arising under this agreement shall be resolved by binding arbitration in Geneva, Switzerland.",
        "This agreement shall remain in effect for a term of 99 years from the effective date.",
        "Either party may terminate this agreement for any reason or no reason upon 30 days prior written notice.",
        "The receiving party shall indemnify and hold harmless the disclosing party against all third-party claims.",
        "This agreement may be assigned by either party without the other party's consent.",
        "The prevailing party in any legal proceeding shall be entitled to recover its reasonable attorneys' fees.",
        "The parties agree to a non-compete period of five years following termination of this agreement.",
        "Interest shall accrue on all late payments at the rate of 18 percent per annum.",
        "This agreement constitutes a binding partnership between the parties for tax purposes.",
    ]
    seed = hash(claim) % len(fabrications)
    return fabrications[seed]


def anachronism(claim: str, clause_id: str) -> str:
    """Cite a non-existent clause number.

    Replaces the clause_id reference in the claim text with a fabricated
    version number that does not exist in any real document.

    Args:
        claim: Claim text containing the clause_id.
        clause_id: The valid clause ID to be replaced.

    Returns:
        Claim text with a non-existent clause ID substituted in.
    """
    fake_id = f"v{abs(hash(clause_id)) % 9999}.99"
    return claim.replace(clause_id, fake_id)
