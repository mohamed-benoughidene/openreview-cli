"""Integration tests for PromptFormScreen (Task 5).

Drives the REAL ``OpenReviewApp`` over the per-test isolated XDG data directory
(``isolated_xdg``) so the app's mounted tabs never touch the developer's real
data directory.

The form is input-only by contract: it dismisses with the field dict and the
*caller* performs the store write.  These tests therefore assert the dismissed
payload, never a database effect, and one test pins the boundary by making the
create/update wrappers explode and proving they are never reached.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from textual.widgets import Input, Label, TextArea

# More than the store's 16384 limit (bytes on create, characters on update).
OVERSIZE_BODY = "x" * 20000


def _push_form(app: Any, screen: Any, results: list[Any]) -> None:
    """Push ``screen`` and record its dismiss result in ``results``."""

    def on_result(result: Any) -> None:
        results.append(result)

    app.push_screen(screen, on_result)


# ── Create mode: validation ──


async def test_create_mode_empty_name_shows_required_and_does_not_dismiss(
    isolated_xdg: dict[str, Path],
) -> None:
    """An empty name is refused with ``Name is required``; the form stays open."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.prompt_form import PromptFormScreen

    app = OpenReviewApp()
    results: list[Any] = []

    async with app.run_test(size=(120, 40)) as pilot:
        _push_form(app, PromptFormScreen(), results)
        await pilot.pause()

        await pilot.click("#prompt-save")
        await pilot.pause()

        assert results == []  # not dismissed
        error = str(app.screen.query_one("#prompt-form-error", Label).render())
        assert error == "Name is required"
        assert app.is_running


async def test_create_mode_empty_content_shows_required_and_does_not_dismiss(
    isolated_xdg: dict[str, Path],
) -> None:
    """A non-empty name with empty content is refused with ``Content is required``."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.prompt_form import PromptFormScreen

    app = OpenReviewApp()
    results: list[Any] = []

    async with app.run_test(size=(120, 40)) as pilot:
        _push_form(app, PromptFormScreen(), results)
        await pilot.pause()

        app.screen.query_one("#prompt-form-name", Input).value = "greeting"
        await pilot.click("#prompt-save")
        await pilot.pause()

        assert results == []
        error = str(app.screen.query_one("#prompt-form-error", Label).render())
        assert error == "Content is required"
        assert app.is_running


# ── Create mode: submission ──


async def test_create_mode_valid_submission_dismisses_with_dict(
    isolated_xdg: dict[str, Path],
) -> None:
    """A complete form dismisses with exactly the four contract keys."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.prompt_form import PromptFormScreen

    app = OpenReviewApp()
    results: list[Any] = []

    async with app.run_test(size=(120, 40)) as pilot:
        _push_form(app, PromptFormScreen(), results)
        await pilot.pause()

        form = app.screen
        form.query_one("#prompt-form-name", Input).value = "greeting"
        form.query_one("#prompt-form-content", TextArea).text = "hello world"
        form.query_one("#prompt-form-tags", Input).value = "a, b"
        form.query_one("#prompt-form-description", Input).value = "a greeting"

        await pilot.click("#prompt-save")
        await pilot.pause()

        assert results == [
            {
                "name": "greeting",
                "content": "hello world",
                "tags": ["a", "b"],
                "description": "a greeting",
            }
        ]
        assert app.is_running


async def test_enter_submits_from_a_single_line_field(
    isolated_xdg: dict[str, Path],
) -> None:
    """``on_key`` enter submits the form."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.prompt_form import PromptFormScreen

    app = OpenReviewApp()
    results: list[Any] = []

    async with app.run_test(size=(120, 40)) as pilot:
        _push_form(app, PromptFormScreen(), results)
        await pilot.pause()

        form = app.screen
        form.query_one("#prompt-form-name", Input).value = "greeting"
        form.query_one("#prompt-form-content", TextArea).text = "hi"
        form.query_one("#prompt-form-name", Input).focus()
        await pilot.pause()

        await pilot.press("enter")
        await pilot.pause()

        assert len(results) == 1
        assert results[0]["name"] == "greeting"
        assert results[0]["content"] == "hi"
        assert app.is_running


# ── Edit mode ──


async def test_edit_mode_name_is_disabled_and_prefilled(
    isolated_xdg: dict[str, Path],
) -> None:
    """Edit mode prefills every field and locks the name."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.prompt_form import PromptFormScreen

    app = OpenReviewApp()
    results: list[Any] = []

    async with app.run_test(size=(120, 40)) as pilot:
        _push_form(
            app,
            PromptFormScreen(
                name="greeting",
                content="hello there",
                tags=["a", "b"],
                description="a greeting",
            ),
            results,
        )
        await pilot.pause()

        form = app.screen
        name_input = form.query_one("#prompt-form-name", Input)
        assert name_input.value == "greeting"
        assert name_input.disabled
        assert form.query_one("#prompt-form-content", TextArea).text == "hello there"
        assert form.query_one("#prompt-form-tags", Input).value == "a, b"
        assert form.query_one("#prompt-form-description", Input).value == "a greeting"
        assert app.is_running


