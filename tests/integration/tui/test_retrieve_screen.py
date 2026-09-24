"""Integration tests for the guided retrieve screen and its launcher tab.

One file per screen, per ``tests/integration/tui/README.md``. Every test uses
``isolated_xdg`` *and* passes ``db_dir`` explicitly, so nothing reaches the
developer's real ``~/.local/share/openreview/indexes/``.

The slow handlers (chunk, ingest) are driven by awaiting the real widget
handler with a real event object; the fast ones are driven by real clicks.
Both go through the same code the user's key press does.
"""

from __future__ import annotations

import asyncio
import sqlite3
import threading
from pathlib import Path
from typing import Any

import pytest
from textual.widgets import Button, Input, Label, ListItem, ListView, Static

from openreview_cli.retrieval.errors import IndexCorruptError
from openreview_cli.tui.app import OpenReviewApp
from openreview_cli.tui.domain import retrieval as _retrieval
from openreview_cli.tui.screens.confirm import ConfirmModal
from openreview_cli.tui.screens.retrieve import RetrieveScreen

FIXTURE_NAME = "nda_with_pii.pdf"
PASSWORD_FIXTURE = Path("pdf") / "password_protected.pdf"

FIRST_RUN = "No document selected. Enter a path above, then Chunk and Ingest before searching."
NOT_INDEXED = "Not indexed yet. Press Ingest to build the index."
DAMAGED = "This document's index is damaged. Press Clear index, then Ingest to rebuild it."
INTERRUPTED = "An earlier Ingest was interrupted. Press Ingest to rebuild the index."
CHUNKED_PREFIX = f"Chunked {FIXTURE_NAME} - "


def _status(screen: RetrieveScreen) -> str:
    return str(screen.query_one("#retrieve-status", Static).render())


def _item_text(item: ListItem) -> str:
    try:
        return str(item.query_one(Label).render())
    except Exception:
        return str(item.render())


async def _result_rows(pilot: Any, screen: RetrieveScreen) -> list[str]:
    """Read the rows once the appended ListItems have finished mounting.

    ``ListView.append`` is documented to "yield control to the event loop until
    the DOM has been updated with the new child item" (``textual/widgets/
    _list_view.py``), so one tick is required before the ``Label`` inside each
    ``ListItem`` exists. Measured: right after ``append`` the item is already in
    ``ListView.children`` but ``item.children`` is still empty and
    ``item.is_mounted`` is ``False``; after one ``pilot.pause()`` the label is
    present and renders verbatim. The screen passes the label into the
    ``ListItem`` constructor, so nothing is deferred by our own code - this is
    Textual's mount scheduling, and the pause is what the user's next repaint
    does too.
    """
    await pilot.pause()
    return [_item_text(item) for item in screen.query_one("#retrieve-results", ListView).children]


def _capture_notifications(screen: RetrieveScreen) -> list[str]:
    """Shadow ``Widget.notify`` on this instance so tests can read the toasts."""
    messages: list[str] = []
    screen.notify = lambda message, **kwargs: messages.append(message)  # type: ignore[method-assign]
    return messages


async def _open_screen(pilot: Any, app: OpenReviewApp, db_dir: Path) -> RetrieveScreen:
    app.push_screen(RetrieveScreen(db_dir=db_dir))
    await pilot.pause()
    screen = app.screen
    assert isinstance(screen, RetrieveScreen)
    return screen


def _set_path(screen: RetrieveScreen, value: str) -> Input:
    path_input = screen.query_one("#retrieve-path", Input)
    path_input.focus()
    path_input.value = value
    return path_input


def _submit(screen: RetrieveScreen, widget_id: str, value: str) -> Any:
    """The real ``Input.Submitted`` event, as pressing Enter in that box raises."""
    widget = screen.query_one(widget_id, Input)
    widget.value = value
    return Input.Submitted(input=widget, value=value)


def _seed_index(db_dir: Path, fixture: Path, chunks: list[dict[str, Any]]) -> tuple[str, Path]:
    """Write a real sparse index for *fixture* under *db_dir*."""
    document_id, db_path = _retrieval.resolve_document(fixture, db_dir=db_dir)
    _retrieval.ingest_chunks(chunks, db_path, document_id=document_id)
    return document_id, db_path


