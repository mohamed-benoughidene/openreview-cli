"""Unit tests for per-mode confidence threshold overrides in the review pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from openreview_cli.review.pipeline import ReviewStage

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def _make_category(cat_id: str) -> dict[str, Any]:
    """Build a minimal category dict for pipeline internal use."""
    return {
        "id": cat_id,
        "name": cat_id.replace("-", " ").title(),
        "description": "test",
        "preferred": {"description": "best", "exemplars": ["ex a"]},
        "acceptable": {"description": "ok", "exemplars": ["ex b"]},
        "walkaway": {"description": "bad", "exemplars": ["ex c"]},
        "default_position": "acceptable",
    }


def _make_playbook(mode: str = "precheck") -> Any:
    """Build a minimal playbook-like object."""
    from openreview_cli.review.models import (
        Category,
        Playbook,
        PlaybookMetadata,
        Position,
        PositionDef,
    )

    pref = PositionDef(description="best", exemplars=["ex a"])
    acc = PositionDef(description="ok", exemplars=["ex b"])
    walk = PositionDef(description="bad", exemplars=["ex c"])
    cat = Category(
        id="test-cat",
        name="Test Category",
        description="test",
        preferred=pref,
        acceptable=acc,
        walkaway=walk,
        default_position=Position.ACCEPTABLE,
    )
    meta = PlaybookMetadata(version="1.0.0", description="test", author="test")
    return Playbook(id="test", mode=mode, categories=[cat], metadata=meta)


class TestReviewStageThresholdResolution:
    """Verify ReviewStage resolves effective threshold from overrides."""

    def test_default_threshold_used_when_no_overrides(self) -> None:
        stage = ReviewStage(
            playbook=_make_playbook("precheck"),
            confidence_threshold=0.7,
        )
        assert stage._effective_threshold == 0.7

    def test_mode_override_takes_precedence(self) -> None:
        stage = ReviewStage(
            playbook=_make_playbook("leasecheck"),
            confidence_threshold=0.7,
            mode_threshold_overrides={"leasecheck": 0.85},
            mode="leasecheck",
        )
        assert stage._effective_threshold == 0.85

    def test_mode_override_ignores_other_modes(self) -> None:
        stage = ReviewStage(
            playbook=_make_playbook("privacycheck"),
            confidence_threshold=0.7,
            mode_threshold_overrides={"leasecheck": 0.85},
            mode="privacycheck",
        )
        assert stage._effective_threshold == 0.7  # no override for privacycheck

    def test_mode_override_empty_dict_falls_back(self) -> None:
        stage = ReviewStage(
            playbook=_make_playbook("precheck"),
            confidence_threshold=0.5,
            mode_threshold_overrides={},
            mode="precheck",
        )
        assert stage._effective_threshold == 0.5

    def test_multiple_overrides_only_current_mode_used(self) -> None:
        stage = ReviewStage(
            playbook=_make_playbook("leasecheck"),
            confidence_threshold=0.7,
            mode_threshold_overrides={
                "leasecheck": 0.9,
                "privacycheck": 0.6,
                "precheck": 0.8,
            },
            mode="leasecheck",
        )
        assert stage._effective_threshold == 0.9


class TestReviewStageReportCarriesOverrides:
    """Verify ReviewReport carries mode_threshold_overrides from the pipeline."""

    def test_report_has_mode_threshold_overrides(self) -> None:
        stage = ReviewStage(
            playbook=_make_playbook("leasecheck"),
            confidence_threshold=0.7,
            mode_threshold_overrides={"leasecheck": 0.85},
            mode="leasecheck",
        )
        # Build an empty report (assessments=[])
        result = stage._empty_report()
        report = result["review_report"]
        assert report.mode_threshold_overrides == {"leasecheck": 0.85}

    def test_report_has_none_when_no_overrides(self) -> None:
        stage = ReviewStage(
            playbook=_make_playbook("precheck"),
            confidence_threshold=0.7,
            mode="precheck",
        )
        result = stage._empty_report()
        report = result["review_report"]
        assert report.mode_threshold_overrides is None or report.mode_threshold_overrides == {}
