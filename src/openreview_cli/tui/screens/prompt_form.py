"""PromptFormScreen — modal create/edit form for a prompt.

The form is *input only*: it collects the fields and dismisses with them.  The
caller owns the store write (``create_prompt_via_tui`` / ``update_prompt_via_tui``)
and reports any failure, so this screen never imports the domain layer and never
writes anything.  It validates only that a name and content are present; the
content-size rule belongs to the store alone (a byte limit on ``create`` and a
character ``CHECK`` on ``update``), so the form is never stricter than the store.
"""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, TextArea


class PromptFormScreen(ModalScreen[dict[str, Any] | None]):
    """Prompt create/edit form; dismisses with the field dict, or None on cancel."""

    DEFAULT_CSS = """
    PromptFormScreen { align: center middle; }
    PromptFormScreen > Vertical { width: 70; padding: 1 2; background: $surface; border: thick $primary; }
    PromptFormScreen #prompt-form-title { text-style: bold; margin: 0 0 1 0; }
    PromptFormScreen Input { margin: 0 0 1 0; }
    PromptFormScreen #prompt-form-content { height: 8; margin: 0 0 1 0; }
    PromptFormScreen #prompt-form-error { color: $error; margin: 0 0 1 0; }
    PromptFormScreen Horizontal { align: center middle; }
    PromptFormScreen Button { margin: 0 1; }
    """

    def __init__(
        self,
        name: str | None = None,
        content: str = "",
        tags: list[str] | None = None,
        description: str = "",
    ) -> None:
        super().__init__()
        self._edit_mode = name is not None
        self._initial_name = name or ""
        self._initial_content = content
        self._initial_tags = tags or []
        self._initial_description = description

    def compose(self) -> ComposeResult:
        title = f"Edit prompt: {self._initial_name}" if self._edit_mode else "New prompt"
        tags_value = ", ".join(self._initial_tags)
        with Vertical():
            # markup=False: the name is user-authored and may contain bracketed
            # text (e.g. "[clause]") that Rich would otherwise consume as markup.
            yield Label(title, id="prompt-form-title", markup=False)
            yield Input(
                placeholder="Name",
                value=self._initial_name,
                id="prompt-form-name",
                disabled=self._edit_mode,
            )
            yield TextArea(self._initial_content, id="prompt-form-content")
            yield Input(
                placeholder="Tags (comma-separated, optional)",
                value=tags_value,
                id="prompt-form-tags",
            )
            yield Input(
                placeholder="Description (optional)",
                value=self._initial_description,
                id="prompt-form-description",
            )
            yield Label("", id="prompt-form-error")
            with Horizontal():
                yield Button("Save", variant="primary", id="prompt-save")
                yield Button("Cancel", id="prompt-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "prompt-save":
            self._save()
        elif event.button.id == "prompt-cancel":
            self.dismiss(None)

    def on_key(self, event: Any) -> None:
        # Enter submits from the single-line fields.  Inside the content
        # TextArea, TextArea consumes Enter to insert a newline (it stops the
        # key event), so multi-line content stays editable; Escape cancels from
        # anywhere.
        if event.key == "enter":
            self._save()
        elif event.key == "escape":
            self.dismiss(None)

    def _save(self) -> None:
        name = self.query_one("#prompt-form-name", Input).value.strip()
        content = self.query_one("#prompt-form-content", TextArea).text.strip()
        error_label = self.query_one("#prompt-form-error", Label)

        if not name:
            error_label.update("Name is required")
            return
        if not content:
            error_label.update("Content is required")
            return

        tags_text = self.query_one("#prompt-form-tags", Input).value
        tags = [tag.strip() for tag in tags_text.split(",") if tag.strip()]
        description = self.query_one("#prompt-form-description", Input).value.strip()

        self.dismiss(
            {
                "name": name,
                "content": content,
                "tags": tags,
                "description": description,
            }
        )
