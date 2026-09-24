"""Integration tests for PromptsTab (Task 4).

Drives the REAL ``OpenReviewApp`` and the REAL ``PromptStore`` over the
per-test isolated XDG data directory materialized by ``isolated_xdg`` — no
data mocks — mirroring ``test_playbooks_tab.py``.

Screens that this tab navigates to (``PromptFormScreen``,
``PromptBindingsScreen``, ``PromptTestModal``, ``PromptExportModal``,
``PromptImportModal``) are imported *inside* the test that needs them, as a
single import block each, so a not-yet-landed screen fails only its own test
rather than the whole module — and so the import block has no section order to
get wrong while those modules do not exist yet.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest
from textual.widgets import Input, Label, ListItem, ListView, TabbedContent, TextArea

from openreview_cli.prompts.store import PromptStore

# The six selection-gated action buttons, in the order the plan lists them.
ACTION_IDS = [
    "btn-edit-prompt",
    "btn-bind-prompt",
    "btn-prompt-bindings",
    "btn-test-prompt",
    "btn-export-prompt",
    "btn-delete-prompt",
]


def _list_item_text(item: ListItem) -> str:
    """Extract visible text from a ListItem (same helper as the playbook tests)."""
    try:
        label = item.query_one(Label)
        return str(label.render())
    except Exception:
        return str(item.render())


def _action_buttons(app: Any) -> list[Any]:
    """Every ``.prompt-action`` button on the mounted tab."""
    from openreview_cli.tui.tabs.prompts import PromptsTab

    return list(app.query_one(PromptsTab).query(".prompt-action"))


async def _highlight(pilot: Any, app: Any, index: int = 0) -> None:
    """Focus the list and highlight ``index`` so the action row is enabled."""
    lv = app.query_one("#prompt-list", ListView)
    lv.focus()
    await pilot.pause()
    lv.index = index
    await pilot.pause()


@pytest.fixture
def store(isolated_xdg: dict[str, Path]) -> PromptStore:
    """A real PromptStore bound to the isolated per-test database."""
    s = PromptStore(isolated_xdg["db_path"])
    s.init()
    return s


# ── List rendering ──


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
    """An empty store shows the teaching empty-state message.

    Rewritten for Task 4: the empty state now names the in-app entry point
    instead of the CLI command.
    """
    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("6")
        await pilot.pause()

        lv = app.query_one("#prompt-list", ListView)
        items = list(lv.children)
        assert len(items) == 1
        msg = _list_item_text(items[0])
        assert "[+ New prompt]" in msg
        assert "openreview prompt create" not in msg


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


async def test_prompt_history_still_reachable(store: PromptStore) -> None:
    """Row-select still opens the history screen for the row that was picked."""
    store.create("alpha", "a")
    store.create("beta", "b")

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.tabs.prompts import PromptsTab

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("6")
        await pilot.pause()

        names = [p["name"] for p in app.query_one(PromptsTab)._prompts_data]
        assert len(names) == 2

        await _highlight(pilot, app, index=1)
        await pilot.press("enter")
        await pilot.pause()

        from openreview_cli.tui.screens.prompt_detail import PromptHistoryScreen

        assert isinstance(app.screen, PromptHistoryScreen)
        title = str(app.screen.query_one("#vhistory-title", Label).render())
        assert names[1] in title


# ── Highlight guard ──


async def test_action_buttons_disabled_until_highlighted(store: PromptStore) -> None:
    """With a prompt present all six actions start disabled; highlighting enables them."""
    store.create("greeting", "hi")

    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("6")
        await pilot.pause()

        buttons = _action_buttons(app)
        assert len(buttons) == 6
        assert {btn.id for btn in buttons} == set(ACTION_IDS)
        assert all(btn.disabled for btn in buttons)

        await _highlight(pilot, app, index=0)

        assert all(not btn.disabled for btn in buttons)


async def test_empty_store_highlight_keeps_actions_disabled(store: PromptStore) -> None:
    """The empty-state row is selectable, but highlighting it enables nothing."""
    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("6")
        await pilot.pause()

        await _highlight(pilot, app, index=0)

        assert all(btn.disabled for btn in _action_buttons(app))
        assert app.is_running


async def test_clear_disables_actions_without_raising(store: PromptStore) -> None:
    """``ListView.clear()`` posts ``Highlighted(None)``; it must not index out of range."""
    store.create("greeting", "hi")

    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("6")
        await pilot.pause()

        await _highlight(pilot, app, index=0)
        assert all(not btn.disabled for btn in _action_buttons(app))

        app.query_one("#prompt-list", ListView).clear()
        await pilot.pause()

        assert all(btn.disabled for btn in _action_buttons(app))
        assert app.is_running


# ── One test per button id: destination ──


async def test_btn_new_prompt_opens_form(store: PromptStore) -> None:
    """``#btn-new-prompt`` opens ``PromptFormScreen`` (create mode)."""
    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("6")
        await pilot.pause()

        await pilot.click("#btn-new-prompt")
        await pilot.pause()

        from openreview_cli.tui.screens.prompt_form import PromptFormScreen

        assert isinstance(app.screen, PromptFormScreen)
        assert app.is_running


