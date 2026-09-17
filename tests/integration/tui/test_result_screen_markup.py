"""Markup-safety and export-dir tests for ResultScreen (P0/T2, P1/T3, P2/T6).

P1T1: bracketed legal text must render literally (including uppercase-initial tags).
P1T2: an ``amber`` clause must carry a Textual-valid colour name (``orange``).
P1T7: exports must default to ``./review_results`` rather than ``/tmp``.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tests.integration.tui.test_result_screen import (
    _make_mock_assessment,
    _make_mock_report,
)

# ── Markup safety (P0/T2) ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_result_screen_preserves_bracketed_clause_text() -> None:
    """Legal bracket text must render literally, including uppercase-initial tags."""
    from textual.widgets import Label

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.result import ResultScreen

    assessments = [
        _make_mock_assessment(text="Confidentiality [intentionally omitted] term."),
        _make_mock_assessment(text="Notice must be sent to [Party A] only."),
    ]
    report = _make_mock_report(assessments)

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(ResultScreen(reports=[report], mode="precheck"))
        await pilot.pause()

        joined = "\n".join(str(w.render()) for w in app.screen.query(Label))
        assert "[intentionally omitted]" in joined, joined
        assert "[Party A]" in joined, joined


# ── Amber colour mapping (P1/T3) ──────────────────────────────────────


@pytest.mark.asyncio
async def test_result_screen_amber_clause_shows_valid_color_name() -> None:
    """An amber clause must not render the invalid `[amber]` tag."""
    from textual.widgets import Label, ListView

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.result import ResultScreen

    assessments = [_make_mock_assessment(color="amber", confidence=0.4, text="Amber clause")]
    report = _make_mock_report(assessments)

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(ResultScreen(reports=[report], mode="precheck"))
        await pilot.pause()

        label = app.screen.query_one("#clause-list-pane", ListView).query_one(Label)
        text = str(label.render())
        assert "[orange]" in text, text
        assert "Amber clause" in text, text
        assert "[amber]" not in text, text


# ── Export directory (P2/T6) ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_save_uses_relative_review_results_dir(tmp_path, monkeypatch) -> None:
    """TUI export must default to ./review_results, not /tmp (T6)."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.result import ResultScreen

    monkeypatch.chdir(tmp_path)
    report = _make_mock_report([_make_mock_assessment()])

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        with patch("openreview_cli.review.memo.exporter.MemoExporter") as mock_exporter_cls:
            mock_exporter = MagicMock()
            mock_exporter.export.return_value = {
                MagicMock(): Path("review_results") / "review-result.md"
            }
            mock_exporter_cls.return_value = mock_exporter

            app.push_screen(ResultScreen(reports=[report], mode="precheck"))
            await pilot.pause()

            await pilot.click("#btn-export")
            await pilot.pause()
            await pilot.click("#btn-fmt-md")
            await pilot.pause()

            label = str(app.screen.query_one("#save-file-path").render())
            assert "review_results" in label, label
            assert "/tmp" not in label, label

            await pilot.click("#btn-save")
            await pilot.pause()

            assert mock_exporter_cls.call_args.kwargs["output_dir"] == Path("review_results")
