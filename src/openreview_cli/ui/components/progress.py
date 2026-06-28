"""Progress — determinate progress bar.

Wraps ``rich.progress.Progress``.  In TTY mode the bar animates;
in non-TTY mode one-line status updates are printed at 10 Hz max.
Quiet mode suppresses all output.
"""

from __future__ import annotations

import sys
import time
from typing import TYPE_CHECKING

from rich.progress import (
    BarColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)
from rich.progress import (
    Progress as RichProgress,
)

from openreview_cli.ui.console import renderer

if TYPE_CHECKING:
    from types import TracebackType

    from rich.console import Console


class Progress:
    """Context manager that displays a determinate progress bar.

    Parameters
    ----------
    total:
        Total number of steps.
    description:
        Initial description label.
    quiet:
        If True, all output is suppressed.
    console:
        Rich Console instance to render to.  Defaults to the application-wide
        ``SGRenderer`` singleton.
    """

    def __init__(
        self,
        total: int,
        description: str,
        *,
        quiet: bool = False,
        console: Console | None = None,
    ) -> None:
        self._total = total
        self._description = description
        self._quiet = quiet
        self._console = console or renderer.console
        self._is_interactive = self._console.is_interactive
        self._current = 0
        self._cancelled = False
        self._last_print = 0.0
        self._rich_progress: RichProgress | None = None
        self._task_id: TaskID | None = None

    # ------------------------------------------------------------------
    # Context manager protocol
    # ------------------------------------------------------------------

    def __enter__(self) -> Progress:
        if self._quiet or renderer.no_spinner:
            return self

        if self._is_interactive:
            self._rich_progress = RichProgress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                console=self._console,
            )
            self._rich_progress.start()
            self._task_id = self._rich_progress.add_task(
                self._description,
                total=self._total,
            )
        else:
            self._print_status()

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._rich_progress is not None:
            self._rich_progress.stop()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def advance(self, n: int = 1) -> None:
        """Advance progress by *n* steps."""
        self._current += n
        if self._quiet:
            return

        if self._rich_progress is not None and self._task_id is not None:
            self._rich_progress.advance(self._task_id, advance=n)
        elif not self._is_interactive:
            self._throttled_print()

    def update(self, description: str) -> None:
        """Change the description label."""
        self._description = description
        if self._quiet:
            return

        if self._rich_progress is not None and self._task_id is not None:
            self._rich_progress.update(self._task_id, description=description)
        elif not self._is_interactive:
            self._throttled_print()

    def cancel(self) -> None:
        """Cancel the progress bar and print ``Cancelled``."""
        self._cancelled = True
        if self._quiet:
            return

        if self._rich_progress is not None:
            self._rich_progress.stop()
            self._rich_progress = None
            self._task_id = None

        print("Cancelled", file=sys.stderr)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _throttled_print(self) -> None:
        """Print a status line at most 10 times per second."""
        now = time.monotonic()
        if now - self._last_print < 0.1:  # 10 Hz ceiling
            return
        self._last_print = now
        self._print_status()

    def _print_status(self) -> None:
        print(f"[{self._current}/{self._total}] {self._description}", file=sys.stderr)
