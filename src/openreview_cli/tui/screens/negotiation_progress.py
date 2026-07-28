"""Negotiation progress screen — elapsed time, cancel support."""

from __future__ import annotations

import asyncio
import contextlib
import time
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Label, ProgressBar, Static


class NegotiationProgressScreen(Screen[None]):
    """Progress screen for negotiation: elapsed timer, cancel → ConfirmModal."""

    DEFAULT_CSS = """
    NegotiationProgressScreen #progress-container { width: 60; height: auto; padding: 1 2; }
    NegotiationProgressScreen #title { text-style: bold; padding: 0 0 1 0; }
    NegotiationProgressScreen #elapsed-time { padding: 1 0; color: $text-muted; }
    NegotiationProgressScreen #nav-buttons { dock: bottom; height: 3; align: center middle; }
    NegotiationProgressScreen #nav-buttons Button { margin: 0 1; min-width: 12; }
    """

    def __init__(
        self,
        doc_path: str,
        solver: str = "qre",
        rationality: float = 1.0,
        depth: int = 2,
        weights: dict[str, float] | None = None,
        confidence_threshold: float = 0.7,
        playbook_path: str | None = None,
    ) -> None:
        super().__init__()
        self._doc_path = doc_path
        self._solver = solver
        self._rationality = rationality
        self._depth = depth
        self._weights = weights
        self._confidence_threshold = confidence_threshold
        self._playbook_path = playbook_path
        self._start_time: float = 0.0
        # ponytail: attr name shared with ProgressScreen so _on_signal cancels both
        self._review_task: asyncio.Task[Any] | None = None
        self._cancelled: bool = False

    def compose(self) -> ComposeResult:
        with Vertical(id="progress-container"):
            yield Static("Negotiation in progress...", id="title")
            yield Static("○ Parsing document", id="step-parse")
            yield Static("○ Building assessments", id="step-assess")
            yield Static("○ Computing equilibria", id="step-solve")
            yield Static("○ Generating report", id="step-report")
            yield ProgressBar(id="progress-bar", total=4)
            yield Label("Elapsed: 0s", id="elapsed-time")
        with Horizontal(id="nav-buttons"):
            yield Button("Cancel negotiation", id="btn-cancel", variant="error")

    def on_mount(self) -> None:
        self._start_time = time.monotonic()
        self.set_interval(0.5, self._update_elapsed)
        self._review_task = asyncio.create_task(self._run_negotiation())

    def _update_elapsed(self) -> None:
        elapsed = int(time.monotonic() - self._start_time)
        with contextlib.suppress(Exception):
            self.query_one("#elapsed-time", Label).update(f"Elapsed: {elapsed}s")

    async def _run_negotiation(self) -> None:
        """Execute negotiation and push result screen."""
        from openreview_cli.tui.domain.negotiation import run_negotiation_via_tui
        from openreview_cli.tui.screens.negotiation_result import (
            NegotiationResultScreen,
        )

        # Yield points keep progress screen visible through pilot.pause()
        for _ in range(12):
            await asyncio.sleep(0.01)

        try:
            report = run_negotiation_via_tui(
                doc_path=self._doc_path,
                solver=self._solver,
                rationality=self._rationality,
                depth=self._depth,
                weights=self._weights,
                confidence_threshold=self._confidence_threshold,
                playbook_path=self._playbook_path,
                cancel_requested=self._cancelled,
            )

            if self._cancelled:
                return

            def _show_result() -> None:
                self.app.pop_screen()
                self.app.push_screen(NegotiationResultScreen(report=report))

            self.app.call_later(_show_result)

        except Exception as exc:
            if self._cancelled:
                return
            _error = str(exc)

            def _show_error() -> None:
                self.app.pop_screen()
                self.app.push_screen(NegotiationResultScreen(report=None, error=_error))

            self.app.call_later(_show_error)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self._confirm_cancel()

    def _confirm_cancel(self) -> None:
        from openreview_cli.tui.screens.confirm import ConfirmModal

        def on_cancel(result: bool | None) -> None:
            if result:
                self._cancelled = True
                if self._review_task and not self._review_task.done():
                    self._review_task.cancel()
                self.app.pop_screen()

        self.app.push_screen(
            ConfirmModal("Cancel negotiation", "Are you sure you want to cancel this negotiation?"),
            on_cancel,
        )

    def on_unmount(self) -> None:
        """Ensure task is cancelled when screen is popped externally (signal handler)."""
        self._cancelled = True
        if self._review_task and not self._review_task.done():
            self._review_task.cancel()
