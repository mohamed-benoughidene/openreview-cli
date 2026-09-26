"""Startup splash (opt-in): the first painted frame is the loading screen.

The splash and its deferred startup I/O are gated behind
``OpenReviewApp(show_splash=True)``. ``OpenReviewApp()`` (the default) must be
byte-for-byte the baseline behaviour: no splash widget, inline startup I/O.
"""

from __future__ import annotations

from unittest.mock import patch

from textual.pilot import Pilot
from textual.widgets import Footer, Static, TabbedContent, TabPane

from openreview_cli import __version__
from openreview_cli.tui.app import OpenReviewApp
from openreview_cli.tui.screens.splash import StartupSplash
from openreview_cli.tui.tabs.settings import SettingsTab


async def _wait_for_splash_lift(app: OpenReviewApp, pilot: Pilot) -> None:
    """Wait wall-clock for the splash's minimum-on-screen timer to fire."""
    for _ in range(40):
        if not app.query(StartupSplash):
            return
        await pilot.pause(0.05)
    raise AssertionError("startup splash did not lift")


async def test_splash_paints_first_then_lifts() -> None:
    app = OpenReviewApp(show_splash=True)
    async with app.run_test(size=(120, 40)) as pilot:
        # First frame: the splash covers the (already mounted) UI.
        splash = app.query_one(StartupSplash)
        assert "openreview" in str(app.query_one("#splash-title", Static).render())
        assert __version__ in str(app.query_one("#splash-version", Static).render())
        assert app.screen.get_widget_at(1, 1)[0] is app.query_one(StartupSplash)
        assert app.query_one("#tabs", TabbedContent) is not None
        # Startup I/O has not run yet: the status bar still shows the compose
        # placeholder ("Privacy: —") that _finish_startup later replaces. This
        # proves the splash is painted before the deferred startup work.
        assert "Privacy: —" in str(app.query_one("#status-privacy", Static).render())

        # Startup completes and the splash lifts.
        await _wait_for_splash_lift(app, pilot)

        assert not app.query(StartupSplash)
        assert app.query_one("#tabs", TabbedContent) is not None
        assert len(app.query(TabPane)) == 7
        assert app.query_one("#status-bar") is not None
        assert app.query_one(Footer) is not None


async def test_default_app_has_no_splash() -> None:
    """The default app (no flag) has no splash and its UI is intact."""
    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)):
        assert not app.query(StartupSplash)
        assert app.query_one("#tabs", TabbedContent) is not None
        assert len(app.query(TabPane)) == 7
        # No splash means startup I/O ran inline: the compose placeholder has
        # already been replaced, locking the baseline to synchronous startup.
        assert "Privacy: —" not in str(app.query_one("#status-privacy", Static).render())


async def test_splash_number_key_at_yield() -> None:
    """A number-key binding lands while the splash is still up."""
    app = OpenReviewApp(show_splash=True)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("4")
        await pilot.pause()
        assert app.query_one("#tabs", TabbedContent).active == "playbooks"


async def test_all_tab_loads_run_behind_the_splash() -> None:
    """Every tab's deferred load is held until the splash lifts, then runs."""
    with (
        patch(
            "openreview_cli.tui.domain.review.list_recent_reviews_via_tui",
            return_value=[],
        ) as m_reviews,
        patch(
            "openreview_cli.tui.domain.clients.list_clients_via_tui",
            return_value=[],
        ) as m_clients,
        patch(
            "openreview_cli.tui.domain.playbooks.list_playbooks_via_tui",
            return_value=[],
        ) as m_playbooks,
        patch(
            "openreview_cli.tui.domain.prompts.list_prompts_via_tui",
            return_value=[],
        ) as m_prompts,
        patch("openreview_cli.tui.tabs.settings.get_slot_configs", return_value={}) as m_slots,
    ):
        app = OpenReviewApp(show_splash=True)
        async with app.run_test(size=(120, 40)) as pilot:
            # At the run_test yield the splash is up and none of the deferred
            # tab loads (nor the settings gateway render) has run yet. The
            # playbooks fetch is a background worker started in on_mount, so it
            # is deliberately not asserted here (it could already be running).
            assert app.query(StartupSplash)
            assert not m_reviews.called
            assert not m_clients.called
            assert not m_prompts.called
            assert not m_slots.called

            await _wait_for_splash_lift(app, pilot)
            await app.workers.wait_for_complete()

            assert not app.query(StartupSplash)
            assert m_reviews.called
            assert m_clients.called
            assert m_playbooks.called
            assert m_prompts.called
            assert m_slots.called


async def test_splash_settings_section_not_clobbered() -> None:
    """A section chosen before the deferred init runs is not reset to gateway."""
    app = OpenReviewApp(show_splash=True)
    async with app.run_test(size=(120, 40)) as pilot:
        tab = app.query_one(SettingsTab)
        # The deferred initial render is still pending, so the current section
        # is the default gateway — otherwise the final assert would be vacuous.
        assert tab._current_section == "gateway"
        tab.select_section("about")

        await _wait_for_splash_lift(app, pilot)

        assert "Accessibility" in str(tab.query_one("#section-content-display", Static).render())
