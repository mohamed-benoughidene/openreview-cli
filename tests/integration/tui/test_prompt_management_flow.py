"""End-to-end proof that all ten prompt actions work from the running TUI (Task 10).

One test per command (``list``, ``create``, ``update``, ``delete``, ``bind``,
``unbind``, ``bindings``, ``test``, ``export``, ``import``).  Each drives the
REAL ``OpenReviewApp`` through the REAL widgets — the tab (reached with ``"6"``),
its toolbar and selection-gated action row, then the real screens — and asserts
the **database or filesystem effect**, never the render alone.

Mirrors ``test_prompts_tab.py``: a real ``PromptStore`` over the per-test
``isolated_xdg`` database, ``tmp_path`` for export/import files, and
``app.run_test(size=(120, 40))`` with ``pilot.press``/``click``/``pause``.

The action row is disabled until a row is highlighted (``tabs/prompts.py:
117-131``), so every per-prompt action selects a row first via ``_highlight``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from textual.widgets import Button, Input, Label, ListItem, ListView, Select, Static, TextArea

from openreview_cli.prompts.io import parse_prompts_yaml
from openreview_cli.prompts.store import PromptStore


def _list_item_text(item: ListItem) -> str:
    """Extract visible text from a ListItem (same helper as the other TUI tests)."""
    try:
        return str(item.query_one(Label).render())
    except Exception:
        return str(item.render())


async def _highlight(pilot: Any, app: Any, index: int = 0) -> None:
    """Focus the prompt list and highlight ``index`` so the action row is enabled.

    The tab disables the whole action row until a row is highlighted, so every
    per-prompt action must select first.
    """
    list_view = app.query_one("#prompt-list", ListView)
    list_view.focus()
    await pilot.pause()
    list_view.index = index
    await pilot.pause()


@pytest.fixture
def store(isolated_xdg: dict[str, Path]) -> PromptStore:
    """A real PromptStore bound to the isolated per-test database."""
    s = PromptStore(isolated_xdg["db_path"])
    s.init()
    return s


# ── list ──


async def test_list_renders_two_seeded_prompts(store: PromptStore) -> None:
    """``list``: pressing "6" renders a row for each seeded prompt with its version."""
    store.create("greeting", "hello one")
    store.create("summary", "summarize this")

    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("6")
        await pilot.pause()

        items = list(app.query_one("#prompt-list", ListView).children)
        texts = [_list_item_text(item) for item in items]
        joined = "\n".join(texts)

        assert len(items) == 2
        assert "greeting (v1)" in joined, joined
        assert "summary (v1)" in joined, joined
        assert app.is_running

    # The render matches what the store actually holds.
    assert sorted(p.name for p in store.list()) == ["greeting", "summary"]


# ── create ──


async def test_create_adds_row_with_version_one(store: PromptStore) -> None:
    """``create``: ``#btn-new-prompt`` -> fill -> ``#prompt-save`` persists version 1."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.prompt_form import PromptFormScreen

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("6")
        await pilot.pause()

        await pilot.click("#btn-new-prompt")
        await pilot.pause()

        form = app.screen
        assert isinstance(form, PromptFormScreen)
        form.query_one("#prompt-form-name", Input).value = "brand new"
        form.query_one("#prompt-form-content", TextArea).text = "body one"
        await pilot.pause()

        await pilot.click("#prompt-save")
        await pilot.pause()

        items = list(app.query_one("#prompt-list", ListView).children)
        assert len(items) == 1
        assert "brand new" in _list_item_text(items[0])
        assert app.is_running

    created = store.get("brand new", 1)
    assert created.version == 1
    assert created.content == "body one"
    assert [p.name for p in store.list()] == ["brand new"]


# ── update ──


async def test_update_appends_version_two_keeping_version_one(store: PromptStore) -> None:
    """``update``: edit -> ``#prompt-save`` appends version 2, leaving version 1 intact."""
    store.create("greeting", "original body")

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.prompt_form import PromptFormScreen

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("6")
        await pilot.pause()
        await _highlight(pilot, app, index=0)

        await pilot.click("#btn-edit-prompt")
        await pilot.pause()

        form = app.screen
        assert isinstance(form, PromptFormScreen)
        form.query_one("#prompt-form-content", TextArea).text = "edited body"
        await pilot.pause()

        await pilot.click("#prompt-save")
        await pilot.pause()

        assert app.is_running

    # Version 1 is intact; version 2 carries the new content.
    assert store.get("greeting", 1).content == "original body"
    latest = store.get("greeting", 2)
    assert latest.version == 2
    assert latest.content == "edited body"


