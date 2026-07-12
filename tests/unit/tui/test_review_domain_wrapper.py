"""Unit tests for tui.domain.review wrapper (T017a).

Tests that PII stripping is enabled by default when invoked from the TUI,
and that the disable_pii flag is properly passed through.
"""

from __future__ import annotations

from unittest.mock import patch


class TestReviewDomainWrapper:
    """T017a: PII default behavior in TUI review wrapper."""

    def test_review_wrapper_enables_pii_by_default(self) -> None:
        """PII stripping enabled by default: no_pii=False."""
        from openreview_cli.tui.domain.review import run_review_via_tui

        with patch("openreview_cli.tui.domain.review.run_review") as mock_run:
            mock_run.return_value = []
            run_review_via_tui(paths=["test.pdf"], mode="precheck")

        mock_run.assert_called_once()
        _call_kwargs = mock_run.call_args.kwargs
        assert _call_kwargs.get("no_pii") is False, (
            "PII should be enabled by default (no_pii=False)"
        )

    def test_review_wrapper_respects_no_pii_flag(self) -> None:
        """disable_pii=True sets no_pii=True."""
        from openreview_cli.tui.domain.review import run_review_via_tui

        with patch("openreview_cli.tui.domain.review.run_review") as mock_run:
            mock_run.return_value = []
            run_review_via_tui(paths=["test.pdf"], mode="precheck", disable_pii=True)

        mock_run.assert_called_once()
        _call_kwargs = mock_run.call_args.kwargs
        assert _call_kwargs.get("no_pii") is True, "disable_pii=True should set no_pii=True"

    def test_review_wrapper_passes_through_params(self) -> None:
        """All parameters passed through to run_review correctly."""
        from openreview_cli.tui.domain.review import run_review_via_tui

        with patch("openreview_cli.tui.domain.review.run_review") as mock_run:
            mock_run.return_value = []
            run_review_via_tui(
                paths=["doc.pdf"],
                mode="hirecheck",
                playbook_path="/tmp/custom.yaml",
                extraction_model="reasoning",
                qa_model="reasoning",
                confidence_threshold=0.8,
                verbose=True,
            )

        mock_run.assert_called_once_with(
            paths=["doc.pdf"],
            playbook_path="/tmp/custom.yaml",
            playbook_id=None,
            extraction_model="reasoning",
            qa_model="reasoning",
            no_pii=False,
            verbose=True,
            confidence_threshold=0.8,
            mode="hirecheck",
        )
