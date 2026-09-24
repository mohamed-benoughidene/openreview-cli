"""PromptExportModal — export one prompt to a YAML file.

Pushed with **no callback**: the modal performs the export itself and reports
the outcome through ``self.notify``.  It owns the destination path, the
``.yaml``/``.yml`` suffix gate, the parent-directory creation, the "one prompt"
scope statement and the ``ConfirmModal(danger=True)`` overwrite guard; the store
write itself goes through ``export_prompt_via_tui``, so no store or filesystem
error reaches a Textual handler.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label

_VALID_SUFFIXES = (".yaml", ".yml")


class PromptExportModal(ModalScreen[None]):
    """Export a single prompt to a user-chosen YAML file."""

    DEFAULT_CSS = """
    PromptExportModal { align: center middle; }
    PromptExportModal > Vertical { width: 70; padding: 1 2; background: $surface; border: thick $primary; }
    PromptExportModal #export-title { text-style: bold; margin: 0 0 1 0; }
    PromptExportModal #export-scope { margin: 0 0 1 0; }
    PromptExportModal #export-path { margin: 0 0 1 0; }
    PromptExportModal #export-error { color: $error; margin: 0 0 1 0; }
    PromptExportModal Horizontal { align: center middle; }
    PromptExportModal Button { margin: 0 1; min-width: 10; }
    """

    def __init__(self, prompt_name: str) -> None:
        super().__init__()
        self._prompt_name = prompt_name
        self._writing = False

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Export prompt", id="export-title")
            # markup=False: the prompt name is user-authored and may contain
            # bracketed expressions Rich would otherwise consume.
            yield Label(
                f"Export one prompt to a YAML file: {self._prompt_name}",
                id="export-scope",
                markup=False,
            )
            yield Input(placeholder="/path/to/prompt.yaml", id="export-path")
            yield Label("", id="export-error", markup=False)
            with Horizontal():
                yield Button("Export", id="btn-export-confirm", variant="primary")
                yield Button("Cancel", id="btn-export-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-export-confirm":
            self._start_export()
        elif event.button.id == "btn-export-cancel":
            self.dismiss(None)

    def on_key(self, event: Any) -> None:
        if event.key == "escape":
            event.stop()
            self.dismiss(None)

    def _start_export(self) -> None:
        """Validate the destination, then write directly or after a confirm."""
        if self._writing:
            return
        error = self.query_one("#export-error", Label)
        raw = self.query_one("#export-path", Input).value.strip()
        if not raw:
            error.update("Enter a destination path.")
            return

        dest = Path(raw).expanduser().resolve()
        if dest.suffix not in _VALID_SUFFIXES:
            error.update(f"Destination must end in .yaml or .yml: {dest}")
            return
        if dest.is_dir():
            error.update(f"Destination is a directory: {dest}")
            return

        error.update("")
        if dest.exists():
            self._confirm_overwrite(dest)
            return
        self._write(dest)

    def _confirm_overwrite(self, dest: Path) -> None:
        """Require a destructive confirmation before replacing an existing file."""
        from openreview_cli.tui.screens.confirm import ConfirmModal

        message = f"Overwrite existing file '{dest}'?"

        def on_confirm(confirmed: bool | None) -> None:
            if confirmed:
                self._write(dest)

        self.app.push_screen(ConfirmModal("Overwrite file", message, danger=True), on_confirm)

    def _write(self, dest: Path) -> None:
        """Create the parent directory and write the export, button disabled.

        The button is disabled (and the reentrancy flag set) before the write so
        a double click cannot write the file twice.
        """
        from openreview_cli.tui.domain.prompts import export_prompt_via_tui

        self._writing = True
        button = self.query_one("#btn-export-confirm", Button)
        button.disabled = True
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            export_prompt_via_tui(dest, self._prompt_name)
        except Exception as exc:
            self._writing = False
            button.disabled = False
            self.query_one("#export-error", Label).update(f"Export failed: {exc}")
            self.notify(f"Export failed: {exc}", severity="error", markup=False)
            return

        self.notify(f"Exported '{self._prompt_name}' to {dest}", markup=False)
        self.dismiss(None)
