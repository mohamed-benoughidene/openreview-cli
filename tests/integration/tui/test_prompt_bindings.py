"""Integration tests for the prompt bindings screen and bind modal (Task 6).

Drives the REAL ``OpenReviewApp`` and a REAL ``PromptStore`` over the per-test
isolated XDG data directory materialized by ``isolated_xdg`` — no data mocks —
except for the one state the schema cannot represent (a prompt with zero
versions), which is mocked explicitly and noted at its test.

The overwrite-confirmation tests drive the real ``PromptsTab`` entry point
(``#btn-bind-prompt``) because the *caller* performs the bind: asserting that a
declined overwrite leaves the database untouched is only meaningful end to end.
Decline and accept are separate tests because each clicks ``#bind-confirm``
exactly once (see the note on the declined test).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from textual.widgets import Button, Label, ListItem, ListView, Select, Static
from textual.widgets.select import InvalidSelectValueError

from openreview_cli.prompts.store import PromptStore
from openreview_cli.slots import VALID_SLOTS


def _list_item_text(item: ListItem) -> str:
    """Extract visible text from a ListItem (same helper as the other TUI tests)."""
    try:
        label = item.query_one(Label)
        return str(label.render())
    except Exception:
        return str(item.render())


async def _highlight(pilot: Any, app: Any, index: int = 0) -> None:
    """Focus the prompt list and highlight ``index`` so the action row is enabled."""
    list_view = app.query_one("#prompt-list", ListView)
    list_view.focus()
    await pilot.pause()
    list_view.index = index
    await pilot.pause()


async def _open_bindings_screen(pilot: Any, app: Any) -> None:
    """Reach the bindings screen through the real tab button."""
    await pilot.press("6")
    await pilot.pause()
    await _highlight(pilot, app)
    await pilot.click("#btn-prompt-bindings")
    await pilot.pause()


@pytest.fixture
def store(isolated_xdg: dict[str, Path]) -> PromptStore:
    """A real PromptStore bound to the isolated per-test database."""
    prompt_store = PromptStore(isolated_xdg["db_path"])
    prompt_store.init()
    return prompt_store


# ── Bindings list ──


async def test_bindings_screen_lists_all_bindings_and_marks_this_prompt(
    store: PromptStore,
) -> None:
    """Every binding is listed; the row for the opened prompt is marked."""
    store.create("greeting", "hi")
    store.create("other", "other")
    store.bind("reasoning", "greeting", 1)
    store.bind("extraction", "other", 1)

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.prompt_bindings import PromptBindingsScreen

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await _open_bindings_screen(pilot, app)

        assert isinstance(app.screen, PromptBindingsScreen)
        assert str(app.screen.query_one("#bindings-title", Static).render()) == "Bindings"

        rows = list(app.screen.query_one("#bindings-list", ListView).children)
        texts = {_list_item_text(row) for row in rows}
        joined = "\n".join(texts)
        assert "reasoning: greeting v1" in joined
        assert "extraction: other v1" in joined

        greeting_row = next(text for text in texts if "greeting" in text)
        other_row = next(text for text in texts if "other" in text)
        assert "this prompt" in greeting_row
        assert "this prompt" not in other_row
        assert app.is_running

    assert {binding.slot for binding in store.bindings()} == {"reasoning", "extraction"}


async def test_bindings_screen_empty_state(store: PromptStore) -> None:
    """With no bindings the screen shows an empty-state line, not a stale row."""
    store.create("greeting", "hi")

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.prompt_bindings import PromptBindingsScreen

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await _open_bindings_screen(pilot, app)

        assert isinstance(app.screen, PromptBindingsScreen)
        assert list(app.screen.query_one("#bindings-list", ListView).children) == []
        empty = app.screen.query_one("#bindings-empty", Static)
        assert empty.display is True
        assert "No slot bindings" in str(empty.render())
        assert app.is_running


async def test_btn_bindings_close_returns_to_tab(store: PromptStore) -> None:
    """``#btn-bindings-close`` pops the screen; the tab reloads behind it."""
    store.create("greeting", "hi")

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.prompt_bindings import PromptBindingsScreen
    from openreview_cli.tui.tabs.prompts import PromptsTab

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await _open_bindings_screen(pilot, app)
        assert isinstance(app.screen, PromptBindingsScreen)

        await pilot.click("#btn-bindings-close")
        await pilot.pause()

        assert not isinstance(app.screen, PromptBindingsScreen)
        assert app.query_one(PromptsTab) is not None
        assert app.is_running