def _seed_state(db_dir: Path, fixture: Path, status: str | None) -> Path:
    """Create the index file, with one ``index_meta`` row - or with none.

    ``status=None`` leaves the schema in place but inserts no row, which is the
    state an interrupted writer or a stray ``sqlite3.connect`` leaves behind.
    """
    from openreview_cli.retrieval.storage import RetrievalStorage

    document_id, db_path = _retrieval.resolve_document(fixture, db_dir=db_dir)
    with RetrievalStorage(db_path) as storage:
        storage.create_schema()
        if status is not None:
            storage.conn.execute(
                "INSERT INTO index_meta (document_id, document_path, index_version, "
                "index_status, chunk_count, method, db_size_bytes) "
                "VALUES (?, ?, 1, ?, 0, 'sparse', 0)",
                (document_id, str(db_path), status),
            )
            storage.conn.commit()
    return db_path


def _set_stored_status(db_path: Path, status: str) -> None:
    """Rewrite the stored ``index_status`` of an existing index."""
    from openreview_cli.retrieval.storage import RetrievalStorage

    with RetrievalStorage(db_path) as storage:
        storage.conn.execute("UPDATE index_meta SET index_status=?", (status,))
        storage.conn.commit()


def _chunk(text: str, structural: str = "Confidentiality") -> dict[str, Any]:
    return {
        "id": "chunk-seed-0",
        "text": text,
        "source_clause_title": structural,
        "source_clause_level": 1,
        "char_offset_start": 0,
        "char_offset_end": len(text),
        "parent_chunk_id": None,
        "structural_location": structural,
    }


# --------------------------------------------------------------------------
# The launcher tab
# --------------------------------------------------------------------------


async def test_the_retrieve_tab_renders_its_title_and_description(
    isolated_xdg: dict[str, Path],
) -> None:
    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("7")
        await pilot.pause()

        text = " ".join(str(widget.render()) for widget in app.query_one("#retrieve").query(Static))
        assert "Search inside a document" in text
        assert "Chunk and index a contract, then search its text." in text
        assert app.query_one("#btn-open-retrieve", Button) is not None


async def test_the_retrieve_tab_opens_the_screen(
    isolated_xdg: dict[str, Path],
) -> None:
    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("7")
        await pilot.pause()

        await pilot.click("#btn-open-retrieve")
        await pilot.pause()

        assert isinstance(app.screen, RetrieveScreen)


# --------------------------------------------------------------------------
# First run
# --------------------------------------------------------------------------


async def test_the_screen_mounts_with_the_path_focused_and_the_first_run_status(
    tmp_path: Path, isolated_xdg: dict[str, Path]
) -> None:
    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open_screen(pilot, app, tmp_path / "indexes")

        assert app.focused is screen.query_one("#retrieve-path", Input)
        assert _status(screen) == FIRST_RUN
        assert app._exception is None


# --------------------------------------------------------------------------
# Chunking
# --------------------------------------------------------------------------


async def test_submitting_a_path_chunks_it_and_reports_the_chunked_state(
    fixtures_dir: Path, tmp_path: Path, isolated_xdg: dict[str, Path]
) -> None:
    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open_screen(pilot, app, tmp_path / "indexes")

        await screen.on_input_submitted(
            _submit(screen, "#retrieve-path", str(fixtures_dir / FIXTURE_NAME))
        )

        assert _status(screen).startswith(CHUNKED_PREFIX)
        assert _status(screen).endswith("Press Ingest to index it.")
        assert app._exception is None


# --------------------------------------------------------------------------
# Searching an un-indexed document (D3 layer 1)
# --------------------------------------------------------------------------


async def test_search_before_indexing_writes_the_persistent_not_indexed_message(
    fixtures_dir: Path, tmp_path: Path, isolated_xdg: dict[str, Path]
) -> None:
    db_dir = tmp_path / "indexes"
    fixture = fixtures_dir / FIXTURE_NAME
    document_id, db_path = _retrieval.resolve_document(fixture, db_dir=db_dir)

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open_screen(pilot, app, db_dir)
        _set_path(screen, str(fixture))
        not_indexed_before = _capture_notifications(screen)

        await screen.on_input_submitted(_submit(screen, "#retrieve-query", "confidentiality"))

        assert _status(screen) == NOT_INDEXED
        assert screen.query_one("#retrieve-status", Static).display is True
        # No engine was built: nothing may have fabricated the database file.
        assert not db_path.exists()
        assert app._exception is None
        # The message is persistent, not only a transient toast.
        assert not_indexed_before == [] or NOT_INDEXED in not_indexed_before

        # The graceful message must stay reachable: these buttons are live.
        assert screen.query_one("#btn-search", Button).disabled is False
        assert screen.query_one("#btn-ingest", Button).disabled is False


# --------------------------------------------------------------------------
# Search results
# --------------------------------------------------------------------------


