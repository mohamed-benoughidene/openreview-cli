"""Integration tests for ConfirmModal (T022)."""

from __future__ import annotations


async def test_confirm_modal_yes_returns_true() -> None:
    """Pressing Yes dismisses with True."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.confirm import ConfirmModal

    app = OpenReviewApp()
    results: list[bool] = []

    def on_result(r: bool) -> None:
        results.append(r)

    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(ConfirmModal("Test", "Confirm?"), on_result)
        await pilot.pause()
        await pilot.click("#yes")
        await pilot.pause()

    assert results == [True]


async def test_confirm_modal_no_returns_false() -> None:
    """Pressing No dismisses with False."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.confirm import ConfirmModal

    app = OpenReviewApp()
    results: list[bool] = []

    def on_result(r: bool) -> None:
        results.append(r)

    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(ConfirmModal("Test", "Confirm?"), on_result)
        await pilot.pause()
        await pilot.click("#no")
        await pilot.pause()

    assert results == [False]


async def test_confirm_modal_escape_returns_false() -> None:
    """Pressing Escape dismisses with False."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.confirm import ConfirmModal

    app = OpenReviewApp()
    results: list[bool] = []

    def on_result(r: bool) -> None:
        results.append(r)

    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(ConfirmModal("Test", "Confirm?"), on_result)
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

    assert results == [False]


async def test_danger_modal_focuses_no_and_enter_returns_false() -> None:
    """A destructive prompt focuses No, so a stray Enter cancels, never confirms."""
    from textual.widgets import Button

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.confirm import ConfirmModal

    app = OpenReviewApp()
    results: list[bool] = []

    def on_result(r: bool) -> None:
        results.append(r)

    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(ConfirmModal("Test", "Confirm?", danger=True), on_result)
        await pilot.pause()
        assert app.screen.focused is app.screen.query_one("#no", Button)
        await pilot.press("enter")
        await pilot.pause()

    assert results == [False]


async def test_non_danger_modal_keeps_focusing_yes_and_enter_returns_true() -> None:
    """The scoped guard: a non-destructive prompt still focuses Yes."""
    from textual.widgets import Button

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.confirm import ConfirmModal

    app = OpenReviewApp()
    results: list[bool] = []

    def on_result(r: bool) -> None:
        results.append(r)

    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(ConfirmModal("Test", "Confirm?"), on_result)
        await pilot.pause()
        assert app.screen.focused is app.screen.query_one("#yes", Button)
        await pilot.press("enter")
        await pilot.pause()

    assert results == [True]
