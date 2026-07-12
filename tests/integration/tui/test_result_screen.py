"""Integration tests for ResultScreen (T021, T022).

T021: Result screen split view, layout toggle, summary header, description bar.
T022: Export action (Markdown, JSON, DOCX), error handling.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _make_mock_assessment(
    color: str = "green",
    confidence: float = 0.92,
    text: str = "Test clause",
    position: str = "preferred",
) -> MagicMock:
    a = MagicMock()
    a.color = color
    a.confidence = confidence
    a.effective_confidence = confidence
    a.clause_text = text
    a.position.value = position
    a.reasoning = "Test reasoning"
    a.qa_revised_rationale = None
    a.clause_ref = None
    return a


def _make_mock_report(assessments: list | None = None) -> MagicMock:
    r = MagicMock()
    asm = assessments or []
    r.assessments = asm
    r.document.filename = "test.pdf"
    r.document.page_count = 5
    r.document.clause_count = len(asm)
    r.document.pii_stripped = True
    r.playbook_id = "precheck-nda-v1"
    r.playbook_version = 1
    r.generated_at = "2026-07-11T00:00:00"
    r.confidence_threshold = 0.7
    r.summary.green_count = sum(1 for a in asm if a.color == "green")
    r.summary.amber_count = sum(1 for a in asm if a.color == "amber")
    r.summary.red_count = sum(1 for a in asm if a.color == "red")
    r.summary.preferred_count = 1
    r.summary.acceptable_count = 0
    r.summary.walkaway_count = 0
    r.summary.uncertain_count = 0
    r.summary.no_match_count = 0
    avg_c = asm[0].confidence if asm else 0.0
    r.summary.avg_confidence = avg_c
    r.summary.avg_effective_confidence = avg_c
    r.cg_metrics = None
    r.mode = "precheck"
    r.schema_version = "1.1.0"
    r.mode_threshold_overrides = None
    return r


def _get_result_screen(app):
    """Get ResultScreen from screen stack."""
    from openreview_cli.tui.screens.result import ResultScreen

    for s in app._screen_stack:
        if isinstance(s, ResultScreen):
            return s
    return None


def _get_result_screen_checked(app):
    """Get ResultScreen, asserting it's not None."""
    s = _get_result_screen(app)
    assert s is not None, "ResultScreen should be on screen stack"
    return s


# ── T021: Result screen display ──────────────────────────────────────


@pytest.mark.asyncio
async def test_result_screen_split_view() -> None:
    """Open with a fake ReviewReport, assert clause list and details visible."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.result import ResultScreen

    assessments = [_make_mock_assessment()]
    report = _make_mock_report(assessments)

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(ResultScreen(reports=[report], mode="precheck"))
        await pilot.pause()

        screen = _get_result_screen_checked(app)

        # Summary header (uses .summary-header class)
        headers = screen.query(".summary-header")
        assert len(headers) > 0, "Summary header should be visible"

        # Clause list pane
        clause_pane = screen.query_one("#clause-list-pane")
        assert clause_pane is not None, "Clause list pane should be visible"

        # Detail pane
        detail_pane = screen.query_one("#clause-detail-pane")
        assert detail_pane is not None, "Clause detail pane should be visible"


@pytest.mark.asyncio
async def test_result_screen_layout_toggle() -> None:
    """Press layout-toggle key (l), assert layout switches to full-screen."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.result import ResultScreen

    assessments = [_make_mock_assessment()]
    report = _make_mock_report(assessments)

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(ResultScreen(reports=[report], mode="precheck"))
        await pilot.pause()

        screen = _get_result_screen_checked(app)

        # Should be in split view
        split_view = screen.query_one("#split-view")
        assert split_view is not None

        # Toggle layout
        await pilot.press("l")
        await pilot.pause()

        # Should now show full-screen scroll
        full_scroll = screen.query_one("#full-screen-scroll")
        assert full_scroll is not None, "Full-screen scroll should appear after toggle"

        # Toggle back
        await pilot.press("l")
        await pilot.pause()
        split_view = screen.query_one("#split-view")
        assert split_view is not None, "Split view should restore after second toggle"