async def test_a_search_that_matches_nothing_clears_the_previous_rows(
    fixtures_dir: Path, tmp_path: Path, isolated_xdg: dict[str, Path]
) -> None:
    db_dir = tmp_path / "indexes"
    fixture = fixtures_dir / FIXTURE_NAME
    _seed_index(db_dir, fixture, [_chunk("The confidentiality obligation survives.")])

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open_screen(pilot, app, db_dir)
        _set_path(screen, str(fixture))

        await screen.on_input_submitted(_submit(screen, "#retrieve-query", "confidentiality"))
        first_rows = await _result_rows(pilot, screen)
        assert first_rows
        assert any("confidentiality" in row for row in first_rows)

        await screen.on_input_submitted(_submit(screen, "#retrieve-query", "zzqqxnonexistent"))

        rows = await _result_rows(pilot, screen)
        assert rows == ['No matches for "zzqqxnonexistent".']
        assert _status(screen) == f'No matches for "zzqqxnonexistent" in {FIXTURE_NAME}.'
        assert app._exception is None


async def test_a_search_with_no_query_asks_for_one_instead_of_reaching_the_engine(
    fixtures_dir: Path, tmp_path: Path, isolated_xdg: dict[str, Path]
) -> None:
    """An empty box must not reach ``RetrievalQuery``, whose ``query_text``
    validator raises ``ValueError`` - that would surface as a logged traceback
    and an "Unexpected error:" line for what is an ordinary mis-click."""
    db_dir = tmp_path / "indexes"
    fixture = fixtures_dir / FIXTURE_NAME
    _seed_index(db_dir, fixture, [_chunk("The confidentiality obligation survives.")])

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open_screen(pilot, app, db_dir)
        _set_path(screen, str(fixture))
        notifications = _capture_notifications(screen)

        await screen.action_retrieve()

        assert _status(screen) == "Enter a phrase below to search."
        assert notifications == ["Enter a phrase below to search."]
        assert app._exception is None


async def test_a_result_row_keeps_contract_brackets_verbatim(
    fixtures_dir: Path, tmp_path: Path, isolated_xdg: dict[str, Path]
) -> None:
    """``[Party A]`` must survive rendering: Rich markup would eat it."""
    db_dir = tmp_path / "indexes"
    fixture = fixtures_dir / FIXTURE_NAME
    _seed_index(
        db_dir,
        fixture,
        [_chunk("Any transfer to [Party A] requires prior written consent.")],
    )

    app = OpenReviewApp()
    async with app.run_test(size=(140, 40)) as pilot:
        screen = await _open_screen(pilot, app, db_dir)
        _set_path(screen, str(fixture))

        await screen.on_input_submitted(_submit(screen, "#retrieve-query", "Party"))

        rows = await _result_rows(pilot, screen)
        assert rows, "the seeded chunk must be retrievable"
        assert any("[Party A]" in row for row in rows), rows


# --------------------------------------------------------------------------
# Index states: no meta row, corrupt, interrupted (T5 / D3)
# --------------------------------------------------------------------------


async def test_a_db_with_no_index_meta_row_shows_not_indexed(
    fixtures_dir: Path, tmp_path: Path, isolated_xdg: dict[str, Path]
) -> None:
    """The engine raises ``IndexNotFoundError`` for this state - *not* the
    corrupt one - so the copy is the ordinary not-indexed message."""
    db_dir = tmp_path / "indexes"
    fixture = fixtures_dir / FIXTURE_NAME
    db_path = _seed_state(db_dir, fixture, None)
    assert db_path.exists(), "the premise is a file on disk with no index_meta row"

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open_screen(pilot, app, db_dir)
        _set_path(screen, str(fixture))

        await screen.on_input_submitted(_submit(screen, "#retrieve-query", "confidentiality"))

        assert _status(screen) == NOT_INDEXED
        assert DAMAGED not in _status(screen)
        assert isinstance(app.screen, RetrieveScreen)
        assert app._exception is None


async def test_a_stored_corrupt_status_shows_the_damaged_message(
    fixtures_dir: Path, tmp_path: Path, isolated_xdg: dict[str, Path]
) -> None:
    db_dir = tmp_path / "indexes"
    fixture = fixtures_dir / FIXTURE_NAME
    _seed_state(db_dir, fixture, "corrupt")

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open_screen(pilot, app, db_dir)
        _set_path(screen, str(fixture))

        await screen.on_input_submitted(_submit(screen, "#retrieve-query", "confidentiality"))

        assert _status(screen) == DAMAGED
        # The engine's copy names a shell command that cannot fix this index,
        # because that command addresses a different one (D4).
        assert "openreview ingest" not in _status(screen)
        assert isinstance(app.screen, RetrieveScreen)
        assert app._exception is None