async def test_btn_import_prompt_opens_import_modal(store: PromptStore) -> None:
    """``#btn-import-prompt`` opens ``PromptImportModal``."""
    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("6")
        await pilot.pause()

        await pilot.click("#btn-import-prompt")
        await pilot.pause()

        from openreview_cli.tui.screens.prompt_import import PromptImportModal

        assert isinstance(app.screen, PromptImportModal)
        assert app.is_running


async def test_btn_edit_prompt_opens_form_prefilled(store: PromptStore) -> None:
    """``#btn-edit-prompt`` opens ``PromptFormScreen`` in edit mode, prefilled."""
    store.create("greeting", "hello there")

    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("6")
        await pilot.pause()
        await _highlight(pilot, app, index=0)

        await pilot.click("#btn-edit-prompt")
        await pilot.pause()

        from openreview_cli.tui.screens.prompt_form import PromptFormScreen

        assert isinstance(app.screen, PromptFormScreen)
        name_input = app.screen.query_one("#prompt-form-name", Input)
        assert name_input.value == "greeting"
        assert name_input.disabled  # edit mode locks the name
        assert app.screen.query_one("#prompt-form-content", TextArea).text == "hello there"
        assert app.is_running


async def test_btn_bind_prompt_opens_bind_modal(store: PromptStore) -> None:
    """``#btn-bind-prompt`` opens ``PromptBindModal`` for this prompt."""
    store.create("greeting", "hi")

    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("6")
        await pilot.pause()
        await _highlight(pilot, app, index=0)

        await pilot.click("#btn-bind-prompt")
        await pilot.pause()

        from openreview_cli.tui.screens.prompt_bindings import PromptBindModal

        assert isinstance(app.screen, PromptBindModal)
        assert app.is_running


async def test_btn_prompt_bindings_opens_bindings_screen(store: PromptStore) -> None:
    """``#btn-prompt-bindings`` opens ``PromptBindingsScreen``."""
    store.create("greeting", "hi")

    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("6")
        await pilot.pause()
        await _highlight(pilot, app, index=0)

        await pilot.click("#btn-prompt-bindings")
        await pilot.pause()

        from openreview_cli.tui.screens.prompt_bindings import PromptBindingsScreen

        assert isinstance(app.screen, PromptBindingsScreen)
        assert app.is_running


async def test_btn_test_prompt_opens_test_modal(store: PromptStore) -> None:
    """``#btn-test-prompt`` opens ``PromptTestModal`` with the latest version."""
    store.create("greeting", "one")
    store.update("greeting", "two")

    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("6")
        await pilot.pause()
        await _highlight(pilot, app, index=0)

        await pilot.click("#btn-test-prompt")
        await pilot.pause()

        from openreview_cli.tui.screens.prompt_test import PromptTestModal

        assert isinstance(app.screen, PromptTestModal)
        assert app.is_running


