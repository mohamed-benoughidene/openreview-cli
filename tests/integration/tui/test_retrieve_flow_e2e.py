"""End-to-end acceptance test: chunk, ingest and search a real document.

This is the goal's acceptance criterion, not a render check. It drives the
real widgets on ``tests/fixtures/nda_with_pii.pdf`` through the real handlers
and asserts on real document text that a real sparse index produced, so the
whole ``parse -> chunk -> ingest -> retrieve`` chain has to work for it to pass.

Everything runs under ``isolated_xdg`` with ``db_dir`` passed explicitly, so no
index and no ``last_indexed.json`` is ever written into the developer's real
``~/.local/share/openreview/indexes/``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from textual.widgets import Input, Label, ListItem, ListView, Static

from openreview_cli.tui.app import OpenReviewApp
from openreview_cli.tui.domain import retrieval as _retrieval
from openreview_cli.tui.screens.retrieve import RetrieveScreen

FIXTURE_NAME = "nda_with_pii.pdf"

#: A phrase that exists verbatim in the fixture *and* falls inside the 60-char
#: excerpt a result row renders, so both the query and the assertion are on the
#: document's own text rather than on anything the test invented.
PHRASE = "CONFIDENTIALITY AGREEMENT"

SEP = " \u00b7 "


def _status(screen: RetrieveScreen) -> str:
    return str(screen.query_one("#retrieve-status", Static).render())


def _submit(screen: RetrieveScreen, widget_id: str, value: str) -> Input.Submitted:
    """The event pressing Enter in that box raises, driven through the handler."""
    widget = screen.query_one(widget_id, Input)
    widget.focus()
    widget.value = value
    return Input.Submitted(input=widget, value=value)


async def _rows(pilot: Any, screen: RetrieveScreen) -> list[str]:
    """Row text, one event-loop tick after the append (Textual's mount)."""
    await pilot.pause()
    rows: list[str] = []
    for item in screen.query_one("#retrieve-results", ListView).children:
        assert isinstance(item, ListItem)
        rows.append(str(item.query_one(Label).render()))
    return rows


def _score_of(row: str) -> float:
    """The rendered score from ``{rank}. [{heading}] · {score} · {excerpt}``."""
    return float(row.split(SEP)[1])


async def test_chunk_ingest_and_search_a_real_document(
    fixtures_dir: Path, tmp_path: Path, isolated_xdg: dict[str, Path]
) -> None:
    db_dir = tmp_path / "indexes"
    fixture = fixtures_dir / FIXTURE_NAME
    top_k = _retrieval.configured_top_k()

    app = OpenReviewApp()
    async with app.run_test(size=(140, 40)) as pilot:
        app.push_screen(RetrieveScreen(db_dir=db_dir))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, RetrieveScreen)

        # 1. Choose the document and chunk it, through the real submit handler.
        path_event = _submit(screen, "#retrieve-path", str(fixture))
        await screen.on_input_submitted(path_event)
        assert _status(screen).startswith(f"Chunked {FIXTURE_NAME} - ")
        assert _status(screen).endswith("Press Ingest to index it.")

        # 2. Ingest it.
        await screen.action_ingest_document()

        document_id, db_path = _retrieval.resolve_document(fixture, db_dir=db_dir)
        assert db_path.exists(), "ingest must leave a real index on disk"
        assert db_path.name == f"{document_id[:32]}.db"
        meta = _retrieval.index_meta(db_path)
        assert meta is not None
        assert meta["index_status"] == "indexed"
        assert _status(screen) == (
            f"Indexed {FIXTURE_NAME} - {meta['chunk_count']} chunks. "
            "Enter a phrase below to search."
        )

        # 3. Search for a phrase that exists in the document.
        query_event = _submit(screen, "#retrieve-query", PHRASE)
        await screen.on_input_submitted(query_event)

        rows = await _rows(pilot, screen)
        assert rows, "a real document must return at least one match"
        assert any(PHRASE in row for row in rows), rows
        top_score = _score_of(rows[0])
        assert isinstance(top_score, float)
        assert 0.0 < top_score <= 1.0
        assert _status(screen) == f'Showing top {top_k} matches for "{PHRASE}".'

        # 4. D7: a second Ingest is a no-op, so the index is not destroyed.
        mtime_before = db_path.stat().st_mtime_ns
        await screen.action_ingest_document()

        assert _status(screen).startswith("Already indexed (")
        assert "Clear index" in _status(screen), "the message must name the rebuild route"
        assert db_path.stat().st_mtime_ns == mtime_before, (
            "D7: a second Ingest must not rebuild the index it just protected"
        )
        assert app._exception is None