async def test_a_stored_ingesting_status_shows_interrupted_not_corrupt(
    fixtures_dir: Path, tmp_path: Path, isolated_xdg: dict[str, Path]
) -> None:
    """An interrupted build is not damage: nothing is broken, and D7 rebuilds
    it, so calling it "corrupt" would send the user to Clear for no reason."""
    db_dir = tmp_path / "indexes"
    fixture = fixtures_dir / FIXTURE_NAME
    _seed_state(db_dir, fixture, "ingesting")

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open_screen(pilot, app, db_dir)
        _set_path(screen, str(fixture))

        await screen.on_input_submitted(_submit(screen, "#retrieve-query", "confidentiality"))

        status = _status(screen)
        assert status == INTERRUPTED
        assert "corrupt" not in status.lower()
        assert "damaged" not in status.lower()
        assert isinstance(app.screen, RetrieveScreen)
        assert app._exception is None


async def test_a_search_that_loses_the_index_mid_flight_reports_not_indexed(
    monkeypatch: pytest.MonkeyPatch,
    fixtures_dir: Path,
    tmp_path: Path,
    isolated_xdg: dict[str, Path],
) -> None:
    """D3 layer 2, reproduced for real rather than stubbed: the file disappears
    between the meta read and the engine call, so the engine's own
    ``IndexNotFoundError`` fires in a state where layer 1 had just seen a
    healthy index."""
    db_dir = tmp_path / "indexes"
    fixture = fixtures_dir / FIXTURE_NAME
    _seed_index(db_dir, fixture, [_chunk("The confidentiality obligation survives.")])
    real_search = _retrieval.search

    def _vanish(db_path: Path, query: str, *, top_k: int | None = None) -> Any:
        _retrieval.clear_index(db_path)  # gone by the time the engine looks
        return real_search(db_path, query, top_k=top_k)

    monkeypatch.setattr(_retrieval, "search", _vanish)

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open_screen(pilot, app, db_dir)
        _set_path(screen, str(fixture))

        await screen.on_input_submitted(_submit(screen, "#retrieve-query", "confidentiality"))

        assert _status(screen) == NOT_INDEXED
        assert "openreview ingest" not in _status(screen)
        assert isinstance(app.screen, RetrieveScreen)
        assert app._exception is None


async def test_a_corrupt_engine_error_is_mapped_by_type_not_by_message(
    monkeypatch: pytest.MonkeyPatch,
    fixtures_dir: Path,
    tmp_path: Path,
    isolated_xdg: dict[str, Path],
) -> None:
    """The screen must never read ``.message`` off these errors: both are bare
    ``Exception`` subclasses (``retrieval/errors.py``) with no such attribute, so
    a read would raise ``AttributeError`` from inside the ``except`` block - the
    exact crash D3's mapping exists to prevent.

    The stub is deliberate. The real engine's only ``IndexCorruptError`` site
    keys off the stored status, which the meta read would then agree with, so
    this branch cannot be reached by seeding a row; it is the defensive branch
    that the class's own "incompatible schema" wording could one day reach.
    """
    db_dir = tmp_path / "indexes"
    fixture = fixtures_dir / FIXTURE_NAME
    _seed_index(db_dir, fixture, [_chunk("The confidentiality obligation survives.")])

    def _raise_corrupt(db_path: Path, query: str, *, top_k: int | None = None) -> Any:
        raise IndexCorruptError(
            "Index database is corrupt. Re-run `openreview ingest <file>` to rebuild."
        )

    monkeypatch.setattr(_retrieval, "search", _raise_corrupt)

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open_screen(pilot, app, db_dir)
        _set_path(screen, str(fixture))

        await screen.on_input_submitted(_submit(screen, "#retrieve-query", "confidentiality"))

        assert _status(screen) == DAMAGED
        # Neither the engine's wording nor a traceback reaches the user.
        assert "openreview ingest" not in _status(screen)
        assert "Re-run" not in _status(screen)
        assert isinstance(app.screen, RetrieveScreen)
        assert app._exception is None


async def test_searching_after_clear_reports_not_indexed_and_keeps_no_stale_rows(
    fixtures_dir: Path, tmp_path: Path, isolated_xdg: dict[str, Path]
) -> None:
    """D14: the list is cleared at the start of *every* search, so a search that
    cannot run never leaves the previous query's rows claiming to be results."""
    db_dir = tmp_path / "indexes"
    fixture = fixtures_dir / FIXTURE_NAME
    _seed_index(db_dir, fixture, [_chunk("The confidentiality obligation survives.")])
    _, db_path = _retrieval.resolve_document(fixture, db_dir=db_dir)

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open_screen(pilot, app, db_dir)
        _set_path(screen, str(fixture))

        await screen.on_input_submitted(_submit(screen, "#retrieve-query", "confidentiality"))
        assert await _result_rows(pilot, screen), "the seeded index must be searchable first"

        _retrieval.clear_index(db_path)

        await screen.on_input_submitted(_submit(screen, "#retrieve-query", "confidentiality"))

        assert _status(screen) == NOT_INDEXED
        assert await _result_rows(pilot, screen) == [], "stale rows from a deleted index"
        assert isinstance(app.screen, RetrieveScreen)
        assert app._exception is None


