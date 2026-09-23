"""Integration tests for the stored-PII screen (view + confirmed delete).

These drive real rows through a real temp database (the ``isolated_xdg``
fixture), not placeholders, so the screen is proven against the same data
``openreview pii list`` reports.
"""

from __future__ import annotations

import re
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

from textual.widgets import Button, Label, ListItem, ListView, Static

from openreview_cli.pii.cache import PiiCache
from openreview_cli.tui.app import OpenReviewApp
from openreview_cli.tui.screens.confirm import ConfirmModal
from openreview_cli.tui.screens.pii_data import PiiDataScreen

HASH_A = "a1b2c3d4" + "0" * 56
HASH_B = "b1c2d3e4" + "0" * 56


def _item_text(item: ListItem) -> str:
    try:
        return str(item.query_one(Label).render())
    except Exception:
        return str(item.render())


def _seed(
    db_path: Path,
    tmp_path: Path,
    doc_hash: str,
    entities: int,
    filename: str | None = None,
) -> tuple[Path, Path]:
    """Write the real encrypted-mapping artifacts + cache/audit rows."""
    review_dir = tmp_path / "reviews" / doc_hash[:12]
    review_dir.mkdir(parents=True, exist_ok=True)
    mapping = review_dir / "pii_map.enc"
    stripped = review_dir / "stripped.txt"
    mapping.write_text("{}", encoding="utf-8")
    stripped.write_text("hello", encoding="utf-8")
    PiiCache(db_path).put(doc_hash, "cfg", str(stripped), str(mapping), filename=filename)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "INSERT INTO pii_audit_trail "
            "(document_hash, timestamp, entity_count, entity_type_distribution, "
            " processing_time_ms, config_hash, status, failed_pages) "
            "VALUES (?, ?, ?, '{}', 0, 'cfg', 'success', '[]')",
            (doc_hash, datetime.now(UTC).isoformat(), entities),
        )
        conn.commit()
    finally:
        conn.close()
    return mapping, stripped


def _cache_hashes(db_path: Path) -> set[str]:
    conn = sqlite3.connect(str(db_path))
    try:
        return {row[0] for row in conn.execute("SELECT document_hash FROM pii_cache")}
    finally:
        conn.close()


async def _open_screen(pilot: Any, app: OpenReviewApp) -> PiiDataScreen:
    app.push_screen(PiiDataScreen())
    await pilot.pause()
    screen = app.screen
    assert isinstance(screen, PiiDataScreen)
    return screen


async def test_empty_state_when_nothing_is_stored(isolated_xdg: dict[str, Path]) -> None:
    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open_screen(pilot, app)

        assert screen.query_one("#pii-list", ListView).display is False
        empty = screen.query_one("#pii-empty", Static)
        assert empty.display is True
        assert "No stored PII" in str(empty.render())
        assert screen.query_one("#btn-delete-pii", Button).disabled is True


async def test_lists_real_rows_from_the_database(
    isolated_xdg: dict[str, Path], tmp_path: Path
) -> None:
    db_path = isolated_xdg["db_path"]
    _seed(db_path, tmp_path, HASH_A, 4)
    _seed(db_path, tmp_path, HASH_B, 9)

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open_screen(pilot, app)

        items = list(screen.query_one("#pii-list", ListView).children)
        assert len(items) == 2
        text = " ".join(_item_text(item) for item in items)
        assert HASH_A[:12] in text
        assert HASH_B[:12] in text
        assert "4" in text and "9" in text
        assert str(screen.query_one("#pii-subtitle", Static).render()).startswith("2")


async def test_delete_button_enables_only_after_a_selection(
    isolated_xdg: dict[str, Path], tmp_path: Path
) -> None:
    db_path = isolated_xdg["db_path"]
    _seed(db_path, tmp_path, HASH_A, 4)

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open_screen(pilot, app)
        delete_btn = screen.query_one("#btn-delete-pii", Button)
        assert delete_btn.disabled is True

        screen.query_one("#pii-list", ListView).index = 0
        await pilot.pause()

        assert delete_btn.disabled is False


