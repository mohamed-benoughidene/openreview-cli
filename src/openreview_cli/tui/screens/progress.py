"""Progress screen — pipeline steps, elapsed time, cancel support."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Label, ProgressBar, Static


class ProgressScreen(Screen[None]):
    """Pipeline progress: 5 steps, elapsed timer, cancel -> ResultScreen."""

    DEFAULT_CSS = """
    ProgressScreen #progress-container { width: 60; height: auto; padding: 1 2; }
    ProgressScreen #title { text-style: bold; padding: 0 0 1 0; }
    ProgressScreen #elapsed-time { padding: 1 0; color: $text-muted; }
    ProgressScreen #nav-buttons { dock: bottom; height: 3; align: center middle; }
    ProgressScreen #nav-buttons Button { margin: 0 1; min-width: 12; }
    """

    def __init__(
        self,
        paths: list[str],
        mode: str = "precheck",
        disable_pii: bool = False,
        playbook_id: str | None = None,
        playbook_path: str | None = None,
        extraction_model: str = "extraction",
        qa_model: str | None = None,
        confidence_threshold: float = 0.7,
    ) -> None:
        super().__init__()
        self._paths = paths
        self._mode = mode
        self._disable_pii = disable_pii
        self._playbook_id = playbook_id
        self._playbook_path = playbook_path
        self._extraction_model = extraction_model
        self._qa_model = qa_model
        self._confidence_threshold = confidence_threshold
        self._start_time: float = 0.0
        self._review_task: asyncio.Task[Any] | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="progress-container"):
            yield Static("Review in progress...", id="title")
            yield Static("○ Parsing document", id="step-parse")
            yield Static("○ Stripping PII", id="step-pii")
            yield Static("○ Extracting clauses", id="step-extract")
            yield Static("○ QA verification", id="step-qa")
            yield Static("○ Building report", id="step-report")
            yield ProgressBar(id="progress-bar", total=5)
            yield Label("Elapsed: 0s", id="elapsed-time")
        with Horizontal(id="nav-buttons"):
            yield Button("Cancel review", id="btn-cancel", variant="error")

    def on_mount(self) -> None:
        self._start_time = time.monotonic()
        self.set_interval(0.5, self._update_elapsed)
        self._review_task = asyncio.create_task(self._run_review())

    def _update_elapsed(self) -> None:
        elapsed = int(time.monotonic() - self._start_time)
        try:
            self.query_one("#elapsed-time", Label).update(f"Elapsed: {elapsed}s")
        except Exception:
            pass

    async def _run_review(self) -> None:
        """Execute review and push result screen."""
        from openreview_cli.tui.domain.review import run_review_via_tui
        from openreview_cli.tui.screens.result import ResultScreen

        # Yield points keep ProgressScreen visible through pilot.pause()
        for _ in range(12):
            await asyncio.sleep(0.01)

        try:
            reports = run_review_via_tui(
                paths=self._paths,
                mode=self._mode,
                disable_pii=self._disable_pii,
                playbook_id=self._playbook_id,
                playbook_path=self._playbook_path,
                extraction_model=self._extraction_model,
                qa_model=self._qa_model,
                confidence_threshold=self._confidence_threshold,
            )

            def _show_result() -> None:
                self.app.pop_screen()
                self.app.push_screen(ResultScreen(reports=reports, mode=self._mode))

            self.app.call_later(_show_result)

        except Exception as exc:
            _error = str(exc)

            def _show_error() -> None:
                self.app.pop_screen()
                self.app.push_screen(ResultScreen(reports=[], mode=self._mode, error=_error))

            self.app.call_later(_show_error)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self._confirm_cancel()

    def _confirm_cancel(self) -> None:
        """Open confirm modal before cancelling."""
        from openreview_cli.tui.screens.confirm import ConfirmModal

        def on_cancel(result: bool | None) -> None:
            if result:
                if self._review_task and not self._review_task.done():
                    self._review_task.cancel()
                self.app.pop_screen()

        self.app.push_screen(
            ConfirmModal("Cancel review", "Are you sure you want to cancel this review?"),
            on_cancel,
        )
