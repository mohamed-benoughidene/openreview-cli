"""Three-color output with confidence scores."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from openreview_cli.review.models import ClauseAssessment


class AssessmentColor(StrEnum):
    green = "green"
    amber = "amber"
    red = "red"


class AmberReason(StrEnum):
    low_confidence = "low_confidence"
    qa_disagreement = "qa_disagreement"
    qa_uncertain = "qa_uncertain"
    error = "error"
    grounding_failure = "grounding_failure"
    grounding_uncertain = "grounding_uncertain"


def effective_confidence(
    extraction_confidence: float | None = None,
    qa_confidence: float | None = None,
    grounding_confidence: float | None = None,
) -> float:
    return min(
        extraction_confidence if extraction_confidence is not None else 1.0,
        qa_confidence if qa_confidence is not None else 1.0,
        grounding_confidence if grounding_confidence is not None else 1.0,
    )


def _collect_triggers(a: Any, eff_conf: float, threshold: float) -> list[AmberReason]:
    triggers: list[AmberReason] = []
    if a.error is not None:
        triggers.append(AmberReason.error)
    if eff_conf < threshold:
        triggers.append(AmberReason.low_confidence)
    if a.qa_verdict == "disagree":
        triggers.append(AmberReason.qa_disagreement)
    if a.qa_verdict == "uncertain":
        triggers.append(AmberReason.qa_uncertain)
    if a.grounding_verdict is not None:
        if a.grounding_verdict == "ungrounded":
            triggers.append(AmberReason.grounding_failure)
        if a.grounding_verdict == "uncertain":
            triggers.append(AmberReason.grounding_uncertain)
    return triggers


def assign_colors(assessments: list[ClauseAssessment], threshold: float = 0.7) -> None:
    for a in assessments:
        eff_conf = effective_confidence(
            extraction_confidence=a.confidence,
            grounding_confidence=a.grounding_confidence,
        )
        triggers = _collect_triggers(a, eff_conf, threshold)

        if triggers:
            color = AssessmentColor.amber
        elif a.position == "walkaway" and eff_conf >= threshold:
            color = AssessmentColor.red
        elif a.position in ("preferred", "acceptable") and eff_conf >= threshold:
            color = AssessmentColor.green
        else:
            color = AssessmentColor.amber

        a.color = color
        a.effective_confidence = eff_conf
        a.amber_reasons = triggers
        a.is_amber = color == AssessmentColor.amber
