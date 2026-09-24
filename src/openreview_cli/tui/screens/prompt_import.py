"""PromptImportModal — import prompts from YAML with a validated live preview.

The modal performs the import itself (``import_prompts_via_tui``) and renders
its own result; the tab that pushes it only reloads its list when the modal
closes, so the modal never returns a path.

The preview and the import both validate through the shared
``parse_prompts_yaml``, so they can never disagree about what a document means.
Import commits per item and is **not** atomic, so the result states exactly what
landed and what did not, and never implies all-or-nothing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

_VALID_SUFFIXES = (".yaml", ".yml")


class PromptImportModal(ModalScreen[None]):
    """Import prompts from a YAML file, gated by a live validated preview."""

    DEFAULT_CSS = """
    PromptImportModal { align: center middle; }
    PromptImportModal > Vertical { width: 80; padding: 1 2; background: $surface; border: thick $primary; }
    PromptImportModal #import-title { text-style: bold; margin: 0 0 1 0; }
    PromptImportModal #import-preview { height: 1fr; min-height: 5; margin: 1 0; }
    PromptImportModal #import-validation { margin: 0 0 1 0; }
    PromptImportModal #import-result { margin: 1 0; }
    PromptImportModal Horizontal { align: center middle; }
    PromptImportModal Button { margin: 0 1; min-width: 10; }
    """

    def __init__(self) -> None:
        super().__init__()
        self._path: Path | None = None
        self._importing = False

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Import prompts from YAML", id="import-title")
            yield Label("Enter path to .yaml/.yml file:")
            yield Input(placeholder="/path/to/prompts.yaml", id="import-path-input")
            # markup=False: prompt names are user-authored and may contain
            # bracketed expressions Rich would otherwise consume.
            yield Static("", id="import-preview", markup=False)
            yield Label("", id="import-validation")
            yield Static("", id="import-result", markup=False)
            with Horizontal():
                yield Button("Import", id="btn-import-confirm", variant="primary")
                yield Button("Close", id="btn-import-close")

    def on_mount(self) -> None:
        self.query_one("#import-preview", Static).display = False
        self.query_one("#import-validation", Label).display = False
        self.query_one("#import-result", Static).display = False
        self.query_one("#btn-import-confirm", Button).display = False

    def on_input_changed(self, event: Input.Changed) -> None:
        path_str = event.value.strip()
        if not path_str:
            self._clear_preview()
            return
        path = Path(path_str).expanduser().resolve()
        if not path.exists() or path.suffix not in _VALID_SUFFIXES:
            self._clear_preview()
            return
        self._show_preview(path)

    def _clear_preview(self) -> None:
        self.query_one("#import-preview", Static).display = False
        self.query_one("#import-validation", Label).display = False
        self.query_one("#import-result", Static).display = False
        button = self.query_one("#btn-import-confirm", Button)
        button.display = False
        button.disabled = False
        self._path = None

    def _show_preview(self, path: Path) -> None:
        """Validate ``path`` through ``parse_prompts_yaml`` and describe it.

        A malformed document is refused here, in the preview, with the
        validator's own message; Import stays hidden and the app keeps running.
        """
        from openreview_cli.prompts.io import parse_prompts_yaml

        preview = self.query_one("#import-preview", Static)
        validation = self.query_one("#import-validation", Label)
        import_button = self.query_one("#btn-import-confirm", Button)
        self.query_one("#import-result", Static).display = False

        try:
            data = parse_prompts_yaml(path.read_text())
        except Exception as exc:
            # Arbitrary data + exception text go only to the non-markup widget;
            # #import-validation keeps intentional markup on a controlled string.
            preview.update(f"Validation error:\n{exc}")
            validation.update("[red]\u2717 Invalid document[/]")
            import_button.display = False
            import_button.disabled = False
            self._path = None
        else:
            preview.update(self._describe(data))
            validation.update("[green]\u2713 Valid document[/]")
            import_button.display = True
            import_button.disabled = False
            self._path = path

        preview.display = True
        validation.display = True

    def _describe(self, data: list[dict[str, Any]]) -> str:
        """Render names, per-prompt version counts and the new/existing tally."""
        existing = self._existing_names()
        lines: list[str] = []
        new_count = 0
        existing_count = 0
        for item in data:
            name = str(item["name"])
            count = len(item["versions"])
            if name in existing:
                existing_count += 1
                lines.append(f"{name}: {count} version(s) (already exists)")
            else:
                new_count += 1
                lines.append(f"{name}: {count} version(s)")
        lines.append("")
        lines.append(f"{new_count} new, {existing_count} already exist")
        return "\n".join(lines)

    def _existing_names(self) -> set[str]:
        from openreview_cli.tui.domain.prompts import list_prompts_via_tui

        try:
            return {str(p["name"]) for p in list_prompts_via_tui()}
        except Exception:
            return set()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-import-confirm":
            self._start_import()
        elif event.button.id == "btn-import-close":
            self.dismiss(None)

    def on_key(self, event: Any) -> None:
        if event.key == "escape":
            event.stop()
            self.dismiss(None)

    def _start_import(self) -> None:
        """Run the import, button disabled, and render the honest result."""
        if self._importing or self._path is None:
            return
        from openreview_cli.tui.domain.prompts import import_prompts_via_tui

        path = self._path
        self._importing = True
        button = self.query_one("#btn-import-confirm", Button)
        button.disabled = True
        result_widget = self.query_one("#import-result", Static)
        try:
            result = import_prompts_via_tui(path)
        except Exception as exc:
            self._importing = False
            button.disabled = False
            result_widget.update(f"Import failed: {exc}")
            result_widget.display = True
            self.notify(f"Import failed: {exc}", severity="error", markup=False)
            return

        self._importing = False
        result_widget.update(self._format_result(result))
        result_widget.display = True

    @staticmethod
    def _format_result(result: dict[str, Any]) -> str:
        """Report what landed and what did not; never imply all-or-nothing."""
        imported = [str(name) for name in result.get("imported", [])]
        failed = {str(name): str(reason) for name, reason in result.get("failed", {}).items()}
        total = len(imported) + len(failed)
        summary = f"Imported {len(imported)} of {total}: {', '.join(imported) or 'none'}."
        if failed:
            details = ", ".join(f"{name} ({reason})" for name, reason in failed.items())
            summary += f" Not imported: {details}."
        return summary