# ── delete ──


async def test_delete_removes_prompt_and_its_bindings(store: PromptStore) -> None:
    """``delete``: confirm -> ``#yes`` removes every row and its bindings."""
    store.create("doomed", "bye")
    store.bind("reasoning", "doomed", 1)
    assert store.bindings()  # sanity: there is a binding to be dropped

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.confirm import ConfirmModal

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("6")
        await pilot.pause()
        await _highlight(pilot, app, index=0)

        await pilot.click("#btn-delete-prompt")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmModal)

        await pilot.click("#yes")
        await pilot.pause()

        items = list(app.query_one("#prompt-list", ListView).children)
        assert len(items) == 1
        assert "No prompts yet" in _list_item_text(items[0])
        assert app.is_running

    assert [p.name for p in store.list()] == []
    assert store.bindings() == []


# ── bind ──


async def test_bind_creates_a_binding_row(store: PromptStore) -> None:
    """``bind``: ``#btn-bind-prompt`` -> slot + version -> ``#bind-confirm`` writes a row."""
    store.create("greeting", "hi")

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.prompt_bindings import PromptBindModal

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("6")
        await pilot.pause()
        await _highlight(pilot, app, index=0)

        await pilot.click("#btn-bind-prompt")
        await pilot.pause()

        modal = app.screen
        assert isinstance(modal, PromptBindModal)
        modal.query_one("#bind-slot", Select).value = "reasoning"
        await pilot.pause()
        modal.query_one("#bind-version", Select).value = 1
        await pilot.pause()

        await pilot.click("#bind-confirm")
        await pilot.pause()

        assert app.is_running

    bindings = {b.slot: (b.prompt_name, b.prompt_version) for b in store.bindings()}
    assert bindings == {"reasoning": ("greeting", 1)}


# ── unbind ──


async def test_unbind_removes_the_binding_row(store: PromptStore) -> None:
    """``unbind``: ``#btn-prompt-bindings`` -> ``#btn-unbind-<slot>`` -> ``#yes`` deletes it."""
    store.create("greeting", "hi")
    store.bind("reasoning", "greeting", 1)

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.confirm import ConfirmModal
    from openreview_cli.tui.screens.prompt_bindings import PromptBindingsScreen

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("6")
        await pilot.pause()
        await _highlight(pilot, app, index=0)

        await pilot.click("#btn-prompt-bindings")
        await pilot.pause()
        assert isinstance(app.screen, PromptBindingsScreen)

        await pilot.click("#btn-unbind-reasoning")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmModal)

        await pilot.click("#yes")
        await pilot.pause()

        assert app.is_running

    assert store.bindings() == []


# ── bindings ──


async def test_bindings_screen_matches_the_database_row(store: PromptStore) -> None:
    """``bindings``: the rendered row is built from the real ``prompt_bindings`` row."""
    store.create("greeting", "hi")
    store.bind("reasoning", "greeting", 1)

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.prompt_bindings import PromptBindingsScreen

    app = OpenReviewApp()
    rendered = ""
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("6")
        await pilot.pause()
        await _highlight(pilot, app, index=0)

        await pilot.click("#btn-prompt-bindings")
        await pilot.pause()
        assert isinstance(app.screen, PromptBindingsScreen)

        rows = list(app.screen.query_one("#bindings-list", ListView).children)
        assert len(rows) == 1
        rendered = _list_item_text(rows[0])
        assert app.is_running

    binding = store.bindings()[0]
    expected = f"{binding.slot}: {binding.prompt_name} v{binding.prompt_version}"
    assert rendered.startswith(expected), rendered
    # The screen was opened for this prompt, so its row is marked as such.
    assert "this prompt" in rendered


# ── test ──


async def test_test_command_refuses_unknown_version(store: PromptStore) -> None:
    """``test``: an unknown version is refused inline, with the store's message.

    The run button is clicked exactly once.  A second ``pilot.click`` on the
    same button within ``Button.active_effect_duration`` (0.2s) is dropped by
    ``Button._on_click`` while the ``-active`` class is set, so this test must
    not rely on a second click landing; the valid-version case is its own test.
    """
    store.create("greeting", "one")
    store.update("greeting", "two")

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.prompt_test import PromptTestModal

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("6")
        await pilot.pause()
        await _highlight(pilot, app, index=0)

        await pilot.click("#btn-test-prompt")
        await pilot.pause()

        modal = app.screen
        assert isinstance(modal, PromptTestModal)
        versions = modal.query_one("#prompt-test-versions", Input)
        # The tab resolves the latest version and pre-fills it.
        assert versions.value == "2"

        # An unknown version is refused inline, never dismissed.
        versions.value = "99"
        await pilot.pause()
        await pilot.click("#prompt-test-run")
        await pilot.pause()

        error = str(modal.query_one("#prompt-test-error", Label).render())
        assert "version 99 not found" in error
        assert str(modal.query_one("#prompt-test-notice", Static).render()) == ""
        assert isinstance(app.screen, PromptTestModal)
        assert app.is_running


