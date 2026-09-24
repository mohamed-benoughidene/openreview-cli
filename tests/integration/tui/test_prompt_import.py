"""Integration tests for PromptImportModal (Task 9).

Drives the REAL ``OpenReviewApp`` and a REAL ``PromptStore`` over the per-test
isolated XDG data directory materialized by ``isolated_xdg`` — no data mocks —
using ``tmp_path`` for the import files.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.widgets import Button, Input, Static

from openreview_cli.prompts.store import PromptStore


@pytest.fixture
def store(isolated_xdg: dict[str, Path]) -> PromptStore:
    """A real PromptStore bound to the isolated per-test database."""
    s = PromptStore(isolated_xdg["db_path"])
    s.init()
    return s


def _yaml(*items: tuple[str, list[str]]) -> str:
    """Build a valid multi-prompt document (every version carries created_at)."""
    lines: list[str] = []
    for name, contents in items:
        lines.append(f"- name: {name}")
        lines.append("  versions:")
        for index, content in enumerate(contents, start=1):
            lines.append(f"    - version: {index}")
            lines.append(f"      content: {content}")
            lines.append("      created_at: 2026-01-01T00:00:00Z")
    return "\n".join(lines) + "\n"


def _preview_text(app: object) -> str:
    return str(app.screen.query_one("#import-preview", Static).render())  # type: ignore[attr-defined]


def _result_text(app: object) -> str:
    return str(app.screen.query_one("#import-result", Static).render())  # type: ignore[attr-defined]


async def test_preview_shows_names_version_counts_and_existing_tally(
    store: PromptStore, tmp_path: Path
) -> None:
    """The live preview lists names, version counts and the new/existing tally."""
    store.create("e1", "existing one")
    store.create("e2", "existing two")
    path = tmp_path / "prompts.yaml"
    path.write_text(
        _yaml(
            ("n1", ["a", "b"]),
            ("n2", ["c"]),
            ("n3", ["d"]),
            ("e1", ["x"]),
            ("e2", ["y"]),
        )
    )

    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        from openreview_cli.tui.screens.prompt_import import PromptImportModal

        app.push_screen(PromptImportModal())
        await pilot.pause()
        app.screen.query_one("#import-path-input", Input).value = str(path)
        await pilot.pause()

        text = _preview_text(app)
        assert "n1: 2 version(s)" in text
        assert "n2: 1 version(s)" in text
        assert "3 new, 2 already exist" in text
        assert app.screen.query_one("#btn-import-confirm", Button).display is True
        assert app.is_running


async def test_preview_validates_through_the_shared_parser(
    store: PromptStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The preview and the import resolve the very same parse_prompts_yaml."""
    import openreview_cli.prompts.io as io_mod
    import openreview_cli.tui.domain.prompts as domain_mod

    calls: list[str] = []
    real = io_mod.parse_prompts_yaml

    def _spy(text: str) -> list[dict[str, object]]:
        calls.append(text)
        return real(text)

    monkeypatch.setattr(io_mod, "parse_prompts_yaml", _spy)
    # The domain wrapper bound the same function object at import time.
    assert domain_mod.parse_prompts_yaml is real

    path = tmp_path / "prompts.yaml"
    path.write_text(_yaml(("a", ["x"])))

    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        from openreview_cli.tui.screens.prompt_import import PromptImportModal

        app.push_screen(PromptImportModal())
        await pilot.pause()
        app.screen.query_one("#import-path-input", Input).value = str(path)
        await pilot.pause()

        assert calls  # the preview went through the shared parser
        assert app.is_running


async def test_import_button_hidden_until_a_file_validates(
    store: PromptStore, tmp_path: Path
) -> None:
    """Import starts hidden and stays hidden for a path that does not resolve."""
    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        from openreview_cli.tui.screens.prompt_import import PromptImportModal

        app.push_screen(PromptImportModal())
        await pilot.pause()
        assert app.screen.query_one("#btn-import-confirm", Button).display is False

        app.screen.query_one("#import-path-input", Input).value = str(tmp_path / "nope.yaml")
        await pilot.pause()
        assert app.screen.query_one("#btn-import-confirm", Button).display is False
        assert app.is_running


MALFORMED_CASES = [
    ("scalar", "just a scalar\n", "mapping or a list"),
    (
        "item-without-name",
        "- versions:\n    - version: 1\n      content: x\n      created_at: t\n",
        "missing 'name'",
    ),
    ("versions-null", "name: a\nversions: null\n", "null 'versions'"),
    (
        "version-without-content",
        "name: a\nversions:\n  - version: 1\n    created_at: t\n",
        "missing 'content'",
    ),
    (
        "version-without-created-at",
        "name: a\nversions:\n  - version: 1\n    content: x\n",
        "missing 'created_at'",
    ),
    (
        "duplicate-version",
        "name: a\nversions:\n  - version: 1\n    content: x\n    created_at: t\n"
        "  - version: 1\n    content: y\n    created_at: t\n",
        "duplicate version 1",
    ),
    ("empty-versions", "name: a\nversions: []\n", "empty 'versions' list"),
]