async def test_edit_mode_submission_keeps_the_locked_name(
    isolated_xdg: dict[str, Path],
) -> None:
    """Saving an edit returns the prefilled name with the edited content."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.prompt_form import PromptFormScreen

    app = OpenReviewApp()
    results: list[Any] = []

    async with app.run_test(size=(120, 40)) as pilot:
        _push_form(app, PromptFormScreen(name="greeting", content="old"), results)
        await pilot.pause()

        form = app.screen
        form.query_one("#prompt-form-content", TextArea).text = "new content"
        await pilot.click("#prompt-save")
        await pilot.pause()

        assert len(results) == 1
        assert results[0]["name"] == "greeting"
        assert results[0]["content"] == "new content"
        assert app.is_running


# ── Cancellation ──


async def test_escape_dismisses_none(isolated_xdg: dict[str, Path]) -> None:
    """Escape cancels the form with ``None``."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.prompt_form import PromptFormScreen

    app = OpenReviewApp()
    results: list[Any] = []

    async with app.run_test(size=(120, 40)) as pilot:
        _push_form(app, PromptFormScreen(name="greeting", content="body"), results)
        await pilot.pause()

        await pilot.press("escape")
        await pilot.pause()

        assert results == [None]
        assert app.is_running


async def test_cancel_button_dismisses_none(isolated_xdg: dict[str, Path]) -> None:
    """The visible Cancel button cancels the form with ``None``."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.prompt_form import PromptFormScreen

    app = OpenReviewApp()
    results: list[Any] = []

    async with app.run_test(size=(120, 40)) as pilot:
        _push_form(app, PromptFormScreen(), results)
        await pilot.pause()

        await pilot.click("#prompt-cancel")
        await pilot.pause()

        assert results == [None]
        assert app.is_running


# ── Markup safety ──


async def test_bracketed_prompt_name_renders_literally(
    isolated_xdg: dict[str, Path],
) -> None:
    """A lowercase-bracketed name survives rendering; Rich would eat ``[clause]``.

    ``Text.from_markup("[clause] Test")`` silently drops the bracketed token, so
    a markup-enabled label would show a corrupted name.  The assertion is on the
    *rendered* label, which proves the markup was not consumed.
    """
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.prompt_form import PromptFormScreen

    app = OpenReviewApp()
    results: list[Any] = []

    async with app.run_test(size=(120, 40)) as pilot:
        _push_form(app, PromptFormScreen(name="[clause] Test", content="body"), results)
        await pilot.pause()

        rendered = str(app.screen.query_one("#prompt-form-title", Label).render())
        assert "[clause] Test" in rendered
        assert rendered == "Edit prompt: [clause] Test"
        assert app.screen.query_one("#prompt-form-name", Input).value == "[clause] Test"
        assert app.is_running


# ── Boundary: the form never writes, and never enforces a size limit ──


async def test_form_never_writes_to_the_store(
    isolated_xdg: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The caller owns the store write; the form must not reach the domain layer.

    The pinned contract says the caller runs ``create_prompt_via_tui`` /
    ``update_prompt_via_tui`` and reports failures.  Both wrappers are replaced
    with a bomb: if the form ever called one, the exception would fire inside a
    Textual handler and the run would fail rather than dismiss.
    """
    calls: list[str] = []

    def _boom(*args: Any, **kwargs: Any) -> None:
        calls.append("called")
        raise AssertionError("PromptFormScreen must not write to the store")

    monkeypatch.setattr("openreview_cli.tui.domain.prompts.create_prompt_via_tui", _boom)
    monkeypatch.setattr("openreview_cli.tui.domain.prompts.update_prompt_via_tui", _boom)

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.prompt_form import PromptFormScreen

    app = OpenReviewApp()
    results: list[Any] = []

    async with app.run_test(size=(120, 40)) as pilot:
        _push_form(app, PromptFormScreen(), results)
        await pilot.pause()

        form = app.screen
        form.query_one("#prompt-form-name", Input).value = "greeting"
        form.query_one("#prompt-form-content", TextArea).text = "hello"
        await pilot.click("#prompt-save")
        await pilot.pause()

        assert calls == []
        assert len(results) == 1
        assert results[0]["name"] == "greeting"
        assert app.is_running


async def test_form_does_not_enforce_a_size_limit(
    isolated_xdg: dict[str, Path],
) -> None:
    """A >16384-byte body is passed through untouched; the store owns the rule."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.prompt_form import PromptFormScreen

    app = OpenReviewApp()
    results: list[Any] = []

    async with app.run_test(size=(120, 40)) as pilot:
        _push_form(app, PromptFormScreen(), results)
        await pilot.pause()

        form = app.screen
        form.query_one("#prompt-form-name", Input).value = "huge"
        form.query_one("#prompt-form-content", TextArea).text = OVERSIZE_BODY
        await pilot.click("#prompt-save")
        await pilot.pause()

        assert len(results) == 1
        assert results[0]["content"] == OVERSIZE_BODY
        assert len(results[0]["content"].encode("utf-8")) > 16384
        assert app.is_running
