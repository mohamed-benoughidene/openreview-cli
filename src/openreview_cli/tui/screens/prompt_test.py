"""PromptTestModal — validate version numbers and report the A/B stub honestly.

``prompt test`` is a stub in the CLI (``prompts/cli.py:213-237``): it validates
that the prompt and each named version exist, then exits 3 with the roadmap
notice.  There is no A/B harness anywhere in the repository, so this modal
mirrors that honesty — it validates against the real store and then states the
limitation.  It never calls a model, never makes a network or gateway call, and
never imports ``openreview_cli.gateway`` or ``litellm`` (AGENTS.md:226).

The tab pushes it with the latest version already resolved and **no** result
callback (``tabs/prompts.py:275-283``); it therefore does all of its own work
and reports inline.
"""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

# Mirrors the CLI stub's notice verbatim (``prompts/cli.py:234-236``); it never
# implies that a model was called.
NOTICE = (
    "A/B testing requires the benchmark harness (roadmap N-3). Configure a benchmark to proceed."
)
# The message for every malformed version list.
PARSE_ERROR = "Versions must be comma-separated version numbers"


class PromptTestModal(ModalScreen[None]):
    """Validate a prompt's versions and report the A/B stub limitation."""

    DEFAULT_CSS = """
    PromptTestModal { align: center middle; }
    PromptTestModal > Vertical { width: 72; padding: 1 2; background: $surface; border: thick $primary; }
    PromptTestModal #prompt-test-title { text-style: bold; margin: 0 0 1 0; }
    PromptTestModal #prompt-test-versions { margin: 0 0 1 0; }
    PromptTestModal #prompt-test-error { color: $error; margin: 0 0 1 0; }
    PromptTestModal #prompt-test-notice { margin: 0 0 1 0; }
    PromptTestModal Horizontal { align: center middle; }
    PromptTestModal Button { margin: 0 1; }
    """

    def __init__(self, prompt_name: str, latest_version: int) -> None:
        super().__init__()
        self._prompt_name = prompt_name
        self._latest_version = latest_version

    def compose(self) -> ComposeResult:
        with Vertical():
            # markup=False: the prompt name is user-authored and may contain
            # bracketed text (e.g. "[clause]") the Rich markup parser would
            # otherwise consume.
            yield Label(
                f"Test prompt: {self._prompt_name}",
                id="prompt-test-title",
                markup=False,
            )
            yield Label("Versions (comma-separated):")
            yield Input(value=str(self._latest_version), id="prompt-test-versions")
            # markup=False: the error body carries the prompt name verbatim.
            yield Label("", id="prompt-test-error", markup=False)
            yield Static("", id="prompt-test-notice", markup=False)
            with Horizontal():
                yield Button("Validate", variant="primary", id="prompt-test-run")
                yield Button("Cancel", id="prompt-test-cancel")

    def on_mount(self) -> None:
        self.query_one("#prompt-test-versions", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "prompt-test-run":
            self._validate()
        elif event.button.id == "prompt-test-cancel":
            self.dismiss()

    def on_key(self, event: Any) -> None:
        if event.key == "escape":
            event.stop()
            self.dismiss()

    @staticmethod
    def _parse_versions(raw: str) -> list[int] | None:
        """Parse ``raw`` into a list of ints, or ``None`` when it is malformed.

        The empty-token guard the CLI lacks: ``cli.py:226`` runs ``int("")`` on
        ``"1,"`` and raises an uncaught ``ValueError``.  Here every empty token
        (``"1,"``, ``""``) and every non-integer token (``"abc"``, ``"1 2"``)
        is rejected with ``PARSE_ERROR`` instead of reaching a handler.
        """
        tokens = [token.strip() for token in raw.split(",")]
        if any(token == "" for token in tokens):
            return None
        try:
            return [int(token) for token in tokens]
        except ValueError:
            return None

    def _validate(self) -> None:
        """Validate the version list inline; never dismiss and never raise."""
        error = self.query_one("#prompt-test-error", Label)
        notice = self.query_one("#prompt-test-notice", Static)
        notice.update("")

        raw = self.query_one("#prompt-test-versions", Input).value
        versions = self._parse_versions(raw)
        if versions is None:
            error.update(PARSE_ERROR)
            return

        # Lazy import: the domain wrapper is the only layer that touches the
        # store, and importing it here keeps this module import-cheap.
        from openreview_cli.tui.domain.prompts import validate_prompt_test_via_tui

        try:
            # No wrapper error may reach a Textual handler: surface it inline.
            validate_prompt_test_via_tui(self._prompt_name, versions)
        except Exception as exc:
            error.update(str(exc))
            return

        error.update("")
        notice.update(NOTICE)
        self.notify(NOTICE, severity="information", markup=False)
