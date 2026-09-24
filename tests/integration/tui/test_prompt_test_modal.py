"""Integration tests for PromptTestModal (Task 7).

Drives the REAL ``OpenReviewApp`` and the REAL ``PromptStore`` over the
per-test isolated XDG data directory materialized by ``isolated_xdg`` — no
data mocks — mirroring ``test_prompts_tab.py``.

The modal is pushed exactly the way the tab pushes it
(``tabs/prompts.py:275-283``): ``PromptTestModal(prompt_name=..., latest_version=...)``
with **no** result callback.

The no-dispatch proof is real rather than vacuous: importing
``openreview_cli.gateway.router`` (which pulls in ``litellm``) is test
scaffolding, so the ``sys.modules`` snapshot is taken *after* that import and
before the modal opens, and the assertion measures only what the modal's own
lifetime adds.  ``Gateway.chat`` is patched to record-and-raise, and the test
asserts it is never called.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest
from textual.widgets import Input, Label, Static

from openreview_cli.prompts.store import PromptStore

# ── Fixtures / helpers ──


@pytest.fixture
def store(isolated_xdg: dict[str, Path]) -> PromptStore:
    """A real PromptStore bound to the isolated per-test database."""
    s = PromptStore(isolated_xdg["db_path"])
    s.init()
    return s


def _text(widget: Label | Static) -> str:
    """The visible text of a Label/Static, markup already resolved."""
    return str(widget.render())


def _gateway_modules() -> set[str]:
    """Every gateway/litellm module currently imported into ``sys.modules``."""
    return {
        name
        for name in sys.modules
        if name == "litellm"
        or name.startswith("litellm.")
        or name == "openreview_cli.gateway"
        or name.startswith("openreview_cli.gateway.")
    }


# ── Default value ──


async def test_versions_input_defaults_to_latest(store: PromptStore) -> None:
    """The versions input starts at the prompt's latest version."""
    store.create("greeting", "one")
    store.update("greeting", "two")

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.prompt_test import PromptTestModal

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(PromptTestModal(prompt_name="greeting", latest_version=2))
        await pilot.pause()

        assert isinstance(app.screen, PromptTestModal)
        assert app.screen.query_one("#prompt-test-versions", Input).value == "2"
        assert app.is_running


# ── Malformed version lists ──


@pytest.mark.parametrize("raw", ["abc", "1,", "1 2", ""])
async def test_malformed_versions_show_parse_error_and_do_not_dismiss(
    store: PromptStore,
    raw: str,
) -> None:
    """Every malformed list is rejected inline, without dismissing."""
    store.create("greeting", "one")

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.prompt_test import PromptTestModal

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(PromptTestModal(prompt_name="greeting", latest_version=1))
        await pilot.pause()

        modal = app.screen
        assert isinstance(modal, PromptTestModal)

        modal.query_one("#prompt-test-versions", Input).value = raw
        await pilot.click("#prompt-test-run")
        await pilot.pause()

        assert _text(modal.query_one("#prompt-test-error", Label)) == (
            "Versions must be comma-separated version numbers"
        )
        # Inline error: the modal stays mounted and the app keeps running.
        assert isinstance(app.screen, PromptTestModal)
        assert app.is_running


# ── Store validation ──


async def test_unknown_version_shows_store_message_inline(store: PromptStore) -> None:
    """An unknown version surfaces the store's own message, inline."""
    store.create("greeting", "one")

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.prompt_test import PromptTestModal

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(PromptTestModal(prompt_name="greeting", latest_version=1))
        await pilot.pause()

        modal = app.screen
        assert isinstance(modal, PromptTestModal)

        modal.query_one("#prompt-test-versions", Input).value = "99"
        await pilot.click("#prompt-test-run")
        await pilot.pause()

        message = _text(modal.query_one("#prompt-test-error", Label))
        assert "version 99 not found" in message
        assert isinstance(app.screen, PromptTestModal)
        assert app.is_running