async def test_btn_export_prompt_opens_export_modal(store: PromptStore) -> None:
    """``#btn-export-prompt`` opens ``PromptExportModal``."""
    store.create("greeting", "hi")

    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("6")
        await pilot.pause()
        await _highlight(pilot, app, index=0)

        await pilot.click("#btn-export-prompt")
        await pilot.pause()

        from openreview_cli.tui.screens.prompt_export import PromptExportModal

        assert isinstance(app.screen, PromptExportModal)
        assert app.is_running


async def test_btn_delete_prompt_opens_confirm(store: PromptStore) -> None:
    """``#btn-delete-prompt`` opens a ``ConfirmModal``."""
    store.create("greeting", "hi")

    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("6")
        await pilot.pause()
        await _highlight(pilot, app, index=0)

        await pilot.click("#btn-delete-prompt")
        await pilot.pause()

        from openreview_cli.tui.screens.confirm import ConfirmModal

        assert isinstance(app.screen, ConfirmModal)
        assert app.is_running


# ── Delete ──


async def test_delete_message_has_version_count_and_slots_and_renders_literally(
    store: PromptStore,
) -> None:
    """The confirmation names the version count and bound slots, rendered verbatim.

    The prompt name carries lowercase brackets, which Rich would otherwise
    consume as markup; asserting on the *rendered* label proves it did not.
    """
    name = "notes [clause] draft"
    store.create(name, "first")
    store.update(name, "second")
    store.bind("reasoning", name, 1)

    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("6")
        await pilot.pause()
        await _highlight(pilot, app, index=0)

        await pilot.click("#btn-delete-prompt")
        await pilot.pause()

        from openreview_cli.tui.screens.confirm import ConfirmModal

        assert isinstance(app.screen, ConfirmModal)
        rendered = str(app.screen.query_one("#confirm-message", Label).render())

    expected = (
        f"Delete prompt '{name}'? This permanently deletes 2 version(s) "
        f"and unbinds 1 slot(s): reasoning. This cannot be undone."
    )
    assert rendered == expected


async def test_delete_confirmed_removes_row(store: PromptStore) -> None:
    """Confirming the delete removes the prompt and reloads the list."""
    store.create("gone", "bye")

    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("6")
        await pilot.pause()
        await _highlight(pilot, app, index=0)

        await pilot.click("#btn-delete-prompt")
        await pilot.pause()
        await pilot.click("#yes")
        await pilot.pause()

        items = list(app.query_one("#prompt-list", ListView).children)
        assert len(items) == 1
        assert "No prompts yet" in _list_item_text(items[0])
        assert app.is_running

    assert [p.name for p in store.list()] == []


async def test_delete_failure_leaves_app_running(
    store: PromptStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A store failure in the delete callback is reported, never fatal."""
    store.create("keep", "still here")

    def _boom(*args: Any, **kwargs: Any) -> None:
        raise sqlite3.IntegrityError("boom")

    monkeypatch.setattr("openreview_cli.tui.domain.prompts.delete_prompt_via_tui", _boom)

    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    notifications: list[tuple[str, dict[str, Any]]] = []
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("6")
        await pilot.pause()
        await _highlight(pilot, app, index=0)

        await pilot.click("#btn-delete-prompt")
        await pilot.pause()

        # Capture what the tab reports without letting the real toast machinery run.
        app.notify = lambda msg, **kw: notifications.append((msg, kw))  # type: ignore[method-assign]
        await pilot.click("#yes")
        await pilot.pause()

        assert app.is_running
        assert any("Delete failed" in msg for msg, _ in notifications)

    assert [p.name for p in store.list()] == ["keep"]


# ── Layout ──


async def test_action_row_fits_at_80x24(store: PromptStore) -> None:
    """The six-button action row fits the smallest supported width."""
    store.create("greeting", "hi")

    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("6")
        await pilot.pause()

        buttons = _action_buttons(app)
        assert len(buttons) == 6
        for btn in buttons:
            assert btn.region.right <= 80, (btn.id, btn.region)
            assert btn.region.width > 0, (btn.id, btn.region)
