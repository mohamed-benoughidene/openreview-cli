"""Negotiation result screen — memo view, export, experimental notice."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Label, Static

if TYPE_CHECKING:
    from openreview_cli.negotiation.models import NegotiationReport


class NegotiationResultScreen(Screen[None]):
    """Result screen: memo text, disclaimer, export to .md file."""

    DEFAULT_CSS = """
    NegotiationResultScreen #result-container { height: 100%; }
    NegotiationResultScreen #result-header { text-style: bold; background: $primary; color: $text; padding: 1 2; }
    NegotiationResultScreen #memo-scroll { height: 1fr; overflow-y: auto; padding: 0 1; }
    NegotiationResultScreen #disclaimer-box { background: $warning 20%; padding: 1; margin: 1 0; }
    NegotiationResultScreen #result-nav { dock: bottom; height: 3; padding: 0 1; align: center middle; }
    NegotiationResultScreen #result-nav Button { margin: 0 1; min-width: 12; }
    """

    BINDINGS: ClassVar = [
        Binding("escape", "close", "Close"),
    ]

    def __init__(
        self,
        report: NegotiationReport | None = None,
        error: str | None = None,
    ) -> None:
        super().__init__()
        self._report = report
        self._error = error

    def compose(self) -> ComposeResult:
        with Vertical(id="result-container"):
            if self._error:
                yield Static(f"Negotiation failed: {self._error}", id="result-header")
                yield Container(Static("An error occurred during negotiation."), id="memo-scroll")
            elif self._report is None:
                yield Static("Negotiation cancelled", id="result-header")
                yield Container(Static("The negotiation was cancelled."), id="memo-scroll")
            else:
                yield Static("Negotiation complete", id="result-header")
                # Build memo text lazily
                from openreview_cli.negotiation.report import format_memo

                memo_text = format_memo(self._report)
                children: list[Static | Label] = [
                    Static(
                        f"⚡ EXPERIMENTAL — {self._report.disclaimer or 'Advisory only.'}",
                        id="disclaimer-box",
                    ),
                    Label(memo_text, id="memo-text"),
                ]
                yield Container(*children, id="memo-scroll")
            with Horizontal(id="result-nav"):
                if self._report is not None and not self._error:
                    yield Button("Export memo (.md)", id="btn-export", variant="primary")
                yield Button("Close", id="btn-close", variant="default")

    def action_close(self) -> None:
        self.app.pop_screen()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "btn-close":
            self.action_close()
        elif btn_id == "btn-export":
            await self._do_export()

    async def _do_export(self) -> None:
        """Write memo to a .md file in /tmp/."""
        if self._report is None:
            self.notify("No report to export.", severity="error")
            return
        from openreview_cli.negotiation.report import format_memo

        try:
            memo_text = format_memo(self._report)
            out_path = Path("/tmp/negotiation-result.md")
            out_path.write_text(memo_text, encoding="utf-8")
            self.notify(f"Exported to {out_path}", severity="information", timeout=5)
        except Exception as exc:
            self.notify(f"Export error: {exc}", severity="error")
