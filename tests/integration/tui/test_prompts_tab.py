"""Integration tests for PromptsTab (Task 3).

Drives the REAL ``OpenReviewApp`` and the REAL ``PromptStore`` over the
per-test isolated XDG data directory materialized by ``isolated_xdg`` — no
data mocks — mirroring ``test_playbooks_tab.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.widgets import Label, ListItem, ListView, TabbedContent

from openreview_cli.prompts.store import PromptStore


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


async def test_prompts_tab_activates_with_six_key(store: PromptStore) -> None:
    """Pressing '6' makes the prompts tab active and shows the PromptsTab."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.tabs.prompts import PromptsTab

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        tabs = app.query_one("#tabs", TabbedContent)
        assert tabs.active == "home"

        await pilot.press("6")
        await pilot.pause()

        assert tabs.active == "prompts"
        assert app.query_one(PromptsTab) is not None


async def test_prompts_tab_empty_state(store: PromptStore) -> None:
    """An empty store shows the teaching empty-state message."""
    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("6")
        await pilot.pause()

        lv = app.query_one("#prompt-list", ListView)
        items = list(lv.children)
        assert len(items) == 1
        msg = _list_item_text(items[0])
        assert "No prompts yet" in msg
        assert "openreview prompt create" in msg


async def test_prompts_tab_shows_prompts_with_latest_version(store: PromptStore) -> None:
    """Seeded prompts appear in the list with their real latest version."""
    store.create("greeting", "hello one")
    store.update("greeting", "hello two")
    store.create("summary", "summarize this")

    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("6")
        await pilot.pause()

        items = list(app.query_one("#prompt-list", ListView).children)
        texts = [_list_item_text(item) for item in items]
        joined = "\n".join(texts)

        assert "greeting" in joined
        assert "summary" in joined

        greeting_text = next(t for t in texts if "greeting" in t)
        summary_text = next(t for t in texts if "summary" in t)
        # Real latest versions straight from the store.
        assert "v2" in greeting_text
        assert "v1" in summary_text


async def test_prompts_tab_select_opens_history(store: PromptStore) -> None:
    """Selecting a prompt opens the PromptHistoryScreen."""
    store.create("greeting", "one")
    store.update("greeting", "two")

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.prompt_detail import PromptHistoryScreen

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("6")
        await pilot.pause()

        lv = app.query_one("#prompt-list", ListView)
        lv.focus()
        await pilot.pause()
        lv.index = 0
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, PromptHistoryScreen)