@pytest.mark.parametrize(("label", "document", "fragment"), MALFORMED_CASES)
async def test_malformed_document_is_refused_in_preview(
    store: PromptStore,
    tmp_path: Path,
    label: str,
    document: str,
    fragment: str,
) -> None:
    """Every malformed document is refused in the preview; the store is untouched."""
    path = tmp_path / f"{label}.yaml"
    path.write_text(document)

    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        from openreview_cli.tui.screens.prompt_import import PromptImportModal

        app.push_screen(PromptImportModal())
        await pilot.pause()
        app.screen.query_one("#import-path-input", Input).value = str(path)
        await pilot.pause()

        text = _preview_text(app)
        assert "Validation error" in text
        assert fragment in text
        assert app.screen.query_one("#btn-import-confirm", Button).display is False
        assert app.is_running

    assert [p.name for p in store.list()] == []


async def test_valid_file_imports_and_reports_landed_names(
    store: PromptStore, tmp_path: Path
) -> None:
    """A valid file imports and reports exactly the names that landed."""
    path = tmp_path / "prompts.yaml"
    path.write_text(_yaml(("a", ["alpha"]), ("b", ["beta"])))

    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    closed: list[object] = []

    def on_close(result: object) -> None:
        closed.append(result)

    async with app.run_test(size=(120, 40)) as pilot:
        from openreview_cli.tui.screens.prompt_import import PromptImportModal

        app.push_screen(PromptImportModal(), on_close)
        await pilot.pause()
        app.screen.query_one("#import-path-input", Input).value = str(path)
        await pilot.pause()

        await pilot.click("#btn-import-confirm")
        await pilot.pause()

        assert _result_text(app) == "Imported 2 of 2: a, b."
        assert app.is_running

        await pilot.click("#btn-import-close")
        await pilot.pause()

    assert sorted(p.name for p in store.list()) == ["a", "b"]
    assert closed == [None]


async def test_partial_import_reports_landed_and_skipped(
    store: PromptStore, tmp_path: Path
) -> None:
    """A duplicate item is reported; the items before it are still committed."""
    store.create("c", "already here")
    path = tmp_path / "prompts.yaml"
    path.write_text(_yaml(("a", ["alpha"]), ("b", ["beta"]), ("c", ["gamma"])))

    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        from openreview_cli.tui.screens.prompt_import import PromptImportModal

        app.push_screen(PromptImportModal())
        await pilot.pause()
        app.screen.query_one("#import-path-input", Input).value = str(path)
        await pilot.pause()

        await pilot.click("#btn-import-confirm")
        await pilot.pause()

        assert _result_text(app) == (
            "Imported 2 of 3: a, b. Not imported: c (Prompt 'c' already exists)."
        )
        assert app.is_running

    assert sorted(p.name for p in store.list()) == ["a", "b", "c"]


async def test_store_exception_during_import_leaves_app_running(
    store: PromptStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A store failure during import is reported, never fatal."""
    import sqlite3

    path = tmp_path / "prompts.yaml"
    path.write_text(_yaml(("a", ["alpha"])))

    def _boom(_path: Path) -> dict[str, object]:
        raise sqlite3.IntegrityError("boom")

    monkeypatch.setattr("openreview_cli.tui.domain.prompts.import_prompts_via_tui", _boom)

    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    notifications: list[tuple[str, dict[str, object]]] = []
    async with app.run_test(size=(120, 40)) as pilot:
        from openreview_cli.tui.screens.prompt_import import PromptImportModal

        app.push_screen(PromptImportModal())
        await pilot.pause()
        app.screen.query_one("#import-path-input", Input).value = str(path)
        await pilot.pause()

        app.notify = lambda msg, **kw: notifications.append((msg, kw))  # type: ignore[method-assign]
        await pilot.click("#btn-import-confirm")
        await pilot.pause()

        assert app.is_running
        assert "Import failed" in _result_text(app)
        assert any("Import failed" in msg for msg, _ in notifications)

    assert [p.name for p in store.list()] == []


async def test_import_button_is_disabled_while_running(
    store: PromptStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The Import button is disabled before the import runs."""
    path = tmp_path / "prompts.yaml"
    path.write_text(_yaml(("a", ["alpha"])))

    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    seen: dict[str, object] = {}

    def _record(_path: Path) -> dict[str, object]:
        seen["disabled"] = app.screen.query_one("#btn-import-confirm", Button).disabled
        seen["calls"] = int(seen.get("calls", 0)) + 1
        return {"imported": ["a"], "failed": {}}

    monkeypatch.setattr("openreview_cli.tui.domain.prompts.import_prompts_via_tui", _record)

    async with app.run_test(size=(120, 40)) as pilot:
        from openreview_cli.tui.screens.prompt_import import PromptImportModal

        app.push_screen(PromptImportModal())
        await pilot.pause()
        app.screen.query_one("#import-path-input", Input).value = str(path)
        await pilot.pause()

        await pilot.click("#btn-import-confirm")
        await pilot.pause()

        assert seen["disabled"] is True
        assert seen["calls"] == 1
        assert app.is_running