async def test_delete_requires_confirmation_and_removes_only_that_document(
    isolated_xdg: dict[str, Path], tmp_path: Path
) -> None:
    db_path = isolated_xdg["db_path"]
    _seed(db_path, tmp_path, HASH_A, 4)
    _seed(db_path, tmp_path, HASH_B, 9)

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open_screen(pilot, app)
        # rows are newest-first; pick the one whose label names HASH_A
        list_view = screen.query_one("#pii-list", ListView)
        for index, item in enumerate(list_view.children):
            if HASH_A[:12] in _item_text(item):
                list_view.index = index
                break
        await pilot.pause()

        await pilot.click("#btn-delete-pii")
        await pilot.pause()

        assert isinstance(app.screen, ConfirmModal)
        message = str(app.screen.query_one("#confirm-message", Label).render())
        assert HASH_A in message
        assert "cannot be undone" in message
        # nothing is gone until the modal is answered
        assert _cache_hashes(db_path) == {HASH_A, HASH_B}

        await pilot.click("#yes")
        await pilot.pause()

        assert _cache_hashes(db_path) == {HASH_B}
        assert not (tmp_path / "reviews" / HASH_A[:12] / "pii_map.enc").exists()
        assert (tmp_path / "reviews" / HASH_B[:12] / "pii_map.enc").exists()
        items = list(screen.query_one("#pii-list", ListView).children)
        assert len(items) == 1


async def test_cancelling_the_confirmation_keeps_the_record(
    isolated_xdg: dict[str, Path], tmp_path: Path
) -> None:
    db_path = isolated_xdg["db_path"]
    _seed(db_path, tmp_path, HASH_A, 4)

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open_screen(pilot, app)
        screen.query_one("#pii-list", ListView).index = 0
        await pilot.pause()

        await pilot.click("#btn-delete-pii")
        await pilot.pause()
        await pilot.click("#no")
        await pilot.pause()

        assert _cache_hashes(db_path) == {HASH_A}
        assert (tmp_path / "reviews" / HASH_A[:12] / "pii_map.enc").exists()


async def test_d_shortcut_opens_the_confirmation_and_never_deletes_directly(
    isolated_xdg: dict[str, Path], tmp_path: Path
) -> None:
    db_path = isolated_xdg["db_path"]
    _seed(db_path, tmp_path, HASH_A, 4)

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open_screen(pilot, app)
        screen.query_one("#pii-list", ListView).index = 0
        await pilot.pause()

        await pilot.press("d")
        await pilot.pause()

        assert isinstance(app.screen, ConfirmModal)
        assert _cache_hashes(db_path) == {HASH_A}


async def test_escape_returns_to_the_previous_screen(
    isolated_xdg: dict[str, Path], tmp_path: Path
) -> None:
    _seed(isolated_xdg["db_path"], tmp_path, HASH_A, 4)

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await _open_screen(pilot, app)
        await pilot.press("escape")
        await pilot.pause()

        assert not isinstance(app.screen, PiiDataScreen)


async def test_delete_is_handed_the_full_hash_not_the_display_prefix(
    isolated_xdg: dict[str, Path], tmp_path: Path
) -> None:
    """A 12-char prefix would match other documents under LIKE prefix%."""
    _seed(isolated_xdg["db_path"], tmp_path, HASH_A, 4)

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open_screen(pilot, app)
        screen.query_one("#pii-list", ListView).index = 0
        await pilot.pause()

        with patch(
            "openreview_cli.tui.domain.pii.delete_pii_document_via_tui",
            return_value={"mapping_removed": True, "audit_records": 1, "cache_removed": True},
        ) as mock_delete:
            await pilot.click("#btn-delete-pii")
            await pilot.pause()
            await pilot.click("#yes")
            await pilot.pause()

        assert mock_delete.call_args.args[0] == HASH_A


async def test_empty_state_after_deleting_the_last_document(
    isolated_xdg: dict[str, Path], tmp_path: Path
) -> None:
    _seed(isolated_xdg["db_path"], tmp_path, HASH_A, 4)

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open_screen(pilot, app)
        screen.query_one("#pii-list", ListView).index = 0
        await pilot.pause()
        await pilot.click("#btn-delete-pii")
        await pilot.pause()
        await pilot.click("#yes")
        await pilot.pause()

        assert screen.query_one("#pii-list", ListView).display is False
        assert screen.query_one("#pii-empty", Static).display is True
        assert screen.query_one("#btn-delete-pii", Button).disabled is True


