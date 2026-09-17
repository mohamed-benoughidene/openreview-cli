"""Pre-flight egress-review modal gates the wizard's Run review (Phase 4).

The modal must not merely appear — the wizard may only switch to
``ProgressScreen`` after the user confirms.  ``switch_screen`` is spied on (and
``ProgressScreen`` stubbed to a bare ``Screen``) so these assertions do not
depend on how long the review worker happens to take to finish.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from textual.screen import Screen


class _StubProgressScreen(Screen[None]):
    """Stand-in for ``ProgressScreen`` that never starts a review worker."""

    def __init__(self, **options: object) -> None:
        super().__init__()
        self.options = options


async def _open_wizard(app, pilot):
    """Push a ReviewWizard on top of the app and return it."""
    from openreview_cli.tui.screens.review_wizard import ReviewWizard

    wizard = ReviewWizard()
    app.push_screen(wizard)
    await pilot.pause()
    return wizard


def _select_for_review(wizard) -> None:
    """Simulate reaching step 4 with a document/mode/playbook selection."""
    wizard._selected_file = "doc.pdf"
    wizard._selected_mode = "precheck"
    wizard._selected_playbook = "default"


# ── Confirmation path ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_egress_modal_blocks_until_confirmed() -> None:
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.domain.egress import EgressSummary
    from openreview_cli.tui.screens.egress_review import EgressReviewModal
    from openreview_cli.tui.screens.progress import ProgressScreen

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        wizard = await _open_wizard(app, pilot)
        _select_for_review(wizard)

        with (
            patch("openreview_cli.tui.domain.egress.build_egress_summary") as builder,
            patch.object(app, "switch_screen") as mock_switch,
        ):
            builder.return_value = EgressSummary(
                privacy_tier="maximum",
                pii_stripped=True,
                destinations=("ollama/qwen3:8b",),
                cloud_warning=False,
            )
            await wizard._run_review()
            await pilot.pause()

            # The modal is shown and nothing has switched yet.
            assert any(isinstance(s, EgressReviewModal) for s in app._screen_stack)
            assert not mock_switch.called

            # Confirm → proceeds to the progress screen.
            await pilot.press("c")
            await pilot.pause()

            assert mock_switch.call_count == 1
            switched = mock_switch.call_args.args[0]
            assert isinstance(switched, ProgressScreen)
            assert switched._paths == ["doc.pdf"]
            assert switched._mode == "precheck"
            assert switched._playbook_id is None
            assert switched._disable_pii is False

            # The modal was popped before the wizard switched screens.
            assert not any(isinstance(s, EgressReviewModal) for s in app._screen_stack)
            assert wizard is app.screen


@pytest.mark.asyncio
async def test_egress_continue_button_switches_to_progress() -> None:
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.review_wizard import ReviewWizard

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        wizard = await _open_wizard(app, pilot)
        _select_for_review(wizard)

        with patch("openreview_cli.tui.screens.progress.ProgressScreen", _StubProgressScreen):
            await wizard._run_review()
            await pilot.pause()

            await pilot.click("#btn-egress-continue")
            await pilot.pause()

            # Real switch_screen ran: the wizard was replaced by the new screen.
            assert not any(isinstance(s, ReviewWizard) for s in app._screen_stack)
            assert isinstance(app.screen, _StubProgressScreen)
            assert app.screen.options["paths"] == ["doc.pdf"]
            assert app.screen.options["mode"] == "precheck"


# ── Cancellation path ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_egress_modal_cancel_stays_on_wizard() -> None:
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.egress_review import EgressReviewModal
    from openreview_cli.tui.screens.progress import ProgressScreen
    from openreview_cli.tui.screens.review_wizard import ReviewWizard

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        wizard = await _open_wizard(app, pilot)
        _select_for_review(wizard)

        await wizard._run_review()
        await pilot.pause()

        await pilot.press("escape")
        await pilot.pause()

        assert not any(isinstance(s, EgressReviewModal) for s in app._screen_stack)
        assert any(isinstance(s, ReviewWizard) for s in app._screen_stack)
        assert not any(isinstance(s, ProgressScreen) for s in app._screen_stack)
        assert wizard is app.screen


@pytest.mark.asyncio
async def test_egress_cancel_button_stays_on_wizard() -> None:
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.egress_review import EgressReviewModal
    from openreview_cli.tui.screens.progress import ProgressScreen
    from openreview_cli.tui.screens.review_wizard import ReviewWizard

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        wizard = await _open_wizard(app, pilot)
        _select_for_review(wizard)

        await wizard._run_review()
        await pilot.pause()

        await pilot.click("#btn-egress-cancel")
        await pilot.pause()

        assert not any(isinstance(s, EgressReviewModal) for s in app._screen_stack)
        assert any(isinstance(s, ReviewWizard) for s in app._screen_stack)
        assert not any(isinstance(s, ProgressScreen) for s in app._screen_stack)
        assert wizard is app.screen


# ── Content ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_egress_modal_renders_privacy_summary() -> None:
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.domain.egress import EgressSummary
    from openreview_cli.tui.screens.egress_review import EgressReviewModal

    summary = EgressSummary(
        privacy_tier="balanced",
        pii_stripped=True,
        destinations=("openai/gpt-4o-mini", "ollama/qwen3:8b"),
        cloud_warning=False,
    )

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(EgressReviewModal(summary))
        await pilot.pause()

        text = str(app.screen.query_one("#egress-body").render())
        assert "Privacy tier: balanced" in text
        assert "PII stripped before egress: Yes" in text
        assert "openai/gpt-4o-mini" in text
        assert "ollama/qwen3:8b" in text


@pytest.mark.asyncio
async def test_egress_modal_renders_bracketed_text_literally() -> None:
    """Summary lines must render with ``markup=False`` (Phase 1 / P0 rule)."""
    from textual.widgets import Label

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.domain.egress import EgressSummary
    from openreview_cli.tui.screens.egress_review import EgressReviewModal

    summary = EgressSummary(
        privacy_tier="maximum",
        pii_stripped=True,
        destinations=("[Party A]/qwen3:8b",),
        cloud_warning=False,
    )

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(EgressReviewModal(summary))
        await pilot.pause()

        label = app.screen.query_one("#egress-body", Label)
        assert label._render_markup is False
        text = str(label.render())
        assert "[Party A]" in text, text