# --------------------------------------------------------------------------
# A physically malformed index file (D3: "No traceback, ever")
# --------------------------------------------------------------------------
#
# T5 covers a *stored* ``corrupt`` status marker. This is the different state a
# verifier measured: the file at the derived path is not a readable SQLite
# image at all, which is what an ingest killed mid-write, a second process or a
# full disk leaves behind. ``_refresh_meta`` sat outside every ``try`` while
# this was true, so chunk, ingest, search and status all died, and Clear - the
# route the screen's own damaged-index copy advertises - died before its modal
# could open.

_PAGE_SIZE = 4096
#: Damage is written as an invalid b-tree page type, so SQLite raises
#: "database disk image is malformed" the moment it reads that page.
_INVALID_PAGE_TYPE = 0x00


def _sqlite_refuses(db_path: Path) -> bool:
    """True when SQLite cannot read the image at all."""
    try:
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("SELECT * FROM index_meta")
    except sqlite3.DatabaseError:
        return True
    return False


def _malformed_index(db_dir: Path, fixture: Path) -> Path:
    """A real index truncated to half its length, as the reproducer built one."""
    _, db_path = _seed_index(db_dir, fixture, [_chunk("The confidentiality obligation survives.")])
    raw = db_path.read_bytes()
    db_path.write_bytes(raw[: len(raw) // 2])

    assert _sqlite_refuses(db_path), "premise: a truncated image must not be readable SQLite"
    return db_path


def _sqlite_reads_meta_but_not_chunks(db_path: Path) -> bool:
    """Raw-SQLite premise check, independent of the adapter under test."""
    try:
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("SELECT * FROM index_meta").fetchone()
    except sqlite3.DatabaseError:
        return False
    try:
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                "SELECT chunk_id FROM chunk_fts WHERE chunk_fts MATCH ? LIMIT 5",
                ("confidentiality",),
            ).fetchall()
    except sqlite3.DatabaseError:
        return True
    return False


def _torn_page_index(db_dir: Path, fixture: Path) -> Path:
    """A real index whose damage is below the metadata row.

    SQLite stores no page checksums, so a torn page is only noticed when that
    page is read. Damage a page the metadata read never touches and the index
    still reports ``indexed`` right up to the search. Which page that is
    depends on the index's own layout, so it is found by measurement against
    raw SQLite rather than by hard-coding a page number.
    """
    _, db_path = _seed_index(db_dir, fixture, [_chunk("The confidentiality obligation survives.")])
    raw = db_path.read_bytes()
    for page in range(1, len(raw) // _PAGE_SIZE):
        variant = bytearray(raw)
        variant[page * _PAGE_SIZE] = _INVALID_PAGE_TYPE
        db_path.write_bytes(bytes(variant))
        if _sqlite_reads_meta_but_not_chunks(db_path):
            return db_path

    raise AssertionError("no page produced a readable metadata row with unreadable chunks")


async def test_searching_a_malformed_index_reports_damage_and_stays_up(
    fixtures_dir: Path, tmp_path: Path, isolated_xdg: dict[str, Path]
) -> None:
    db_dir = tmp_path / "indexes"
    fixture = fixtures_dir / FIXTURE_NAME
    db_path = _malformed_index(db_dir, fixture)

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open_screen(pilot, app, db_dir)
        _set_path(screen, str(fixture))

        await screen.on_input_submitted(_submit(screen, "#retrieve-query", "confidentiality"))

        # D3's damaged-index copy, not the engine's CLI copy and not a traceback.
        assert _status(screen) == DAMAGED
        assert "openreview ingest" not in _status(screen)
        assert isinstance(app.screen, RetrieveScreen)
        assert app._exception is None
        assert db_path.exists(), "looking at a damaged index must not delete it"


async def test_a_damaged_page_under_a_readable_metadata_row_still_reports_damage(
    fixtures_dir: Path, tmp_path: Path, isolated_xdg: dict[str, Path]
) -> None:
    """The metadata row is intact, so D3 layer 1 says ``indexed`` and the
    failure happens inside the engine instead. It must arrive as the damaged
    index too, rather than as ``Unexpected error: database disk image is
    malformed``: one vocabulary for damage, on both read paths."""
    db_dir = tmp_path / "indexes"
    fixture = fixtures_dir / FIXTURE_NAME
    db_path = _torn_page_index(db_dir, fixture)
    meta = _retrieval.index_meta(db_path)
    assert meta is not None and meta["index_status"] == "indexed", "premise: layer 1 passes"

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open_screen(pilot, app, db_dir)
        _set_path(screen, str(fixture))

        await screen.on_input_submitted(_submit(screen, "#retrieve-query", "confidentiality"))

        assert _status(screen) == DAMAGED
        assert "Unexpected error" not in _status(screen)
        assert isinstance(app.screen, RetrieveScreen)
        assert app._exception is None


async def test_clear_recovers_a_malformed_index_without_reading_its_metadata(
    fixtures_dir: Path, tmp_path: Path, isolated_xdg: dict[str, Path]
) -> None:
    """This is the recovery route the damaged-index copy advertises, and it
    must not need a metadata row: Clear needs the resolved ``db_path``."""
    db_dir = tmp_path / "indexes"
    fixture = fixtures_dir / FIXTURE_NAME
    db_path = _malformed_index(db_dir, fixture)

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open_screen(pilot, app, db_dir)
        _set_path(screen, str(fixture))

        await pilot.click("#btn-clear")
        await pilot.pause()

        modal = app.screen
        assert isinstance(modal, ConfirmModal)
        assert str(modal.query_one("#confirm-title", Label).render()) == "Clear index"
        message = str(modal.query_one("#confirm-message", Label).render())
        assert FIXTURE_NAME in message
        # The count is unreadable, and saying "0" would contradict the damaged
        # status line the user is looking at.
        assert "cannot be read" in message
        assert "0 chunks" not in message
        assert "The source file is not touched." in message
        assert "Ingesting it again rebuilds this index." in message
        assert db_path.exists(), "nothing is deleted while the question is open"

        await pilot.click("#yes")
        await pilot.pause()
        await pilot.pause()

        assert isinstance(app.screen, RetrieveScreen)
        assert not db_path.exists(), "the advertised recovery route must remove the damaged file"
        assert _status(screen) == NOT_INDEXED
        assert app._exception is None


async def test_ingesting_a_malformed_index_rebuilds_it_and_search_then_works(
    fixtures_dir: Path, tmp_path: Path, isolated_xdg: dict[str, Path]
) -> None:
    """``ingest_document`` deletes the index before rebuilding, so this should
    already work once the metadata read stops crashing - proven, not assumed."""
    db_dir = tmp_path / "indexes"
    fixture = fixtures_dir / FIXTURE_NAME
    db_path = _malformed_index(db_dir, fixture)

    app = OpenReviewApp()
    async with app.run_test(size=(140, 40)) as pilot:
        screen = await _open_screen(pilot, app, db_dir)
        _set_path(screen, str(fixture))

        await screen.action_ingest_document()

        assert not _sqlite_refuses(db_path), "Ingest must replace the malformed image"
        meta = _retrieval.index_meta(db_path)
        assert meta is not None
        assert meta["index_status"] == "indexed"
        assert _status(screen).startswith(f"Indexed {FIXTURE_NAME} - ")

        await screen.on_input_submitted(_submit(screen, "#retrieve-query", "confidentiality"))

        rows = await _result_rows(pilot, screen)
        assert rows, "the rebuilt index must be searchable"
        assert any("confidentiality" in row.lower() for row in rows), rows
        assert app._exception is None


async def test_the_refresh_routine_and_chunking_survive_a_malformed_index(
    monkeypatch: pytest.MonkeyPatch,
    fixtures_dir: Path,
    tmp_path: Path,
    isolated_xdg: dict[str, Path],
) -> None:
    """``_refresh_meta`` runs in every action, so the crash was not confined to
    Search. Chunking is given a stub so the test stays on that concern."""
    db_dir = tmp_path / "indexes"
    fixture = fixtures_dir / FIXTURE_NAME
    db_path = _malformed_index(db_dir, fixture)
    monkeypatch.setattr(
        _retrieval,
        "chunk_document",
        lambda _path: [
            {**_chunk("The confidentiality obligation survives."), "source_clause_id": "clause-0"}
        ],
    )

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open_screen(pilot, app, db_dir)
        _set_path(screen, str(fixture))

        await screen.action_chunk_document()
        assert _status(screen).endswith("Press Ingest to index it.")

        # The refresh routine, which also runs on mount and after every step.
        await screen.action_index_status()
        assert _status(screen) == DAMAGED

        assert isinstance(app.screen, RetrieveScreen)
        assert app._exception is None
        assert db_path.exists()


# --------------------------------------------------------------------------
# Clear requires confirmation (T6 / D6)
# --------------------------------------------------------------------------


async def test_clear_asks_first_naming_the_document_and_keeps_the_index_open(
    fixtures_dir: Path, tmp_path: Path, isolated_xdg: dict[str, Path]
) -> None:
    db_dir = tmp_path / "indexes"
    fixture = fixtures_dir / FIXTURE_NAME
    _seed_index(db_dir, fixture, [_chunk("The confidentiality obligation survives.")])
    _, db_path = _retrieval.resolve_document(fixture, db_dir=db_dir)

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open_screen(pilot, app, db_dir)
        _set_path(screen, str(fixture))

        await pilot.click("#btn-clear")
        await pilot.pause()

        modal = app.screen
        assert isinstance(modal, ConfirmModal)
        assert str(modal.query_one("#confirm-title", Label).render()) == "Clear index"
        message = str(modal.query_one("#confirm-message", Label).render())
        assert FIXTURE_NAME in message
        assert "1 chunks are indexed for this document." in message
        assert "The source file is not touched." in message
        assert "Ingesting it again rebuilds this index." in message
        # Destructive styling, and the safe answer is the focused one.
        assert modal.query_one("#yes", Button).variant == "error"
        assert app.focused is modal.query_one("#no", Button)
        # Nothing is deleted while the question is still open.
        assert db_path.exists()
        assert app._exception is None


async def test_declining_the_clear_keeps_the_index(
    fixtures_dir: Path, tmp_path: Path, isolated_xdg: dict[str, Path]
) -> None:
    db_dir = tmp_path / "indexes"
    fixture = fixtures_dir / FIXTURE_NAME
    _seed_index(db_dir, fixture, [_chunk("The confidentiality obligation survives.")])
    _, db_path = _retrieval.resolve_document(fixture, db_dir=db_dir)

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open_screen(pilot, app, db_dir)
        _set_path(screen, str(fixture))

        await pilot.click("#btn-clear")
        await pilot.pause()
        await pilot.click("#no")
        await pilot.pause()

        assert isinstance(app.screen, RetrieveScreen)
        assert db_path.exists()
        assert app._exception is None

        # The index is not just still on disk, it is still usable.
        await screen.on_input_submitted(_submit(screen, "#retrieve-query", "confidentiality"))
        assert await _result_rows(pilot, screen)


async def test_confirming_the_clear_removes_the_index_and_the_next_search_says_so(
    fixtures_dir: Path, tmp_path: Path, isolated_xdg: dict[str, Path]
) -> None:
    db_dir = tmp_path / "indexes"
    fixture = fixtures_dir / FIXTURE_NAME
    _seed_index(db_dir, fixture, [_chunk("The confidentiality obligation survives.")])
    _, db_path = _retrieval.resolve_document(fixture, db_dir=db_dir)

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open_screen(pilot, app, db_dir)
        _set_path(screen, str(fixture))

        await pilot.click("#btn-clear")
        await pilot.pause()
        await pilot.click("#yes")
        await pilot.pause()
        await pilot.pause()

        assert isinstance(app.screen, RetrieveScreen)
        assert not db_path.exists(), "the confirmed clear must delete the index"
        assert _status(screen) == NOT_INDEXED

        await screen.on_input_submitted(_submit(screen, "#retrieve-query", "confidentiality"))

        assert _status(screen) == NOT_INDEXED
        assert await _result_rows(pilot, screen) == []
        assert app._exception is None


# --------------------------------------------------------------------------
# Escape
# --------------------------------------------------------------------------


async def test_escape_pops_the_screen(tmp_path: Path, isolated_xdg: dict[str, Path]) -> None:
    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await _open_screen(pilot, app, tmp_path / "indexes")

        await pilot.press("escape")
        await pilot.pause()

        assert not isinstance(app.screen, RetrieveScreen)


# --------------------------------------------------------------------------
# Bad input is reported, never fatal
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("case", "expected"),
    [
        ("directory", "That is a directory, not a file."),
        ("missing", "No file found at "),
        ("empty", "The file appears to be empty or unreadable."),
        ("password", "This contract is password-protected."),
    ],
)
async def test_bad_input_is_reported_and_the_screen_stays_up(
    case: str,
    expected: str,
    fixtures_dir: Path,
    tmp_path: Path,
    isolated_xdg: dict[str, Path],
) -> None:
    db_dir = tmp_path / "indexes"
    if case == "directory":
        bad = tmp_path / "a-directory"
        bad.mkdir()
    elif case == "missing":
        bad = tmp_path / "absent.pdf"
    elif case == "empty":
        bad = tmp_path / "empty.pdf"
        bad.write_bytes(b"")
    else:
        bad = fixtures_dir / PASSWORD_FIXTURE

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open_screen(pilot, app, db_dir)
        notifications = _capture_notifications(screen)
        _set_path(screen, str(bad))

        await screen.action_chunk_document()

        assert notifications, "the failure must reach the user as a notification"
        assert expected in _status(screen)
        assert isinstance(app.screen, RetrieveScreen)
        assert app._exception is None


async def test_the_password_error_says_the_variable_is_read_at_parse_time(
    fixtures_dir: Path, tmp_path: Path, isolated_xdg: dict[str, Path]
) -> None:
    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open_screen(pilot, app, tmp_path / "indexes")
        _set_path(screen, str(fixtures_dir / PASSWORD_FIXTURE))

        await screen.action_chunk_document()

        assert "OPENREVIEW_PDF_PASSWORD" in _status(screen)
        assert "restart" in _status(screen)


async def test_an_unexpected_failure_is_reported_by_message_not_by_class_name(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, isolated_xdg: dict[str, Path]
) -> None:
    def _explode(_path: Path) -> list[dict[str, Any]]:
        raise RuntimeError("engine fell over")

    monkeypatch.setattr(_retrieval, "chunk_document", _explode)

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open_screen(pilot, app, tmp_path / "indexes")
        notifications = _capture_notifications(screen)
        _set_path(screen, str(tmp_path / "whatever.pdf"))
        (tmp_path / "whatever.pdf").write_bytes(b"%PDF-1.4 x")

        await screen.action_chunk_document()

        assert notifications == ["Unexpected error: engine fell over"]
        assert "RuntimeError" not in _status(screen)
        assert isinstance(app.screen, RetrieveScreen)
        assert app._exception is None


# --------------------------------------------------------------------------
# The busy guard (D8)
# --------------------------------------------------------------------------


async def test_the_busy_flag_gates_all_five_actions_and_the_inputs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, isolated_xdg: dict[str, Path]
) -> None:
    calls: list[str] = []

    def _record(name: str) -> Any:
        def _recorder(*_args: Any, **_kwargs: Any) -> Any:
            calls.append(name)
            return []

        return _recorder

    for name in (
        "resolve_document",
        "chunk_document",
        "index_meta",
        "ingest_chunks",
        "search",
        "clear_index",
    ):
        monkeypatch.setattr(_retrieval, name, _record(name))

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open_screen(pilot, app, tmp_path / "indexes")
        screen._set_busy(True)
        try:
            for button_id in (
                "#btn-chunk",
                "#btn-ingest",
                "#btn-search",
                "#btn-clear",
                "#btn-back",
            ):
                assert screen.query_one(button_id, Button).disabled is True
            assert screen.check_action("go_back", ()) is False

            await screen.action_chunk_document()
            await screen.action_ingest_document()
            await screen.action_retrieve()
            await screen.action_index_status()
            await screen.action_index_clear()
            await screen.on_input_submitted(
                _submit(screen, "#retrieve-path", str(tmp_path / "x.pdf"))
            )
            await screen.on_input_submitted(_submit(screen, "#retrieve-query", "anything"))
        finally:
            screen._set_busy(False)

        assert calls == []
        assert screen.check_action("go_back", ()) is True


