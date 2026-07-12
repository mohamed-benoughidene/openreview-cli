"""Integration tests for US2 — recent-reviews on Home tab (T025, T026)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from textual.widgets import Label as TLabel
from textual.widgets import ListView

# ── helpers ──


def _make_mock_review(**overrides: str | int) -> dict:
    """Build a dict matching recent-reviews row shape."""
    return {
        "id": overrides.get("id", "r-001"),
        "filename": overrides.get("filename", "test.pdf"),
        "mode": overrides.get("mode", "precheck"),
        "green_count": overrides.get("green_count", 3),
        "amber_count": overrides.get("amber_count", 1),
        "red_count": overrides.get("red_count", 0),
        "created_at": overrides.get("created_at", "2026-07-11T10:00:00"),
    }


def _make_mock_report(mode: str = "precheck") -> MagicMock:
    """Build a mock ReviewReport with one green assessment."""
    assess = MagicMock()
    assess.color = "green"
    assess.confidence = 0.95
    assess.clause_text = "Test clause"
    assess.effective_confidence = 0.95
    assess.position.value = "preferred"
    assess.reasoning = "Test reasoning"
    assess.qa_revised_rationale = None
    assess.clause_ref = None
    report = MagicMock()
    report.assessments = [assess]
    report.document.filename = "test.pdf"
    report.document.page_count = 1
    report.document.clause_count = 1
    report.document.pii_stripped = True
    report.generated_at = "2026-07-11T00:00:00"
    report.confidence_threshold = 0.7
    report.playbook_id = "test-playbook"
    report.cg_metrics = None
    report.mode = mode
    report.schema_version = "1.1.0"
    report.summary.green_count = 1
    report.summary.amber_count = 0
    report.summary.red_count = 0
    report.summary.avg_confidence = 0.95
    report.summary.avg_effective_confidence = 0.95
    return report


# ── T025 tests: Home tab recent-reviews list ──


async def test_home_tab_empty_state_no_reviews() -> None:
    """Fresh launch — empty-state message visible, list hidden."""
    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    with patch("openreview_cli.tui.domain.review.list_recent_reviews_via_tui") as mock_list:
        mock_list.return_value = []
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()

            empty = app.query_one("#empty-state", TLabel)
            recent_list = app.query_one("#recent-list", ListView)

            assert empty.display is True
            assert recent_list.display is False
            assert "No reviews yet" in empty.content


async def test_home_tab_shows_recent_reviews() -> None:
    """Seed 3 reviews — all 3 entries visible with filename, mode, date, counts."""
    from openreview_cli.tui.app import OpenReviewApp

    mock_reviews = [
        _make_mock_review(id="r-001", filename="a.pdf", created_at="2026-07-11T10:00:00"),
        _make_mock_review(id="r-002", filename="b.pdf", created_at="2026-07-10T10:00:00"),
        _make_mock_review(id="r-003", filename="c.pdf", created_at="2026-07-09T10:00:00"),
    ]

    app = OpenReviewApp()
    with patch("openreview_cli.tui.domain.review.list_recent_reviews_via_tui") as mock_list:
        mock_list.return_value = mock_reviews
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()

            recent_list = app.query_one("#recent-list", ListView)
            assert recent_list.display is True
            assert len(recent_list.children) == 3

            all_text = " ".join(child.query_one(TLabel).content for child in recent_list.children)
            assert "a.pdf" in all_text
            assert "b.pdf" in all_text
            assert "c.pdf" in all_text
            assert "precheck" in all_text
            assert "3g/1a/0r" in all_text


async def test_home_tab_description_bar() -> None:
    """Focus entry — description bar shows mode, date, color counts."""
    from openreview_cli.tui.app import OpenReviewApp

    mock_reviews = [_make_mock_review(id="r-001")]

    app = OpenReviewApp()
    with patch("openreview_cli.tui.domain.review.list_recent_reviews_via_tui") as mock_list:
        mock_list.return_value = mock_reviews
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()

            recent_list = app.query_one("#recent-list", ListView)
            recent_list.focus()
            await pilot.pause()

            from textual.widgets import Static as TStatic

            desc_bar = app.query_one("#desc-bar", TStatic)
            assert "precheck" in desc_bar.content
            assert "2026-07-11" in desc_bar.content
            assert "3g/1a/0r" in desc_bar.content


async def test_recent_reviews_order_descending_by_date() -> None:
    """Seed reviews with different dates — most recent first."""
    from openreview_cli.tui.app import OpenReviewApp

    mock_reviews = [
        _make_mock_review(id="r-new", created_at="2026-07-11T10:00:00", filename="new.pdf"),
        _make_mock_review(id="r-mid", created_at="2026-06-15T10:00:00", filename="mid.pdf"),
        _make_mock_review(id="r-old", created_at="2026-01-01T10:00:00", filename="old.pdf"),
    ]

    app = OpenReviewApp()
    with patch("openreview_cli.tui.domain.review.list_recent_reviews_via_tui") as mock_list:
        mock_list.return_value = mock_reviews
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()

            recent_list = app.query_one("#recent-list", ListView)
            items = list(recent_list.children)
            assert len(items) == 3

            texts = [item.query_one(TLabel).content for item in items]
            # Most recent should be first
            assert texts[0].startswith("new.pdf"), f"Expected new.pdf first, got: {texts[0]}"
            assert texts[1].startswith("mid.pdf")
            assert texts[2].startswith("old.pdf")


# ── T026 test: Enter opens result screen ──


@pytest.mark.slow
async def test_recent_reviews_enter_loads_report() -> None:
    """Focus entry, press Enter, mock load_review_report, assert ResultScreen pushed."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.result import ResultScreen

    mock_reviews = [_make_mock_review(id="r-001")]
    mock_report = _make_mock_report()

    app = OpenReviewApp()
    with (
        patch("openreview_cli.tui.domain.review.list_recent_reviews_via_tui") as mock_list,
        patch("openreview_cli.tui.domain.review.load_review_report_via_tui") as mock_load,
    ):
        mock_list.return_value = mock_reviews
        mock_load.return_value = mock_report
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()

            recent_list = app.query_one("#recent-list", ListView)
            recent_list.focus()
            await pilot.pause()

            # Press Enter on the focused item
            await pilot.press("enter")
            await pilot.pause()

            # ResultScreen should be on screen stack
            result = None
            for s in app._screen_stack:
                if isinstance(s, ResultScreen):
                    result = s
                    break
            assert result is not None, "ResultScreen should be pushed after Enter"
            assert result._mode == "precheck"
            assert len(result._reports) == 1
