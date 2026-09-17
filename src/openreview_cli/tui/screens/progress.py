"""Progress screen — pipeline steps, elapsed time, cancel support."""

from __future__ import annotations

import asyncio
import contextlib
import time
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Label, ProgressBar, Static

from openreview_cli.pipeline.progress import ProgressEvent

# The five user-facing steps, in execution order.  The review pipeline emits
# stage events for ``parse`` / ``strip`` / ``review``; ``review`` covers the
# last three UI steps (extract + QA + report).
_STEP_IDS: tuple[str, ...] = (
    "step-parse",
    "step-pii",
    "step-extract",
    "step-qa",
    "step-report",
)
_STEP_LABELS: tuple[str, ...] = (
    "Parsing document",
    "Stripping PII",
    "Extracting clauses",
    "QA verification",
    "Building report",
)
# Pipeline stage name -> UI step index it starts/stops at.
_STAGE_START: dict[str, int] = {"parse": 0, "strip": 1, "review": 2}
# Checklist glyphs, keyed by step state.
_MARKERS: dict[str, str] = {
    "pending": "\u25cb",
    "active": "\u25cf",
    "done": "\u2713",
    "failed": "\u2717",
}


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
        client_id: str | None = None,
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
        self._client_id = client_id
        self._start_time: float = 0.0
        self._review_task: asyncio.Task[Any] | None = None
        self._cancelled: bool = False

    def compose(self) -> ComposeResult:
        with Vertical(id="progress-container"):
            yield Static("Review in progress...", id="title")
            for step_id, text in zip(_STEP_IDS, _STEP_LABELS, strict=True):
                yield Static(f"{_MARKERS['pending']} {text}", id=step_id)
            yield ProgressBar(id="progress-bar", total=len(_STEP_IDS))
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

    def _on_progress_event(self, event: ProgressEvent) -> None:
        """Forward a pipeline event from the worker thread to the UI thread."""
        try:
            self.app.call_from_thread(self._apply_progress_event, event)
        except Exception:
            # App not mounted / shutting down — progress is best-effort.
            pass

    def _apply_progress_event(self, event: ProgressEvent) -> None:
        """Translate a pipeline ``ProgressEvent`` into step markers + bar moves."""
        index = _STAGE_START.get(event.stage_name)
        if index is None:
            return
        if event.status == "running":
            self._set_step(index, "active")
            self._set_bar(index)
        elif event.status in ("completed", "skipped"):
            self._set_step(index, "done")
            if event.stage_name == "review":
                for i in range(index, len(_STEP_IDS)):
                    self._set_step(i, "done")
                self._set_bar(len(_STEP_IDS))
            else:
                self._set_bar(index + 1)
        elif event.status == "failed":
            self._set_step(index, "failed")

    def _set_step(self, index: int, state: str) -> None:
        with contextlib.suppress(Exception):
            label = self.query_one(f"#{_STEP_IDS[index]}", Static)
            label.update(f"{_MARKERS[state]} {_STEP_LABELS[index]}")

    def _set_bar(self, progress: int) -> None:
        with contextlib.suppress(Exception):
            self.query_one("#progress-bar", ProgressBar).update(progress=progress)

    async def _run_review(self) -> None:
        """Execute review off the event loop and push the result screen."""
        from openreview_cli.tui.domain.review import run_review_via_tui
        from openreview_cli.tui.screens.result import ResultScreen

        # Yield points keep ProgressScreen visible through pilot.pause()
        for _ in range(12):
            await asyncio.sleep(0.01)

        try:
            # Blocking pipeline runs on a worker thread so the bar and step
            # markers can repaint while it proceeds.  Events arrive on that
            # thread and are marshalled back via ``_on_progress_event``.
            reports = await asyncio.to_thread(
                run_review_via_tui,
                paths=self._paths,
                mode=self._mode,
                disable_pii=self._disable_pii,
                playbook_id=self._playbook_id,
                playbook_path=self._playbook_path,
                extraction_model=self._extraction_model,
                qa_model=self._qa_model,
                confidence_threshold=self._confidence_threshold,
                client_id=self._client_id,
                cancel_requested=self._cancelled,
                progress_callback=self._on_progress_event,
            )

            # If cancelled during run_review_via_tui (e.g. signal handler
            # popped us while sync code was executing), don't push result.
            if self._cancelled:
                return

            def _show_result() -> None:
                self.app.pop_screen()
                self.app.push_screen(ResultScreen(reports=reports, mode=self._mode))

            self.app.call_later(_show_result)

        except Exception as exc:
            if self._cancelled:
                return
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
                self._cancelled = True
                if self._review_task and not self._review_task.done():
                    self._review_task.cancel()
                self.app.pop_screen()

        self.app.push_screen(
            ConfirmModal("Cancel review", "Are you sure you want to cancel this review?"),
            on_cancel,
        )

    def on_unmount(self) -> None:
        """Ensure review task is cancelled when screen is popped externally.

        This covers the case where a signal handler (SIGTERM/SIGINT) pops
        the screen while a review is in-flight — the task will be GC'd when
        the event loop shuts down, but we also cancel it explicitly so any
        pending CancelledError is raised cleanly (Edge case 6).
        """
        self._cancelled = True
        if self._review_task and not self._review_task.done():
            self._review_task.cancel()