async def test_a_second_ingest_while_the_first_is_in_flight_is_ignored(
    monkeypatch: pytest.MonkeyPatch,
    fixtures_dir: Path,
    tmp_path: Path,
    isolated_xdg: dict[str, Path],
) -> None:
    calls: list[str] = []
    release = threading.Event()

    monkeypatch.setattr(
        _retrieval, "chunk_document", lambda _path: [_chunk("A chunk of contract text.")]
    )

    def _blocking_ingest(
        chunks: list[dict[str, Any]], db_path: Path, *, document_id: str
    ) -> dict[str, Any]:
        calls.append(document_id)
        release.wait(10)
        return {"index_status": "indexed", "chunk_count": len(chunks)}

    monkeypatch.setattr(_retrieval, "ingest_chunks", _blocking_ingest)

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open_screen(pilot, app, tmp_path / "indexes")
        _set_path(screen, str(fixtures_dir / FIXTURE_NAME))

        in_flight = asyncio.create_task(screen.action_ingest_document())
        await pilot.pause()
        await pilot.pause()

        assert screen._busy is True
        assert screen.query_one("#btn-ingest", Button).disabled is True
        assert screen.query_one("#btn-back", Button).disabled is True
        assert len(calls) == 1

        # The second submission, while the first is still in flight.
        await screen.action_ingest_document()
        await screen.on_input_submitted(_submit(screen, "#retrieve-query", "any phrase at all"))
        assert len(calls) == 1

        release.set()
        await in_flight

        assert len(calls) == 1
        assert app._exception is None