async def test_expiring_row_is_labelled(isolated_xdg: dict[str, Path], tmp_path: Path) -> None:
    """The list tells the user when a mapping stops being kept for them."""
    db_path = isolated_xdg["db_path"]
    _seed(db_path, tmp_path, HASH_A, 4)
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "UPDATE pii_cache SET expiry_at = ?",
        ((datetime.now(UTC) + timedelta(days=3)).isoformat(),),
    )
    conn.commit()
    conn.close()

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open_screen(pilot, app)

        text = _item_text(next(iter(screen.query_one("#pii-list", ListView).children)))
        assert "expires" in text


async def test_row_leads_with_the_recorded_filename(
    isolated_xdg: dict[str, Path], tmp_path: Path
) -> None:
    """A row whose filename was recorded shows it, with the hash tiebreaker."""
    db_path = isolated_xdg["db_path"]
    _seed(db_path, tmp_path, HASH_A, 4, filename="Acme_NDA_v3.pdf")

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open_screen(pilot, app)

        text = _item_text(next(iter(screen.query_one("#pii-list", ListView).children)))
        assert "Acme_NDA_v3.pdf" in text
        assert HASH_A[:12] in text


async def test_confirmation_names_the_recorded_file(
    isolated_xdg: dict[str, Path], tmp_path: Path
) -> None:
    """The delete confirmation names the file and keeps the full hash."""
    db_path = isolated_xdg["db_path"]
    _seed(db_path, tmp_path, HASH_A, 4, filename="Acme_NDA_v3.pdf")

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open_screen(pilot, app)
        screen.query_one("#pii-list", ListView).index = 0
        await pilot.pause()

        await pilot.click("#btn-delete-pii")
        await pilot.pause()

        assert isinstance(app.screen, ConfirmModal)
        message = str(app.screen.query_one("#confirm-message", Label).render())
        assert "Acme_NDA_v3.pdf" in message
        assert HASH_A in message  # the full 64-char hash is still present
        assert "cannot be undone" in message
        # the known-filename subject keeps its single (hash prefix) parenthetical
        assert f"Acme_NDA_v3.pdf ({HASH_A[:12]}...)" in message
        # no filename fallback line is added when the file is known
        assert "No source filename was recorded" not in message
        assert ") (" not in message
        for line in message.splitlines():
            assert line.count("(") <= 1, line


async def test_row_without_a_filename_shows_the_fallback_and_still_deletes(
    isolated_xdg: dict[str, Path], tmp_path: Path
) -> None:
    """Records written before this change (no filename) show a clear fallback."""
    db_path = isolated_xdg["db_path"]
    _seed(db_path, tmp_path, HASH_A, 4)  # no filename recorded

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open_screen(pilot, app)

        text = _item_text(next(iter(screen.query_one("#pii-list", ListView).children)))
        assert "filename not recorded" in text

        # the modal still opens and names the date rather than inventing a file
        screen.query_one("#pii-list", ListView).index = 0
        await pilot.pause()
        await pilot.click("#btn-delete-pii")
        await pilot.pause()

        assert isinstance(app.screen, ConfirmModal)
        message = str(app.screen.query_one("#confirm-message", Label).render())
        assert HASH_A in message
        assert "cannot be undone" in message

        lines = message.splitlines()
        # the subject is a clean noun phrase: no "filename not recorded"
        # parenthetical and no hash prefix stacked onto it
        subject = lines[0]
        assert re.fullmatch(
            r"Permanently delete the stored PII data for the document reviewed on "
            r"\d{4}-\d{2}-\d{2}\?",
            subject,
        ), subject
        assert HASH_A[:12] not in subject
        assert "filename not recorded" not in subject
        # the explanation is its own body line, right under the full hash
        hash_index = next(i for i, line in enumerate(lines) if line.startswith("Document hash:"))
        assert lines[hash_index] == f"Document hash: {HASH_A}"
        assert lines[hash_index + 1] == "No source filename was recorded for this record."
        # no line stacks two parentheticals
        assert ") (" not in message
        for line in lines:
            assert line.count("(") <= 1, line

        await pilot.click("#yes")
        await pilot.pause()

        assert _cache_hashes(db_path) == set()
