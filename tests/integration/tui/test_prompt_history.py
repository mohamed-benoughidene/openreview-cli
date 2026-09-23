"""Integration tests for prompt history/diff screens (Task 2).

Drives the REAL ``OpenReviewApp`` and the REAL ``PromptStore`` over the
per-test isolated XDG data directory materialized by ``isolated_xdg`` — no
data mocks.  The screens are pushed onto a running app and exercised through
their real widgets, mirroring ``test_playbooks_tab.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.widgets import Label, ListItem, ListView, Static

from openreview_cli.prompts.store import PromptStore
from openreview_cli.tui.domain.prompts import (
    get_prompt_history_via_tui,
    get_prompt_version_diff,
)


def _list_item_text(item: ListItem) -> str:
    """Extract visible text from a ListItem (same helper as the playbook tests)."""
    try:
        label = item.query_one(Label)
        return str(label.render())
    except Exception:
        return str(item.render())


@pytest.fixture
def store(isolated_xdg: dict[str, Path]) -> PromptStore:
    """A real PromptStore bound to the isolated per-test database."""
    s = PromptStore(isolated_xdg["db_path"])
    s.init()
    return s


async def test_prompt_history_screen_shows_real_versions(store: PromptStore) -> None:
    """The list renders the real version numbers and created_at values."""
    v1 = store.create("greeting", "hello one\n")
    v2 = store.update("greeting", "hello two\n")
    v3 = store.update("greeting", "hello three\n")

    history = get_prompt_history_via_tui("greeting")
    assert history["found"] is True
    assert history["current_version"] == 3

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.prompt_detail import PromptHistoryScreen

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(
            PromptHistoryScreen(
                prompt_name="greeting",
                rows=history["rows"],
                current_version=history["current_version"],
            )
        )
        await pilot.pause()

        lv = app.screen.query_one("#vhistory-list", ListView)
        texts = [_list_item_text(item) for item in lv.children]
        joined = "\n".join(texts)

        assert len(texts) == 3
        # Real version numbers from the store's rows.
        for version in (1, 2, 3):
            assert f"v{version}" in joined, joined
        # Real created_at timestamps from the store's writes.
        for created_at in (v1.created_at, v2.created_at, v3.created_at):
            assert created_at in joined, joined


async def test_prompt_diff_screen_renders_real_unified_diff(store: PromptStore) -> None:
    """The body renders the real unified diff produced by the domain helper."""
    store.create("doc", "alpha\nbeta\n")
    store.update("doc", "alpha\ngamma\nunique-newer-line\n")

    diff_text = get_prompt_version_diff("doc", 1, 2)
    assert "+unique-newer-line" in diff_text

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.prompt_detail import PromptDiffScreen

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(PromptDiffScreen("doc", 1, 2, diff_text))
        await pilot.pause()

        body = app.screen.query_one("#diff-body", Static)
        rendered = str(body.content)

        assert "unique-newer-line" in rendered, rendered
        assert "+unique-newer-line" in rendered, rendered


async def test_prompt_history_screen_dismisses_on_escape(store: PromptStore) -> None:
    """Pressing Escape pops the history modal (inherited from VersionHistoryScreen)."""
    store.create("greeting", "one\n")
    store.update("greeting", "two\n")

    history = get_prompt_history_via_tui("greeting")

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.prompt_detail import PromptHistoryScreen

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(
            PromptHistoryScreen(
                prompt_name="greeting",
                rows=history["rows"],
                current_version=history["current_version"],
            )
        )
        await pilot.pause()
        assert isinstance(app.screen, PromptHistoryScreen)

        await pilot.press("escape")
        await pilot.pause()

        assert not any(isinstance(s, PromptHistoryScreen) for s in app._screen_stack)


async def test_prompt_history_view_diff_opens_diff_screen(store: PromptStore) -> None:
    """Clicking 'View diff' pushes a PromptDiffScreen for the selected pair."""
    store.create("greeting", "one\n")
    store.update("greeting", "two\n")

    history = get_prompt_history_via_tui("greeting")

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.prompt_detail import (
        PromptDiffScreen,
        PromptHistoryScreen,
    )

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(
            PromptHistoryScreen(
                prompt_name="greeting",
                rows=history["rows"],
                current_version=history["current_version"],
            )
        )
        await pilot.pause()

        # Highlight a row so the inherited handler has a selected version.
        lv = app.screen.query_one("#vhistory-list", ListView)
        lv.index = 0
        await pilot.pause()

        await pilot.click("#btn-diff-v")
        await pilot.pause()

        assert isinstance(app.screen, PromptDiffScreen)