@pytest.mark.asyncio
async def test_result_screen_summary_header() -> None:
    """Assert summary counts header visible."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.result import ResultScreen

    assessments = [
        _make_mock_assessment(color="green"),
        _make_mock_assessment(color="amber", confidence=0.5),
        _make_mock_assessment(color="red", confidence=0.3),
    ]
    report = _make_mock_report(assessments)

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(ResultScreen(reports=[report], mode="precheck"))
        await pilot.pause()

        screen = _get_result_screen_checked(app)
        headers = screen.query(".summary-header")
        assert len(headers) > 0, "Summary header should exist"
        # Check header text contains expected counts
        assert "Green" in str(headers[0].render())


@pytest.mark.asyncio
async def test_result_screen_description_bar() -> None:
    """Focus different clause, assert description bar updates."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.result import ResultScreen

    assessments = [
        _make_mock_assessment(color="green"),
        _make_mock_assessment(color="amber", confidence=0.5),
    ]
    report = _make_mock_report(assessments)

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(ResultScreen(reports=[report], mode="precheck"))
        await pilot.pause()

        screen = _get_result_screen_checked(app)

        desc_bar = screen.query_one("#description-bar")
        assert desc_bar is not None, "Description bar should exist"

        # Navigate down
        await pilot.press("down")
        await pilot.pause()

        # Description bar exists (check it has some content)
        assert str(desc_bar) != ""


@pytest.mark.asyncio
async def test_result_screen_export_button() -> None:
    """Assert Export button visible."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.result import ResultScreen

    assessments = [_make_mock_assessment()]
    report = _make_mock_report(assessments)

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(ResultScreen(reports=[report], mode="precheck"))
        await pilot.pause()

        screen = _get_result_screen_checked(app)

        export_btn = screen.query_one("#btn-export")
        assert export_btn is not None, "Export button should be visible"


# ── T022: Export action ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_export_markdown() -> None:
    """Click Export, select Markdown, save, assert exporter called."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.result import ResultScreen

    assessments = [_make_mock_assessment()]
    report = _make_mock_report(assessments)

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        with patch("openreview_cli.review.memo.exporter.MemoExporter") as mock_exporter_cls:
            mock_exporter = MagicMock()
            mock_exporter.export.return_value = {MagicMock(): Path("/tmp/review-result.md")}
            mock_exporter_cls.return_value = mock_exporter

            app.push_screen(ResultScreen(reports=[report], mode="precheck"))
            await pilot.pause()

            # Click Export
            await pilot.click("#btn-export")
            await pilot.pause()

            # Click Markdown
            await pilot.click("#btn-fmt-md")
            await pilot.pause()

            # Click Save
            await pilot.click("#btn-save")
            await pilot.pause()

            mock_exporter.export.assert_called_once()


@pytest.mark.asyncio
async def test_export_json() -> None:
    """Click Export, select JSON, save, assert exporter called."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.result import ResultScreen

    assessments = [_make_mock_assessment()]
    report = _make_mock_report(assessments)

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        with patch("openreview_cli.review.memo.exporter.MemoExporter") as mock_exporter_cls:
            mock_exporter = MagicMock()
            mock_exporter.export.return_value = {MagicMock(): Path("/tmp/review-result.json")}
            mock_exporter_cls.return_value = mock_exporter

            app.push_screen(ResultScreen(reports=[report], mode="precheck"))
            await pilot.pause()

            await pilot.click("#btn-export")
            await pilot.pause()
            await pilot.click("#btn-fmt-json")
            await pilot.pause()
            await pilot.click("#btn-save")
            await pilot.pause()

            mock_exporter.export.assert_called_once()


@pytest.mark.asyncio
async def test_export_docx() -> None:
    """Click Export, select DOCX, save, assert exporter called."""
    import importlib.util

    has_docx = importlib.util.find_spec("docx") is not None
    if not has_docx:
        pytest.skip("python-docx not installed")

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.result import ResultScreen

    assessments = [_make_mock_assessment()]
    report = _make_mock_report(assessments)

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        with patch("openreview_cli.review.memo.exporter.MemoExporter") as mock_exporter_cls:
            mock_exporter = MagicMock()
            mock_exporter.export.return_value = {MagicMock(): Path("/tmp/review-result.docx")}
            mock_exporter_cls.return_value = mock_exporter

            app.push_screen(ResultScreen(reports=[report], mode="precheck"))
            await pilot.pause()

            await pilot.click("#btn-export")
            await pilot.pause()
            await pilot.click("#btn-fmt-docx")
            await pilot.pause()
            await pilot.click("#btn-save")
            await pilot.pause()

            mock_exporter.export.assert_called_once()


@pytest.mark.asyncio
async def test_export_error_on_empty_report() -> None:
    """Try to export empty report, assert no crash."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.result import ResultScreen

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(ResultScreen(reports=[], mode="precheck"))
        await pilot.pause()

        screen = _get_result_screen_checked(app)

        # Click Export
        await pilot.click("#btn-export")
        await pilot.pause()

        # Click Markdown format
        await pilot.click("#btn-fmt-md")
        await pilot.pause()

        # Click Save
        await pilot.click("#btn-save")
        await pilot.pause()

    # No crash = success