async def test_btn_bind_new_opens_bind_modal(store: PromptStore) -> None:
    """``#btn-bind-new`` opens ``PromptBindModal`` for the opened prompt."""
    store.create("greeting", "hi")

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.prompt_bindings import PromptBindModal

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await _open_bindings_screen(pilot, app)

        await pilot.click("#btn-bind-new")
        await pilot.pause()

        assert isinstance(app.screen, PromptBindModal)
        assert app.is_running


# ── Bind modal ──


async def test_bind_modal_slot_select_holds_the_real_slots(store: PromptStore) -> None:
    """The slot Select is never blank and offers exactly the real slots."""
    store.create("greeting", "hi")

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.prompt_bindings import PromptBindModal

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(PromptBindModal(prompt_name="greeting"))
        await pilot.pause()

        slot_select = app.screen.query_one("#bind-slot", Select)
        # allow_blank=False auto-selects the first option, so it is never blank.
        assert slot_select.is_blank() is False
        assert slot_select.value in VALID_SLOTS
        # Every real slot is a legal option; an illegal value would raise.
        for slot in VALID_SLOTS:
            slot_select.value = slot
            assert slot_select.value == slot
        assert app.is_running


async def test_bind_modal_version_select_blank_and_lists_real_versions(
    store: PromptStore,
) -> None:
    """The version Select starts blank (allow_blank=True) and lists real versions."""
    store.create("greeting", "one")
    store.update("greeting", "two")

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.prompt_bindings import PromptBindModal

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(PromptBindModal(prompt_name="greeting"))
        await pilot.pause()

        version_select = app.screen.query_one("#bind-version", Select)
        assert version_select.is_blank() is True
        for version in (1, 2):
            version_select.value = version
            assert version_select.value == version
        # A version this prompt does not have is not an option.
        with pytest.raises(InvalidSelectValueError):
            version_select.value = 99
        assert app.is_running


async def test_bind_modal_untouched_shows_message_and_calls_no_store(
    store: PromptStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An untouched modal reports the blank state and makes no store call."""
    store.create("greeting", "hi")
    calls: list[Any] = []

    def _boom(*args: Any, **kwargs: Any) -> None:
        calls.append((args, kwargs))
        raise AssertionError("the guard must return before any store call")

    monkeypatch.setattr("openreview_cli.tui.domain.prompts.list_bindings_via_tui", _boom)

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.prompt_bindings import PromptBindModal

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(PromptBindModal(prompt_name="greeting"))
        await pilot.pause()

        await pilot.click("#bind-confirm")
        await pilot.pause()

        rendered = str(app.screen.query_one("#bind-error", Label).render())
        assert rendered == "Choose a slot and a version"
        assert calls == []
        assert isinstance(app.screen, PromptBindModal)
        assert app.is_running


async def test_bind_modal_prompt_with_no_versions_disables_bind(
    store: PromptStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A prompt with no versions disables Bind and says so.

    The schema cannot represent a prompt with zero versions (any prompt row
    implies a version), so this single unreachable state is mocked.
    """
    store.create("greeting", "hi")

    monkeypatch.setattr(
        "openreview_cli.tui.domain.prompts.get_prompt_detail_via_tui",
        lambda name: {
            "found": True,
            "name": name,
            "latest_version": 0,
            "versions": [],
            "content": "",
            "tags": None,
            "description": None,
        },
    )

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.prompt_bindings import PromptBindModal

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(PromptBindModal(prompt_name="greeting"))
        await pilot.pause()

        rendered = str(app.screen.query_one("#bind-error", Label).render())
        assert rendered == "This prompt has no versions"
        assert app.screen.query_one("#bind-confirm", Button).disabled is True
        assert app.is_running


async def test_bind_modal_vanished_prompt_reports_message(store: PromptStore) -> None:
    """A prompt that vanished before the modal opened is reported honestly.

    Resolving first matters: ``store.bind`` misdiagnoses a missing prompt as a
    missing version (``store.py:173``).
    """
    store.create("ghost", "boo")
    store.delete("ghost")

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.prompt_bindings import PromptBindModal

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(PromptBindModal(prompt_name="ghost"))
        await pilot.pause()

        rendered = str(app.screen.query_one("#bind-error", Label).render())
        assert rendered == "Prompt 'ghost' no longer exists"
        assert app.screen.query_one("#bind-confirm", Button).disabled is True
        assert app.is_running


async def test_bind_overwrite_declined_writes_nothing(store: PromptStore) -> None:
    """An already-bound slot requires a danger confirm; declining writes nothing.

    ``#bind-confirm`` is clicked exactly once.  Textual's ``Button._on_click``
    (``_button.py:416``) drops a click while the button carries ``-active``,
    which lasts ``active_effect_duration`` (0.2s, ``_button.py:370``), so a
    second click on the *same* instance is timing-dependent: it lands only if
    the intervening work happens to outlast 0.2s.  The accepted path is its own
    single-click test below rather than a second click here.
    """
    store.create("greeting", "hi")
    store.create("other", "other content")
    store.bind("reasoning", "other", 1)

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.confirm import ConfirmModal
    from openreview_cli.tui.screens.prompt_bindings import PromptBindModal

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("6")
        await pilot.pause()
        await _highlight(pilot, app)
        await pilot.click("#btn-bind-prompt")
        await pilot.pause()

        assert isinstance(app.screen, PromptBindModal)
        app.screen.query_one("#bind-slot", Select).value = "reasoning"
        app.screen.query_one("#bind-version", Select).value = 1
        await pilot.pause()

        # One click: the modal pushes a danger confirm rather than dismissing.
        await pilot.click("#bind-confirm")
        await pilot.pause()

        assert isinstance(app.screen, ConfirmModal)
        rendered = str(app.screen.query_one("#confirm-message", Label).render())
        assert rendered == "Slot 'reasoning' is currently bound to other:v1. Replace it?"

        # Decline: stay in the modal and write nothing.
        await pilot.click("#no")
        await pilot.pause()
        assert isinstance(app.screen, PromptBindModal)
        assert {binding.slot: binding.prompt_name for binding in store.bindings()} == {
            "reasoning": "other"
        }
        assert app.is_running


async def test_bind_overwrite_accepted_writes_new_binding(store: PromptStore) -> None:
    """The overwrite confirm dismissed on Yes hands the write to the tab caller.

    ``#bind-confirm`` is clicked exactly once, for the reason given on the
    declined sibling above.
    """
    store.create("greeting", "hi")
    store.create("other", "other content")
    store.bind("reasoning", "other", 1)

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.confirm import ConfirmModal
    from openreview_cli.tui.screens.prompt_bindings import PromptBindModal

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("6")
        await pilot.pause()
        await _highlight(pilot, app)
        await pilot.click("#btn-bind-prompt")
        await pilot.pause()

        assert isinstance(app.screen, PromptBindModal)
        app.screen.query_one("#bind-slot", Select).value = "reasoning"
        app.screen.query_one("#bind-version", Select).value = 1
        await pilot.pause()

        # One click: the modal pushes a danger confirm rather than dismissing.
        await pilot.click("#bind-confirm")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmModal)

        # Confirm: dismiss with the payload; the tab caller performs the write.
        await pilot.click("#yes")
        await pilot.pause()
        assert app.is_running

    bindings = {b.slot: (b.prompt_name, b.prompt_version) for b in store.bindings()}
    assert bindings["reasoning"] == ("greeting", 1)