async def test_test_command_valid_versions_render_notice_and_never_dispatch(
    store: PromptStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``test``: a valid version shows the honest roadmap notice; no dispatch.

    The no-dispatch proof is real: ``Gateway.chat`` (``gateway/router.py``) is
    patched to record-and-raise, and the test asserts it is never called.  The
    run button is clicked exactly once (see the sibling refusal test for why a
    second click would be dropped).
    """
    store.create("greeting", "one")
    store.update("greeting", "two")

    from openreview_cli.gateway.router import Gateway

    dispatched: list[Any] = []

    def _boom(self: Any, *args: Any, **kwargs: Any) -> str:
        dispatched.append((args, kwargs))
        raise AssertionError("dispatched")

    monkeypatch.setattr(Gateway, "chat", _boom)

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.prompt_test import PromptTestModal

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("6")
        await pilot.pause()
        await _highlight(pilot, app, index=0)

        await pilot.click("#btn-test-prompt")
        await pilot.pause()

        modal = app.screen
        assert isinstance(modal, PromptTestModal)
        versions = modal.query_one("#prompt-test-versions", Input)
        assert versions.value == "2"

        # A valid version shows the honest roadmap notice.
        versions.value = "1,2"
        await pilot.pause()
        await pilot.click("#prompt-test-run")
        await pilot.pause()

        notice = str(modal.query_one("#prompt-test-notice", Static).render())
        assert "benchmark harness" in notice
        assert "roadmap N-3" in notice
        assert str(modal.query_one("#prompt-test-error", Label).render()) == ""
        assert app.is_running

    # No model was ever dispatched.
    assert dispatched == []


# ── export ──


async def test_export_writes_file_that_parses_back(store: PromptStore, tmp_path: Path) -> None:
    """``export``: ``#btn-export-prompt`` -> path -> ``#btn-export-confirm`` writes YAML."""
    store.create("greeting", "hello one")
    store.update("greeting", "hello two")
    dest = tmp_path / "greeting.yaml"

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.prompt_export import PromptExportModal

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("6")
        await pilot.pause()
        await _highlight(pilot, app, index=0)

        await pilot.click("#btn-export-prompt")
        await pilot.pause()
        assert isinstance(app.screen, PromptExportModal)

        app.screen.query_one("#export-path", Input).value = str(dest)
        await pilot.pause()

        await pilot.click("#btn-export-confirm")
        await pilot.pause()

        assert app.is_running

    # The file exists and parses back to every version of that one prompt.
    assert dest.exists()
    parsed = parse_prompts_yaml(dest.read_text())
    assert len(parsed) == 1
    assert parsed[0]["name"] == "greeting"
    assert {int(version["version"]) for version in parsed[0]["versions"]} == {1, 2}


# ── import ──


async def test_import_adds_prompt_to_the_store(store: PromptStore, tmp_path: Path) -> None:
    """``import``: ``#btn-import-prompt`` -> path -> ``#btn-import-confirm`` lands a row."""
    path = tmp_path / "prompts.yaml"
    path.write_text(
        "- name: imported\n"
        "  versions:\n"
        "    - version: 1\n"
        "      content: hi there\n"
        "      created_at: 2026-01-01T00:00:00Z\n"
    )

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.prompt_import import PromptImportModal

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("6")
        await pilot.pause()

        await pilot.click("#btn-import-prompt")
        await pilot.pause()
        assert isinstance(app.screen, PromptImportModal)

        app.screen.query_one("#import-path-input", Input).value = str(path)
        await pilot.pause()

        # The Import button is shown only once the file validates.
        assert app.screen.query_one("#btn-import-confirm", Button).display is True
        await pilot.click("#btn-import-confirm")
        await pilot.pause()

        assert app.is_running

    assert [p.name for p in store.list()] == ["imported"]
    assert store.get("imported", 1).content == "hi there"
