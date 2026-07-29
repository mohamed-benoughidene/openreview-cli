"""Structural citation grounding metrics — computed deterministically.

Provides CP (Citation Precision), CR (Citation Relevance), and CL (Citation
Locality) metrics for a set of grounding verdicts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openreview_cli.grounding.models import CGMetrics, GroundingResult
    from openreview_cli.parsing.models import Clause, Document

from openreview_cli.parsing.clause_detector import count_paragraphs


def _compute_cp(
    grounded: list[GroundingResult],
    clause_exists: set[str],
) -> int:
    """CP: count grounded claims whose clause_id exists in source (or is non-empty as fallback)."""
    if clause_exists:
        return sum(1 for v in grounded if any(p.clause_id in clause_exists for p in v.provenances))
    return sum(1 for v in grounded if any(p.clause_id.strip() for p in v.provenances))


def _compute_cr(
    grounded: list[GroundingResult],
    clause_text_map: dict[str, str],
    claim_text_by_index: dict[int, str] | None,
    n_grounded: int,
) -> int:
    """CR: count grounded claims whose text is a substring of the cited clause text."""
    if not clause_text_map or not claim_text_by_index:
        return n_grounded  # ponytail: fallback — assume all relevant
    cr_valid = 0
    for v in grounded:
        claim_text = claim_text_by_index.get(v.claim_index, "")
        if not claim_text.strip():
            continue
        for p in v.provenances:
            source_text = clause_text_map.get(p.clause_id, "")
            if claim_text.lower() in source_text.lower():
                cr_valid += 1
                break
    return cr_valid


def _compute_cl(
    grounded: list[GroundingResult],
    clause_paragraph_count: dict[str, int],
) -> float:
    """CL: average proportion of provenances with valid paragraph_index.

    When clause paragraph counts are available, validates that the
    paragraph_index is within the clause's paragraph range. Otherwise
    falls back to checking ``paragraph_index >= 0``.
    """
    cl_sum = 0.0
    for v in grounded:
        if v.provenances:
            if clause_paragraph_count:
                valid_indices = sum(
                    1
                    for p in v.provenances
                    if 0 <= p.paragraph_index < clause_paragraph_count.get(p.clause_id, 0)
                )
            else:
                # ponytail: fallback — check non-negative paragraph_index
                valid_indices = sum(1 for p in v.provenances if p.paragraph_index >= 0)
            cl_sum += valid_indices / max(len(v.provenances), 1)
    return cl_sum / max(len(grounded), 1)


def compute_cg_metrics(
    verdicts: list[GroundingResult],
    source_document: Document,
    source_clauses: list[Clause] | None = None,
    claim_text_by_index: dict[int, str] | None = None,
) -> CGMetrics:
    """Compute structural CP/CR/CL metrics for a set of grounding verdicts.

    Args:
        verdicts: The list of GroundingResult objects from a discriminator run.
        source_document: The parsed source document (metadata only).
        source_clauses: The parsed clause objects from the source document.
            When provided, enables clause-text-aware CP, CR, and CL.
        claim_text_by_index: Mapping of claim index to claim text.
            Required for CR when ``source_clauses`` is provided.

    Returns:
        CGMetrics with citation_precision, citation_relevance, citation_locality.
    """
    from openreview_cli.grounding.models import CGMetrics, GroundingVerdict

    grounded = [v for v in verdicts if v.verdict == GroundingVerdict.GROUNDED]
    n_grounded = len(grounded)

    if n_grounded == 0:
        return CGMetrics(
            citation_precision=1.0,
            citation_relevance=1.0,
            citation_locality=1.0,
        )

    # Build clause lookups when source_clauses is available
    clause_exists: set[str] = set()
    clause_text_map: dict[str, str] = {}
    clause_paragraph_count: dict[str, int] = {}
    if source_clauses:
        clause_exists = {c.id for c in source_clauses}
        clause_text_map = {c.id: c.text for c in source_clauses}
        clause_paragraph_count = {
            c.id: c.paragraph_count if c.paragraph_count is not None else count_paragraphs(c.text)
            for c in source_clauses
        }

    cp_valid = _compute_cp(grounded, clause_exists)
    cr_valid = _compute_cr(grounded, clause_text_map, claim_text_by_index, n_grounded)
    cl_avg = _compute_cl(grounded, clause_paragraph_count)

    return CGMetrics(
        citation_precision=round(cp_valid / n_grounded, 4),
        citation_relevance=round(cr_valid / n_grounded, 4),
        citation_locality=round(cl_avg, 4),
    )