async def test_valid_entry_shows_roadmap_notice(store: PromptStore) -> None:
    """A valid entry clears the error and shows the roadmap notice."""
    store.create("greeting", "one")
    store.update("greeting", "two")

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.prompt_test import PromptTestModal

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(PromptTestModal(prompt_name="greeting", latest_version=2))
        await pilot.pause()

        modal = app.screen
        assert isinstance(modal, PromptTestModal)

        modal.query_one("#prompt-test-versions", Input).value = "1,2"
        await pilot.click("#prompt-test-run")
        await pilot.pause()

        notice = _text(modal.query_one("#prompt-test-notice", Static))
        assert "benchmark harness" in notice
        assert "roadmap N-3" in notice
        assert _text(modal.query_one("#prompt-test-error", Label)) == ""
        assert isinstance(app.screen, PromptTestModal)
        assert app.is_running


# ── The no-dispatch proof ──


async def test_valid_entry_never_dispatches_a_model(
    store: PromptStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The happy path must not call ``Gateway.chat`` nor import the gateway."""
    store.create("greeting", "one")
    store.update("greeting", "two")

    # Test scaffolding: importing the router pulls in litellm.  The snapshot
    # below is taken *after* this so the assertion measures only the modal.
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
        await pilot.pause()
        before = _gateway_modules()

        app.push_screen(PromptTestModal(prompt_name="greeting", latest_version=2))
        await pilot.pause()

        modal = app.screen
        assert isinstance(modal, PromptTestModal)

        await pilot.click("#prompt-test-run")
        await pilot.pause()

        # The honest notice is shown; the app is still up.
        assert "roadmap N-3" in _text(modal.query_one("#prompt-test-notice", Static))
        assert app.is_running

        new_modules = _gateway_modules() - before

    # No model was dispatched...
    assert dispatched == []
    # ...and the modal's own lifetime imported no gateway/litellm module.
    assert new_modules == set()


# ── Error containment / affordances ──


async def test_wrapper_error_is_inline_and_app_survives(
    store: PromptStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A wrapper ``ValueError`` becomes an inline error, never a crash."""
    store.create("greeting", "one")

    def _boom(name: str, versions: list[int]) -> None:
        raise ValueError("store exploded")

    monkeypatch.setattr(
        "openreview_cli.tui.domain.prompts.validate_prompt_test_via_tui",
        _boom,
    )

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.prompt_test import PromptTestModal

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(PromptTestModal(prompt_name="greeting", latest_version=1))
        await pilot.pause()

        modal = app.screen
        assert isinstance(modal, PromptTestModal)

        await pilot.click("#prompt-test-run")
        await pilot.pause()

        assert "store exploded" in _text(modal.query_one("#prompt-test-error", Label))
        assert isinstance(app.screen, PromptTestModal)
        assert app.is_running


async def test_cancel_dismisses_modal(store: PromptStore) -> None:
    """``#prompt-test-cancel`` closes the modal."""
    store.create("greeting", "one")

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.prompt_test import PromptTestModal

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(PromptTestModal(prompt_name="greeting", latest_version=1))
        await pilot.pause()
        assert isinstance(app.screen, PromptTestModal)

        await pilot.click("#prompt-test-cancel")
        await pilot.pause()

        assert not isinstance(app.screen, PromptTestModal)
        assert app.is_running


async def test_title_renders_prompt_name_literally(store: PromptStore) -> None:
    """The title renders bracketed prompt names verbatim (markup=False)."""
    name = "notes [clause]"
    store.create(name, "body")

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.prompt_test import PromptTestModal

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(PromptTestModal(prompt_name=name, latest_version=1))
        await pilot.pause()

        modal = app.screen
        assert isinstance(modal, PromptTestModal)

        assert name in _text(modal.query_one("#prompt-test-title", Label))
        assert app.is_running
