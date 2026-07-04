"""Unit tests for run_review() public API."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

from openreview_cli.review import run_review


class TestRunReviewPublicAPI:
    """Tests for the run_review() public API surface."""

    def test_accepts_kwargs(self) -> None:
        """run_review should accept all keyword arguments without error (signature check)."""
        import inspect

        sig = inspect.signature(run_review)
        params = {p.name for p in sig.parameters.values()}
        for expected in (
            "paths",
            "playbook_path",
            "extraction_model",
            "qa_model",
            "no_pii",
            "verbose",
        ):
            assert expected in params, f"Missing parameter: {expected}"

    def test_returns_list_of_reports(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """run_review returns a list of ReviewReport objects."""

        class MockDoc:
            page_count = 0

        # Mock document parsing to return (doc, empty clauses)
        monkeypatch.setattr("openreview_cli.review._parse_clauses", lambda p: (MockDoc(), []))

        # Patch load_bundled to return a valid playbook with a category
        from openreview_cli.review.models import (
            Category,
            Playbook,
            PlaybookMetadata,
            Position,
            PositionDef,
        )

        def mock_bundled() -> Playbook:
            fav = PositionDef(description="a", exemplars=["a"])
            neu = PositionDef(description="b", exemplars=["b"])
            unfav = PositionDef(description="c", exemplars=["c"])
            cat = Category(
                id="test-cat",
                name="Test",
                description="test",
                preferred=fav,
                acceptable=neu,
                walkaway=unfav,
                default_position=Position.ACCEPTABLE,
            )
            return Playbook(
                id="test",
                mode="precheck",
                categories=[cat],
                metadata=PlaybookMetadata(version="1.0.0", description="t", author="t"),
            )

        monkeypatch.setattr("openreview_cli.review.load_bundled", mock_bundled)

        reports = run_review(paths=["test.docx"])
        assert isinstance(reports, list)