# ── Unbind ──


async def test_unbind_row_confirms_naming_prompt_and_version_and_removes_row(
    store: PromptStore,
) -> None:
    """A per-row Unbind confirms with prompt and version, then removes the row."""
    store.create("greeting", "hi")
    store.bind("reasoning", "greeting", 1)

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.confirm import ConfirmModal
    from openreview_cli.tui.screens.prompt_bindings import PromptBindingsScreen

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await _open_bindings_screen(pilot, app)
        assert isinstance(app.screen, PromptBindingsScreen)
        assert len(app.screen.query_one("#bindings-list", ListView).children) == 1

        await pilot.click("#btn-unbind-reasoning")
        await pilot.pause()

        assert isinstance(app.screen, ConfirmModal)
        rendered = str(app.screen.query_one("#confirm-message", Label).render())
        assert "reasoning" in rendered
        assert "greeting" in rendered
        assert "v1" in rendered

        await pilot.click("#yes")
        await pilot.pause()

        assert isinstance(app.screen, PromptBindingsScreen)
        assert list(app.screen.query_one("#bindings-list", ListView).children) == []
        assert app.is_running

    assert store.bindings() == []


async def test_unbind_vanished_binding_reports_store_message(store: PromptStore) -> None:
    """An unbind whose binding vanished surfaces the store's message, not a crash."""
    store.create("greeting", "hi")
    store.bind("reasoning", "greeting", 1)

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.prompt_bindings import PromptBindingsScreen

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await _open_bindings_screen(pilot, app)
        assert isinstance(app.screen, PromptBindingsScreen)

        # The binding disappears between render and confirm.
        store.unbind("reasoning")

        notifications: list[tuple[str, dict[str, Any]]] = []
        app.notify = lambda msg, **kw: notifications.append((msg, kw))  # type: ignore[method-assign]

        await pilot.click("#btn-unbind-reasoning")
        await pilot.pause()
        await pilot.click("#yes")
        await pilot.pause()

        assert app.is_running
        assert any("No binding exists for slot" in msg for msg, _ in notifications)
