"""Prompt version history and unified-diff screens (Task 2).

``PromptHistoryScreen`` reuses the playbook ``VersionHistoryScreen`` list,
markers, and buttons, overriding only the diff-opening hook so it fetches a
prompt unified diff.  The diff body of ``PromptDiffScreen`` renders as a Rich
``Text`` with ``markup=False`` because prompt content is user-authored and may
contain bracketed expressions the Rich markup parser would otherwise consume.
"""

from __future__ import annotations

from typing import Any

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

from openreview_cli.tui.screens.playbook_detail import VersionHistoryScreen


class PromptHistoryScreen(VersionHistoryScreen):
    """Version history list for a prompt.

    Inherits the list rendering, current/latest markers, and action buttons
    from ``VersionHistoryScreen``; only the diff hook is prompt-specific.
    """

    def __init__(
        self,
        prompt_name: str,
        rows: list[dict[str, Any]],
        current_version: int,
    ) -> None:
        super().__init__(item_id=prompt_name, rows=rows, current_version=current_version)

    def _open_diff(self, v1: int, v2: int) -> None:
        from openreview_cli.tui.domain.prompts import get_prompt_version_diff

        try:
            diff = get_prompt_version_diff(self._item_id, v1, v2)
        except Exception as exc:
            self.notify(f"Diff error: {exc}", timeout=3)
            return
        self.app.push_screen(PromptDiffScreen(self._item_id, v1, v2, diff))


class PromptDiffScreen(ModalScreen[None]):
    """Full-screen unified diff view for a prompt version pair."""

    DEFAULT_CSS = """
    PromptDiffScreen { align: center middle; }
    PromptDiffScreen > Vertical { width: 80; height: 90%; padding: 1 2; background: $surface; border: thick $primary; }
    PromptDiffScreen #diff-title { text-style: bold; margin: 0 0 1 0; }
    PromptDiffScreen #diff-content { height: 1fr; }
    PromptDiffScreen #diff-close { margin: 1 0 0 0; }
    """

    def __init__(self, prompt_name: str, v1: int, v2: int, diff_text: str) -> None:
        super().__init__()
        self._prompt_name = prompt_name
        self._v1 = v1
        self._v2 = v2
        self._diff_text = diff_text

    def compose(self) -> ComposeResult:
        with Vertical():
            # markup=False: the prompt name is user-authored and may contain
            # brackets that the markup parser would otherwise consume.
            yield Label(
                f"Version diff: {self._prompt_name} (v{self._v1} → v{self._v2})",
                id="diff-title",
                markup=False,
            )
            with ScrollableContainer(id="diff-content"):
                yield Static(self._render_diff(), id="diff-body", markup=False)
            yield Button("Close", id="diff-close", variant="default")

    def _render_diff(self) -> Text:
        """Colorize the raw diff as a Rich ``Text`` without markup parsing.

        Added lines (``+``, excluding the ``+++`` header) are green and removed
        lines (``-``, excluding the ``---`` header) are red; every other line
        keeps the default style.
        """
        text = Text()
        for line in self._diff_text.splitlines(keepends=True):
            if line.startswith("+++") or line.startswith("---"):
                text.append(line)
            elif line.startswith("+"):
                text.append(line, style="green")
            elif line.startswith("-"):
                text.append(line, style="red")
            else:
                text.append(line)
        return text

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "diff-close":
            self.dismiss()

    def on_key(self, event: Any) -> None:
        if event.key == "escape":
            self.dismiss()
