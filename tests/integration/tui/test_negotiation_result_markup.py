"""Integration tests for ``NegotiationResultScreen``.

P1T3 (P0/T2): memo text is rendered with ``markup=False`` so bracketed legal
text such as ``[Party A]`` survives Textual's markup parser.
P1T7 (P2/T6): exports land in ``./review_results/`` rather than ``/tmp``.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# ── P1T3: markup safety ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_negotiation_result_preserves_bracketed_memo_text() -> None:
    """Rendered memo text must keep literal brackets such as [Party A]."""
    from textual.widgets import Label

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.negotiation_result import NegotiationResultScreen

    report = MagicMock()
    report.disclaimer = "Advisory only."
    memo = "Clause 3 [intentionally omitted] remains binding; see [Party A]."

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        with patch("openreview_cli.negotiation.report.format_memo", return_value=memo):
            app.push_screen(NegotiationResultScreen(report=report))
            await pilot.pause()

            labels = [str(w.render()) for w in app.screen.query(Label)]
            assert any("[intentionally omitted]" in text for text in labels), labels
            assert any("[Party A]" in text for text in labels), labels


# ── P1T7: export directory ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_negotiation_export_writes_to_review_results(tmp_path, monkeypatch) -> None:
    """Negotiation export must land in ./review_results, not /tmp (T6)."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.negotiation_result import NegotiationResultScreen

    monkeypatch.chdir(tmp_path)
    report = MagicMock()
    report.disclaimer = "Advisory only."

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        with patch("openreview_cli.negotiation.report.format_memo", return_value="memo [x]"):
            app.push_screen(NegotiationResultScreen(report=report))
            await pilot.pause()
            await pilot.click("#btn-export")
            await pilot.pause()

    out = tmp_path / "review_results" / "negotiation-result.md"
    assert out.exists(), out
    assert out.read_text(encoding="utf-8") == "memo [x]"
