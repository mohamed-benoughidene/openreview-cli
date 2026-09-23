"""Stored-PII screen — view and delete the PII data kept on disk.

Mirrors ``openreview pii list`` and ``pii delete``: the read path is the same
shared inventory query and the delete path is the same retention function, so
the two surfaces cannot disagree. Deletion is permanent, so it always goes
through the confirmation modal.

The list is driven by ``pii_cache``: one entry per document whose encrypted
PII mapping is still stored. A plain review writes such an entry even when the
body carried no personal information, because document metadata is redacted by
default.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Label, ListItem, ListView, Static

from openreview_cli.tui.domain import pii as _pii
from openreview_cli.tui.screens.confirm import ConfirmModal

_EMPTY_MESSAGE = (
    "No stored PII data.\n\n"
    "Entries appear here once a review has redacted personal information. The "
    "encrypted mapping of what was replaced is kept locally so a redaction can "
    "be read back, and it expires 30 days after the review that wrote it."
)


def _row_label(row: dict[str, Any]) -> str:
    entities = row.get("entity_count") or 0
    noun = "entity" if entities == 1 else "entities"
    created = str(row.get("created_at") or "")[:10] or "—"
    expires = str(row.get("expiry_at") or "")[:10] or "—"
    return (
        f"{str(row['document_hash'])[:12]}   {entities} {noun}   "
        f"created {created}   expires {expires}"
    )


def _artifacts_dir(row: dict[str, Any]) -> str:
    mapping_path = row.get("mapping_path")
    if mapping_path:
        return str(Path(str(mapping_path)).parent)
    return f"reviews/{str(row['document_hash'])[:12]}"


class PiiDataScreen(Screen[None]):
    """List stored PII records and delete one document's worth."""

    DEFAULT_CSS: ClassVar[str] = """
    PiiDataScreen { padding: 1; }
    #pii-header { text-style: bold; background: $primary; color: $text; padding: 1 2; margin: 0 0 1 0; }
    #pii-subtitle { padding: 0 0 0 1; margin: 0 0 1 0; color: $text-muted; }
    #pii-list { height: 1fr; min-height: 3; }
    #pii-empty { padding: 1 2; color: $text-muted; }
    #pii-actions { dock: bottom; height: 3; padding: 0 1; align: center middle; }
    #pii-actions Button { margin: 0 1; min-width: 12; }
    """

    BINDINGS: ClassVar = [
        ("escape", "pop_screen", "Back"),
        ("d", "request_delete", "Delete"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._rows: list[dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Stored PII data", id="pii-header")
            yield Static(id="pii-subtitle")
            yield ListView(id="pii-list")
            yield Static(_EMPTY_MESSAGE, id="pii-empty")
            with Horizontal(id="pii-actions"):
                yield Button(
                    "Delete selected PII (D)",
                    id="btn-delete-pii",
                    variant="error",
                    disabled=True,
                )
                yield Button("Back (Esc)", id="btn-pii-back", variant="default")

    def on_mount(self) -> None:
        self._load()

    def _load(self) -> None:
        """Fetch stored PII records and render them."""
        self._rows = _pii.list_stored_pii_via_tui()

        list_view = self.query_one("#pii-list", ListView)
        empty = self.query_one("#pii-empty", Static)
        delete_button = self.query_one("#btn-delete-pii", Button)
        subtitle = self.query_one("#pii-subtitle", Static)

        list_view.clear()
        delete_button.disabled = True

        if not self._rows:
            list_view.display = False
            empty.display = True
            subtitle.update("Nothing stored.")
            return

        list_view.display = True
        empty.display = False
        subtitle.update(f"{len(self._rows)} document(s) with a stored PII mapping, newest first.")
        for row in self._rows:
            list_view.append(ListItem(Label(_row_label(row), markup=False)))

    def _selected_row(self) -> dict[str, Any] | None:
        index = self.query_one("#pii-list", ListView).index
        if index is None or index >= len(self._rows):
            return None
        return self._rows[index]

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        self.query_one("#btn-delete-pii", Button).disabled = self._selected_row() is None

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-delete-pii":
            self.action_request_delete()
        elif event.button.id == "btn-pii-back":
            self.app.pop_screen()

    def action_request_delete(self) -> None:
        """Ask for confirmation, then delete the selected document's PII."""
        row = self._selected_row()
        if row is None:
            return

        document_hash = str(row["document_hash"])
        entities = row.get("entity_count") or 0
        noun = "entity" if entities == 1 else "entities"

        def _on_confirmed(confirmed: bool | None) -> None:
            if confirmed:
                self._delete(document_hash)

        self.app.push_screen(
            ConfirmModal(
                "Delete stored PII",
                f"Permanently delete the stored PII data for document "
                f"{document_hash}?\n\n"
                f"{entities} redacted {noun} recorded. Artifacts: "
                f"{_artifacts_dir(row)}\n\n"
                f"The encrypted mapping is the only way to reverse the redaction "
                f"in this document, so this cannot be undone.",
                danger=True,
            ),
            _on_confirmed,
        )

    def _delete(self, document_hash: str) -> None:
        result = _pii.delete_pii_document_via_tui(document_hash)
        if result["mapping_removed"] or result["cache_removed"] or result["audit_records"]:
            self.notify(f"Deleted stored PII for {document_hash[:12]}.", timeout=3)
        else:
            self.notify(f"No stored PII found for {document_hash[:12]}.", severity="warning")
        self._load()

    def action_pop_screen(self) -> None:
        self.app.pop_screen()


__all__ = ["PiiDataScreen"]
