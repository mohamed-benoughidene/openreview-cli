"""RetrieveScreen — the guided chunk -> ingest -> search flow.

One screen owns the whole flow and its five actions. Every heavy step runs in
a worker thread (``asyncio.to_thread``) and every user-visible string is
written to ``#retrieve-status`` in one persistent voice, so the screen always
states what is true now and what to press next.

Retrieval is sparse-only: no gateway is constructed, embedding is never
computed, and ``openreview_cli.gateway.router`` is never imported.

No document text, chunk text, PII or query is logged — counts and durations
only.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any, ClassVar, Literal

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Label, ListItem, ListView, Static

from openreview_cli.parsing.models import ParseError
from openreview_cli.retrieval.errors import IndexCorruptError, IndexNotFoundError
from openreview_cli.retrieval.models import RetrievalResult
from openreview_cli.tui.domain import retrieval as _retrieval
from openreview_cli.tui.screens.confirm import ConfirmModal

logger = logging.getLogger(__name__)

HEADER_TITLE = "Search inside a document"
HEADER_SUBTITLE = "sparse index - no embeddings, no network"

FIRST_RUN_MESSAGE = (
    "No document selected. Enter a path above, then Chunk and Ingest before searching."
)
NOT_INDEXED_MESSAGE = "Not indexed yet. Press Ingest to build the index."
DAMAGED_MESSAGE = "This document's index is damaged. Press Clear index, then Ingest to rebuild it."
INTERRUPTED_MESSAGE = "An earlier Ingest was interrupted. Press Ingest to rebuild the index."
#: Not new copy: this is the closing sentence of D14's "Indexed" state, reused
#: for the one case D14 does not name - Search pressed with an empty box.
NO_QUERY_MESSAGE = "Enter a phrase below to search."

_PASSWORD_NOTE = (
    " OPENREVIEW_PDF_PASSWORD is read when the document is parsed, so restart "
    "openreview after setting it."
)

_BUTTON_IDS = ("#btn-chunk", "#btn-ingest", "#btn-search", "#btn-clear", "#btn-back")

#: Stand-in for the metadata of a file that exists but cannot be read at all.
#: Such a file has no ``index_status`` to read, and the adapter reports it as
#: ``IndexCorruptError``; mapping it onto the stored ``corrupt`` state gives it
#: D3's damaged-index copy - and the Clear route that copy advertises - instead
#: of a crash. ``chunk_count`` is ``None`` because the count is not zero, it is
#: unreadable, and Clear's confirmation must not claim otherwise.
_DAMAGED_META: dict[str, Any] = {"index_status": "corrupt", "chunk_count": None}


def _index_state_message(meta: dict[str, Any] | None) -> str | None:
    """Return the copy for an unusable index, or ``None`` when it is usable.

    The stored state is the only input: the engine's own messages name a shell
    command that writes a *different* index, so they never reach the user.
    """
    if meta is None:
        return NOT_INDEXED_MESSAGE
    status = str(meta.get("index_status", ""))
    if status == "indexed":
        return None
    if status == "corrupt":
        return DAMAGED_MESSAGE
    if status == "ingesting":
        return INTERRUPTED_MESSAGE
    return NOT_INDEXED_MESSAGE


def _error_copy(error: BaseException, raw_path: str) -> str:
    """Map a failure to specific copy — never a raw errno string."""
    if isinstance(error, ParseError):
        copy = f"{error.message} {error.action}"
        if error.category == "password_protected":
            copy += _PASSWORD_NOTE
        return copy
    if isinstance(error, IsADirectoryError):
        return "That is a directory, not a file."
    if isinstance(error, FileNotFoundError):
        return f"No file found at {raw_path}."
    if isinstance(error, PermissionError):
        return f"Permission denied reading {raw_path}."
    if isinstance(error, OSError):
        return f"Could not read {raw_path}."
    return f"Unexpected error: {error}"


class RetrieveScreen(Screen[None]):
    """Chunk a document, index it, and search inside it, in one guided flow."""

    DEFAULT_CSS: ClassVar[str] = """
    RetrieveScreen { padding: 1; }
    #retrieve-header { text-style: bold; background: $primary; color: $text; padding: 1 2; margin: 0 0 1 0; }
    #retrieve-path { margin: 0 0 1 0; }
    #retrieve-buttons { height: auto; }
    #retrieve-buttons Button { margin: 0 1 0 0; min-width: 12; }
    #retrieve-status { padding: 0 0 0 1; margin: 1 0; color: $text-muted; }
    #retrieve-query-row { height: auto; }
    #retrieve-query { width: 1fr; margin: 0 1 0 0; }
    #retrieve-results { height: 1fr; min-height: 3; }
    #retrieve-actions { dock: bottom; height: 3; padding: 0 1; align: center middle; }
    #retrieve-actions Button { margin: 0 1; min-width: 12; }
    """

    BINDINGS: ClassVar = [
        Binding("escape", "go_back", "Back"),
    ]

    def __init__(self, *, db_dir: Path | None = None) -> None:
        super().__init__()
        self._db_dir = db_dir
        self._busy = False
        self._meta: dict[str, Any] | None = None
        self._db_path: Path | None = None
        self._document_id: str | None = None
        self._document_name: str = ""
        self._chunks: list[dict[str, Any]] | None = None

    # ── layout (D11 order fixes Tab order) ──

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(f"{HEADER_TITLE}\n{HEADER_SUBTITLE}", id="retrieve-header", markup=False)
            yield Input(placeholder="Path to a .pdf or .docx document", id="retrieve-path")
            with Horizontal(id="retrieve-buttons"):
                yield Button("Chunk", id="btn-chunk", variant="default")
                yield Button("Ingest", id="btn-ingest", variant="primary")
            yield Static(FIRST_RUN_MESSAGE, id="retrieve-status", markup=False)
            with Horizontal(id="retrieve-query-row"):
                yield Input(placeholder="Phrase to search for", id="retrieve-query")
                yield Button("Search", id="btn-search", variant="primary")
            yield ListView(id="retrieve-results")
            with Horizontal(id="retrieve-actions"):
                yield Button("Clear index", id="btn-clear", variant="error")
                yield Button("Back (Esc)", id="btn-back", variant="default")

    def on_mount(self) -> None:
        self.query_one("#retrieve-path", Input).focus()
        # The one action with no control of its own: the refresh routine.
        self.call_later(self.action_index_status)

    # ── input routing (D11) ──

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if self._busy:
            event.stop()
            return
        if event.input.id == "retrieve-path":
            await self.action_chunk_document()
        elif event.input.id == "retrieve-query":
            await self.action_retrieve()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        handlers = {
            "btn-chunk": self.action_chunk_document,
            "btn-ingest": self.action_ingest_document,
            "btn-search": self.action_retrieve,
            "btn-clear": self.action_index_clear,
            "btn-back": self.action_go_back,
        }
        handler = handlers.get(event.button.id or "")
        if handler is not None:
            await handler()

    # ── the five actions (D2) ──

    async def action_chunk_document(self) -> None:
        """Parse and chunk the selected document, without touching the index."""
        if self._busy:
            return
        self._set_busy(True)
        try:
            if await self._resolve_selected() is None:
                return
            self._set_status(f"● Chunking {self._document_name}...")
            ok, chunks = await self._run_step(
                "chunking", _retrieval.chunk_document, self._path_value()[1]
            )
            if not ok:
                return
            self._chunks = chunks
            self._set_status(f"✓ Chunked {self._document_name} - {self._chunk_summary(chunks)}")
            await self._refresh_meta()
            self._set_status(
                f"Chunked {self._document_name} - {self._chunk_summary(chunks)} "
                "Press Ingest to index it."
            )
        finally:
            self._set_busy(False)

    async def action_ingest_document(self) -> None:
        """Build the sparse index for the selected document, unless already built."""
        if self._busy:
            return
        self._set_busy(True)
        try:
            db_path = await self._resolve_selected()
            if db_path is None:
                return

            # Data-loss guard, exactly like the CLI: ingest clears the database
            # first, so a reflexive second press would destroy a good index.
            await self._refresh_meta()
            if self._meta is not None and str(self._meta.get("index_status", "")) == "indexed":
                self._set_status(
                    f"Already indexed ({int(self._meta.get('chunk_count', 0))} chunks). "
                    "Clear index first to rebuild."
                )
                return

            if self._chunks is None:
                self._set_status(f"● Chunking {self._document_name}...")
                ok, chunks = await self._run_step(
                    "chunking", _retrieval.chunk_document, self._path_value()[1]
                )
                if not ok:
                    return
                self._chunks = chunks

            chunks = self._chunks
            self._set_status(f"● Ingesting {len(chunks)} chunks...")
            ok, meta = await self._run_step(
                "ingesting",
                _retrieval.ingest_chunks,
                chunks,
                db_path,
                document_id=self._document_id or "",
            )
            if not ok:
                return

            count = int(meta.get("chunk_count", len(chunks)))
            self._set_status(f"✓ Indexed {self._document_name} - {count} chunks.")
            await self._refresh_status_line()
        finally:
            self._set_busy(False)

    async def action_retrieve(self) -> None:
        """Search the selected document's index, or say why that is impossible."""
        if self._busy:
            return
        self._set_busy(True)
        try:
            # D14: every search starts from an empty list. Clearing only on the
            # success path would let a search that cannot run - not indexed,
            # corrupt, interrupted, no query - leave the previous query's rows
            # on screen claiming to be its results.
            self._clear_results()
            db_path = await self._resolve_selected()
            if db_path is None:
                return
            await self._refresh_meta()

            # Layer 1 of D3: refuse before an engine is ever constructed.
            state = _index_state_message(self._meta)
            if state is not None:
                self._set_status(state)
                return

            query = self.query_one("#retrieve-query", Input).value.strip()
            if not query:
                self._fail(NO_QUERY_MESSAGE, severity="warning")
                return

            self._set_status("● Searching...")
            top_k = _retrieval.configured_top_k()
            try:
                results = await asyncio.to_thread(_retrieval.search, db_path, query, top_k=top_k)
            except (IndexNotFoundError, IndexCorruptError) as error:
                # Layer 2: the state changed underneath us. Speak with one voice,
                # by exception type and by the metadata - never the engine's text.
                await self._refresh_meta()
                fallback = (
                    DAMAGED_MESSAGE if isinstance(error, IndexCorruptError) else NOT_INDEXED_MESSAGE
                )
                self._clear_results()
                self._set_status(_index_state_message(self._meta) or fallback)
                return
            except Exception as error:
                self._report_step_error(error, str(db_path), step="searching")
                return

            self._render_results(results, query)
            if results:
                self._set_status(f'Showing top {top_k} matches for "{query}".')
            else:
                self._set_status(f'No matches for "{query}" in {self._document_name}.')
        finally:
            self._set_busy(False)

    async def action_index_status(self) -> None:
        """Refresh the index status and restate it on the status line."""
        if self._busy:
            return
        self._set_busy(True)
        try:
            await self._refresh_status_line()
        finally:
            self._set_busy(False)

    async def action_index_clear(self) -> None:
        """Ask for confirmation, then delete the selected document's index.

        The confirmation needs the resolved ``db_path``, not the metadata row:
        this is the recovery route for an index that cannot be read, so it must
        work when no metadata can be read.
        """
        if self._busy:
            return
        self._set_busy(True)
        try:
            if await self._resolve_selected() is None:
                return
            await self._refresh_meta()
            if self._meta is None:
                self._set_status(NOT_INDEXED_MESSAGE)
                return

            count_sentence = self._chunk_count_sentence()
            self.app.push_screen(
                ConfirmModal(
                    "Clear index",
                    f"Clear the index for {self._document_name}?\n\n"
                    f"{count_sentence}\n\n"
                    "The source file is not touched. Ingesting it again rebuilds "
                    "this index.",
                    danger=True,
                ),
                self._on_clear_confirmed,
            )
        finally:
            self._set_busy(False)

    async def action_go_back(self) -> None:
        self.app.pop_screen()

    # ── confirmation plumbing (D6) ──

    def _on_clear_confirmed(self, confirmed: bool | None) -> None:
        if confirmed:
            self.call_later(self._perform_clear)

    async def _perform_clear(self) -> None:
        db_path = self._db_path
        if self._busy or db_path is None:
            return
        self._set_busy(True)
        try:
            ok, _ = await self._run_step("clearing the index", _retrieval.clear_index, db_path)
            if not ok:
                return
            await self._refresh_status_line()
        finally:
            self._set_busy(False)

    # ── state ──

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Escape must not unmount the screen under an uncancellable worker."""
        return not (action == "go_back" and self._busy)

    def _set_busy(self, busy: bool) -> None:
        """Set the guard synchronously, before any await in the caller."""
        self._busy = busy
        for button_id in _BUTTON_IDS:
            self.query_one(button_id, Button).disabled = busy

    def _set_status(self, message: str) -> None:
        self.query_one("#retrieve-status", Static).update(message)

    def _fail(
        self,
        message: str,
        *,
        severity: Literal["information", "warning", "error"] = "error",
    ) -> None:
        """Report a failure on both channels: persistent copy and a toast."""
        self._set_status(message)
        self.notify(message, severity=severity)

    def _report_step_error(self, error: BaseException, raw_path: str, *, step: str) -> None:
        """Report a failed step. Only the unanticipated branch logs a traceback."""
        if isinstance(error, (ParseError, OSError)):
            self._fail(_error_copy(error, raw_path))
            return
        logger.exception("Unexpected error while %s", step)
        self._fail(f"Unexpected error: {error}")

    async def _run_step(
        self, step: str, func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> tuple[bool, Any]:
        """Run *func* on a worker thread; on failure report it and return ``False``."""
        try:
            return True, await asyncio.to_thread(func, *args, **kwargs)
        except Exception as error:
            self._report_step_error(error, self._raw_path(), step=step)
            return False, None

    def _raw_path(self) -> str:
        return self.query_one("#retrieve-path", Input).value.strip()

    def _path_value(self) -> tuple[str, Path]:
        raw = self._raw_path()
        return raw, Path(raw).expanduser()

    def _chunk_summary(self, chunks: list[dict[str, Any]]) -> str:
        """``{clauses} clauses, {chunks} chunks.``

        Every ``Clause`` carries non-empty text, so every clause yields at least
        one chunk: the distinct source clauses are the parsed clause count.
        """
        clause_count = len({chunk["source_clause_id"] for chunk in chunks})
        return f"{clause_count} clauses, {len(chunks)} chunks."

    async def _resolve_selected(self) -> Path | None:
        """Resolve the path box into an identity, or report why it cannot be."""
        raw = self._raw_path()
        if not raw:
            self._fail(FIRST_RUN_MESSAGE, severity="warning")
            return None
        path = Path(raw).expanduser()
        ok, resolved = await self._run_step(
            "resolving the document",
            _retrieval.resolve_document,
            path,
            db_dir=self._db_dir,
        )
        if not ok:
            return None
        document_id, db_path = resolved
        self._document_id = str(document_id)
        self._db_path = Path(db_path)
        self._document_name = path.name
        return self._db_path

    async def _refresh_meta(self) -> None:
        """Read the index metadata. Damage is a state here, never a crash.

        ``_refresh_meta`` is called by every action, so an error leaving it
        leaves the whole screen: it would reach Textual's ``_handle_exception``,
        whose documented behaviour is app exit with a traceback. A physically
        malformed index raises ``IndexCorruptError`` from the adapter (see
        ``tui/domain/retrieval.py``), which is rendered here as D3's damaged
        state - the one state whose copy tells the user how to recover.
        """
        if self._db_path is None:
            self._meta = None
            return
        try:
            self._meta = await asyncio.to_thread(_retrieval.index_meta, self._db_path)
        except IndexCorruptError:
            self._meta = dict(_DAMAGED_META)

    def _chunk_count_sentence(self) -> str:
        """D6's middle line, or the truth when the index cannot be read at all."""
        count = (self._meta or {}).get("chunk_count")
        if count is None:
            return "This index is damaged, so its chunk count cannot be read."
        return f"{int(count)} chunks are indexed for this document."

    async def _refresh_status_line(self) -> None:
        """Restate the persistent truth for the current document."""
        await self._refresh_meta()
        if self._db_path is None:
            self._set_status(FIRST_RUN_MESSAGE)
            return
        state = _index_state_message(self._meta)
        if state is not None:
            self._set_status(state)
            return
        count = int((self._meta or {}).get("chunk_count", 0))
        self._set_status(
            f"Indexed {self._document_name} - {count} chunks. Enter a phrase below to search."
        )

    # ── results ──

    def _clear_results(self) -> None:
        self.query_one("#retrieve-results", ListView).clear()

    def _render_results(self, results: list[RetrievalResult], query: str) -> None:
        self._clear_results()
        list_view = self.query_one("#retrieve-results", ListView)
        if not results:
            list_view.append(ListItem(Label(f'No matches for "{query}".', markup=False)))
            return
        for rank, result in enumerate(results, start=1):
            heading = " / ".join(result.hierarchy_chain)
            excerpt = " ".join(result.text.split())[:60]
            list_view.append(
                ListItem(
                    Label(
                        f"{rank}. [{heading}] · {result.score:.2f} · {excerpt}",
                        markup=False,
                    )
                )
            )


__all__ = ["RetrieveScreen"]
