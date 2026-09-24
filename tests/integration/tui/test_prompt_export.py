"""Integration tests for PromptExportModal (Task 8).

Drives the REAL ``OpenReviewApp`` and a REAL ``PromptStore`` over the per-test
isolated XDG data directory materialized by ``isolated_xdg`` — no data mocks —
using ``tmp_path`` for the export destinations.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.widgets import Button, Input, Label

from openreview_cli.prompts.io import parse_prompts_yaml
from openreview_cli.prompts.store import PromptStore


@pytest.fixture
def store(isolated_xdg: dict[str, Path]) -> PromptStore:
    """A real PromptStore bound to the isolated per-test database."""
    s = PromptStore(isolated_xdg["db_path"])
    s.init()
    return s


async def test_export_writes_file_that_parses_back_to_every_version(
    store: PromptStore, tmp_path: Path
) -> None:
    """Exporting one prompt writes a YAML file every version parses back from."""
    store.create("greeting", "hello one")
    store.update("greeting", "hello two")
    dest = tmp_path / "greeting.yaml"

    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        from openreview_cli.tui.screens.prompt_export import PromptExportModal

        app.push_screen(PromptExportModal(prompt_name="greeting"))
        await pilot.pause()
        app.screen.query_one("#export-path", Input).value = str(dest)
        await pilot.pause()

        await pilot.click("#btn-export-confirm")
        await pilot.pause()

        assert app.is_running

    assert dest.exists()
    parsed = parse_prompts_yaml(dest.read_text())
    assert len(parsed) == 1
    assert parsed[0]["name"] == "greeting"
    assert {int(v["version"]) for v in parsed[0]["versions"]} == {1, 2}


async def test_export_modal_states_its_scope(store: PromptStore) -> None:
    """The modal says it exports one prompt and names it, rendered literally."""
    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        from openreview_cli.tui.screens.prompt_export import PromptExportModal

        # Lowercase brackets: Rich would consume them as markup if not disabled.
        app.push_screen(PromptExportModal(prompt_name="notes [clause]"))
        await pilot.pause()
        rendered = str(app.screen.query_one("#export-scope", Label).render())

    assert "one prompt" in rendered
    assert "notes [clause]" in rendered


async def test_existing_destination_requires_danger_confirm_and_decline_is_identical(
    store: PromptStore, tmp_path: Path
) -> None:
    """An existing file needs a danger confirm; declining leaves it byte-identical."""
    dest = tmp_path / "existing.yaml"
    original = b"name: keep\nversions:\n  - version: 1\n    content: x\n    created_at: t\n"
    dest.write_bytes(original)

    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        from openreview_cli.tui.screens.confirm import ConfirmModal
        from openreview_cli.tui.screens.prompt_export import PromptExportModal

        app.push_screen(PromptExportModal(prompt_name="greeting"))
        await pilot.pause()
        app.screen.query_one("#export-path", Input).value = str(dest)
        await pilot.pause()

        await pilot.click("#btn-export-confirm")
        await pilot.pause()

        assert isinstance(app.screen, ConfirmModal)
        assert app.screen.query_one("#yes", Button).variant == "error"

        await pilot.click("#no")
        await pilot.pause()

        assert isinstance(app.screen, PromptExportModal)
        assert app.is_running

    assert dest.read_bytes() == original


async def test_directory_target_is_refused(store: PromptStore, tmp_path: Path) -> None:
    """A destination that is a directory is refused with a clear message."""
    target = tmp_path / "out.yaml"
    target.mkdir()

    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        from openreview_cli.tui.screens.prompt_export import PromptExportModal

        app.push_screen(PromptExportModal(prompt_name="greeting"))
        await pilot.pause()
        app.screen.query_one("#export-path", Input).value = str(target)
        await pilot.pause()

        await pilot.click("#btn-export-confirm")
        await pilot.pause()

        error = str(app.screen.query_one("#export-error", Label).render())
        assert "directory" in error.lower()
        assert app.is_running

    assert target.is_dir()
    assert list(target.iterdir()) == []


async def test_missing_parent_directory_is_created(store: PromptStore, tmp_path: Path) -> None:
    """A destination under a missing parent gets that parent created."""
    dest = tmp_path / "nested" / "deeper" / "out.yaml"
    assert not dest.parent.exists()
    store.create("greeting", "hi")

    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        from openreview_cli.tui.screens.prompt_export import PromptExportModal

        app.push_screen(PromptExportModal(prompt_name="greeting"))
        await pilot.pause()
        app.screen.query_one("#export-path", Input).value = str(dest)
        await pilot.pause()

        await pilot.click("#btn-export-confirm")
        await pilot.pause()

        assert app.is_running

    assert dest.exists()
    assert dest.parent.is_dir()


async def test_non_yaml_suffix_is_refused(store: PromptStore, tmp_path: Path) -> None:
    """A destination that is not .yaml/.yml is refused before any write."""
    dest = tmp_path / "out.txt"

    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        from openreview_cli.tui.screens.prompt_export import PromptExportModal

        app.push_screen(PromptExportModal(prompt_name="greeting"))
        await pilot.pause()
        app.screen.query_one("#export-path", Input).value = str(dest)
        await pilot.pause()

        await pilot.click("#btn-export-confirm")
        await pilot.pause()

        error = str(app.screen.query_one("#export-error", Label).render())
        assert ".yaml or .yml" in error
        assert app.is_running

    assert not dest.exists()


async def test_permission_error_is_reported_and_app_stays_running(
    store: PromptStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A filesystem failure is reported through notify, never fatal."""
    dest = tmp_path / "out.yaml"

    def _boom(_dest: Path, _name: str) -> None:
        raise PermissionError("denied")

    monkeypatch.setattr("openreview_cli.tui.domain.prompts.export_prompt_via_tui", _boom)

    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    notifications: list[tuple[str, dict[str, object]]] = []
    async with app.run_test(size=(120, 40)) as pilot:
        from openreview_cli.tui.screens.prompt_export import PromptExportModal

        app.push_screen(PromptExportModal(prompt_name="greeting"))
        await pilot.pause()
        app.screen.query_one("#export-path", Input).value = str(dest)
        await pilot.pause()

        app.notify = lambda msg, **kw: notifications.append((msg, kw))  # type: ignore[method-assign]
        await pilot.click("#btn-export-confirm")
        await pilot.pause()

        assert app.is_running
        assert any("Export failed" in msg for msg, _ in notifications)

    assert not dest.exists()


async def test_export_button_is_disabled_while_writing(
    store: PromptStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The confirm button is disabled before the write, so a double click cannot write twice."""
    dest = tmp_path / "out.yaml"

    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    seen: dict[str, object] = {}

    def _record(d: Path, _name: str) -> None:
        seen["disabled"] = app.screen.query_one("#btn-export-confirm", Button).disabled
        seen["calls"] = int(seen.get("calls", 0)) + 1
        d.write_text(
            "name: greeting\nversions:\n  - version: 1\n    content: x\n    created_at: t\n"
        )

    monkeypatch.setattr("openreview_cli.tui.domain.prompts.export_prompt_via_tui", _record)

    async with app.run_test(size=(120, 40)) as pilot:
        from openreview_cli.tui.screens.prompt_export import PromptExportModal

        app.push_screen(PromptExportModal(prompt_name="greeting"))
        await pilot.pause()
        app.screen.query_one("#export-path", Input).value = str(dest)
        await pilot.pause()

        await pilot.click("#btn-export-confirm")
        await pilot.pause()

    assert seen["disabled"] is True
    assert seen["calls"] == 1
