"""Citation Grounding Discriminator module.

Provides LLM-based post-hoc grounding validation for assessment claims
against source document clauses.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Literal

from openreview_cli.grounding.audit import GroundingAuditLog
from openreview_cli.grounding.discriminator import CitationGroundingDiscriminator
from openreview_cli.grounding.metrics import compute_cg_metrics
from openreview_cli.grounding.models import (
    CGMetrics,
    CGReport,
    CitationProvenance,
    DiscriminationAuditEntry,
    GroundingResult,
    GroundingVerdict,
)

if TYPE_CHECKING:
    from openreview_cli.gateway.router import Gateway
    from openreview_cli.parsing.models import Clause, Document
    from openreview_cli.review.models import ReviewReport

logger = logging.getLogger(__name__)

__all__ = [
    "CGMetrics",
    "CGReport",
    "CitationGroundingDiscriminator",
    "CitationProvenance",
    "DiscriminationAuditEntry",
    "GroundingAuditLog",
    "GroundingResult",
    "GroundingVerdict",
    "compute_cg_metrics",
    "run_grounding",
]


def run_grounding(
    report: ReviewReport,
    source_document: Document,
    mode: Literal["strict", "lenient"] = "strict",
    gateway: Gateway | None = None,
    model: str | None = None,
    source_clauses: list[Clause] | None = None,
    session_id: str | None = None,
) -> CGReport:
    """Run citation grounding on a ReviewReport.

    Args:
        report: The ReviewReport from single-party review.
        source_document: The parsed source document (metadata only).
        mode: Grounding mode — 'strict' excludes ungrounded, 'lenient' flags only.
        gateway: Optional Gateway instance (defaults to creating a new one).
        model: Optional model override (defaults to gateway default).
        source_clauses: The parsed clause objects from the source document.
            When provided, enables clause-text-aware CP/CR/CL metrics and
            populates the prompt with actual clause text.
        session_id: Optional session identifier for cost attribution.
            Passed through to the discriminator so grounding gateway calls
            share the same session ID as the review pipeline.

    Returns:
        CGReport with per-claim verdicts, provenances, and metrics.
    """
    discriminator = CitationGroundingDiscriminator(
        mode=mode,
        gateway=gateway,
        model=model,
        session_id=session_id,
    )
    return discriminator.ground_report(report, source_document, source_clauses)
