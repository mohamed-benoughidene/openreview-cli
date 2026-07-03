"""Paired color assignment — three-color status per paired assessment.

Maps each ``PairedAssessment`` to Green/Amber/Red following spec FR-4:

- **Amber triggers** (any applies → Amber):
  - Divergence confidence < threshold
  - QA verdict != agree on either side
  - Extraction confidence < threshold on either side
  - Divergence is uncertain
- **Red**: Divergence detected, confident (≥ threshold), no Amber triggers
- **Green**: No divergence, confident (≥ threshold), no Amber triggers

Pure function — mutates ``.color`` in place, returns the same list.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from openreview_cli.review.colors import AssessmentColor

if TYPE_CHECKING:
    from openreview_cli.bilateral.models import PairedAssessment
    from openreview_cli.review.models import QAVerdict


def assign_paired_colors(
    assessments: list[PairedAssessment],
    confidence_threshold: float = 0.7,
) -> list[PairedAssessment]:
    """Assign three-color status to every paired assessment.

    Mutates ``assessment.color`` on each item in place.

    Parameters
    ----------
    assessments : list[PairedAssessment]
        The paired assessments to color.
    confidence_threshold : float
        Confidence boundary for Amber (default 0.7).

    Returns
    -------
    list[PairedAssessment]
        The same list (mutated in place) for chaining.
    """
    for pa in assessments:
        pa.color = _assign_single(pa, confidence_threshold)
    return assessments


def _assign_single(pa: PairedAssessment, threshold: float) -> AssessmentColor:
    """Determine color for a single PairedAssessment."""
    # Check all Amber triggers in a single condition
    if (
        pa.confidence < threshold
        or pa.divergence.value == "uncertain"
        or _qa_is_not_agree(pa.party_a_assessment.qa_verdict)
        or _qa_is_not_agree(pa.party_b_assessment.qa_verdict)
        or pa.party_a_assessment.confidence < threshold
        or pa.party_b_assessment.confidence < threshold
    ):
        return AssessmentColor.amber

    # Red: divergence detected with confidence
    if pa.divergence.value == "divergent":
        return AssessmentColor.red

    # Otherwise: no divergence, confident
    return AssessmentColor.green


def _qa_is_not_agree(verdict: QAVerdict) -> bool:
    """Check if a QA verdict is anything other than agree."""
    return verdict.value != "agree"
