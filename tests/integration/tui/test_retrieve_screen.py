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
import threading
from pathlib import Path
from typing import Any

import pytest
from textual.widgets import Button, Input, Label, ListItem, ListView, Static

from openreview_cli.tui.app import OpenReviewApp
from openreview_cli.tui.domain import retrieval as _retrieval
from openreview_cli.tui.screens.retrieve import RetrieveScreen

FIXTURE_NAME = "nda_with_pii.pdf"
PASSWORD_FIXTURE = Path("pdf") / "password_protected.pdf"

FIRST_RUN = "No document selected. Enter a path above, then Chunk and Ingest before searching."
NOT_INDEXED = "Not indexed yet. Press Ingest to build the index."
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
