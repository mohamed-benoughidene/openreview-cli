"""Integration tests for the reusable :class:`LoadingState` widget (T1).

The widget is the per-tab loading surface: a centered spinner plus a fixed
muted message.  A tab shows it with ``begin(content)`` while its fetch is in
flight and hides it with ``end(content)`` once the fetch lands.
"""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import LoadingIndicator, Static

from openreview_cli.tui.loading import LoadingState


class _LoadingApp(App[None]):
    """Minimal host app that mounts a single LoadingState."""

    def compose(self) -> ComposeResult:
        yield LoadingState(id="tab-loading")


class _ContentApp(App[None]):
    """Host app with a content widget plus a LoadingState (for ``begin``/``end``)."""

    def compose(self) -> ComposeResult:
        yield Static("content body", id="content-body")
        yield LoadingState(id="tab-loading")


async def test_loading_state_shows_indicator_and_message() -> None:
    """Mounted visible, with one LoadingIndicator and the fixed message."""
    app = _LoadingApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()

        state = app.query_one(LoadingState)
        assert state.display is True
        assert len(state.query(LoadingIndicator)) == 1

        message = state.query_one(".loading-message", Static)
        assert message.content == "Loading …"


async def test_loading_state_spinner_is_actually_painted() -> None:
    """The spinner really paints: non-zero region and the message on screen.

    Regression guard for the auto-width sizing bug where the inner Vertical was
    ``width: auto`` while its children asked for ``width: 100%`` of that parent
    — circular, resolved to width 0, and nothing rendered.
    """
    app = _LoadingApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()

        state = app.query_one(LoadingState)
        indicator = state.query_one(LoadingIndicator)
        assert indicator.region.width > 0
        assert indicator.region.height > 0

        assert "Loading" in app.export_screenshot()


async def test_loading_state_display_toggle() -> None:
    """The owning tab can hide and re-show the widget via ``display``."""
    app = _LoadingApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()

        state = app.query_one(LoadingState)
        assert state.display is True

        state.display = False
        await pilot.pause()
        assert state.display is False

        state.display = True
        await pilot.pause()
        assert state.display is True


async def test_loading_state_begin_and_end_toggle_content() -> None:
    """``begin`` shows the spinner and hides content; ``end`` reverses both."""
    app = _ContentApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()

        state = app.query_one(LoadingState)
        content = app.query_one("#content-body", Static)

        # Start from a loaded state, then begin a new in-flight load.
        state.end(content)
        state.begin(content)
        await pilot.pause()
        assert state.display is True
        assert content.display is False

        state.end(content)
        await pilot.pause()
        assert state.display is False
        assert content.display is True
