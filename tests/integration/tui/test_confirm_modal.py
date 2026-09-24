"""Integration tests for ConfirmModal (T022)."""

from __future__ import annotations

from pathlib import Path


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


async def test_escape_on_confirmation_does_not_pop_the_screen_underneath(
    isolated_xdg: dict[str, Path],
) -> None:
    """A handled Escape must not also reach the screen underneath.

    ``PiiDataScreen`` binds ``escape`` to ``pop_screen``; without stopping the
    key event in the modal, one Escape both cancels the deletion and closes the
    stored-PII list. The modal must swallow the key.
    """
    import sqlite3
    from datetime import UTC, datetime

    from textual.widgets import ListView

    from openreview_cli.pii.cache import PiiCache
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.confirm import ConfirmModal
    from openreview_cli.tui.screens.pii_data import PiiDataScreen

    doc_hash = "c1d2e3f4" + "0" * 56
    db_path = isolated_xdg["db_path"]
    review_dir = isolated_xdg["data_dir"] / "reviews" / doc_hash[:12]
    review_dir.mkdir(parents=True, exist_ok=True)
    mapping = review_dir / "pii_map.enc"
    stripped = review_dir / "stripped.txt"
    mapping.write_text("{}", encoding="utf-8")
    stripped.write_text("hello", encoding="utf-8")
    PiiCache(db_path).put(doc_hash, "cfg", str(stripped), str(mapping))
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "INSERT INTO pii_audit_trail "
            "(document_hash, timestamp, entity_count, entity_type_distribution, "
            " processing_time_ms, config_hash, status, failed_pages) "
            "VALUES (?, ?, 3, '{}', 0, 'cfg', 'success', '[]')",
            (doc_hash, datetime.now(UTC).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(PiiDataScreen())
        await pilot.pause()

        # 1. the stored-PII screen is live and showing the seeded row
        assert isinstance(app.screen, PiiDataScreen)
        list_view = app.screen.query_one("#pii-list", ListView)
        assert len(list_view.children) == 1

        # 2. the delete confirmation is open on top of it
        list_view.index = 0
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmModal)

        # 3. Escape cancels the deletion and stays on the stored-PII screen
        await pilot.press("escape")
        await pilot.pause()

        assert isinstance(app.screen, PiiDataScreen)

    conn = sqlite3.connect(str(db_path))
    try:
        remaining = {row[0] for row in conn.execute("SELECT document_hash FROM pii_cache")}
    finally:
        conn.close()
    assert remaining == {doc_hash}
    assert mapping.exists()


async def test_confirmation_message_renders_bracketed_text_literally() -> None:
    """A message with lowercase brackets is rendered verbatim, not eaten as markup.

    Rich parses ``[clause]`` as a (bogus) style tag and consumes it, so the
    literal text would silently vanish from the rendered label. Confirmation
    text is user-authored (prompt names, slot names); the modal must render it
    literally by default. The assertion is on the *rendered* label, so it
    proves the markup was not consumed rather than restating the argument.
    """
    from textual.widgets import Label

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.confirm import ConfirmModal

    app = OpenReviewApp()
    message = "Delete prompt 'notes [clause] draft'? This cannot be undone."

    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(ConfirmModal("Delete prompt", message, danger=True))
        await pilot.pause()
        rendered = str(app.screen.query_one("#confirm-message", Label).render())

    assert "[clause]" in rendered
    assert rendered == message


async def test_confirmation_title_renders_bracketed_text_literally() -> None:
    """The title is literal by default too - both labels carry the parameter."""
    from textual.widgets import Label

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.confirm import ConfirmModal

    app = OpenReviewApp()
    title = "Confirm [clause]"

    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(ConfirmModal(title, "Confirm?"))
        await pilot.pause()
        rendered = str(app.screen.query_one("#confirm-title", Label).render())

    assert "[clause]" in rendered
    assert rendered == title


async def test_markup_true_still_allows_markup() -> None:
    """``markup=True`` opts back in, so the parameter is real, not hard-coded off."""
    from textual.widgets import Label

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.confirm import ConfirmModal

    app = OpenReviewApp()

    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(ConfirmModal("Title", "[b]bold[/b] message", markup=True))
        await pilot.pause()
        rendered = str(app.screen.query_one("#confirm-message", Label).render())

    assert "[b]" not in rendered
    assert rendered == "bold message"
