"""Spinner — animated status indicator.

Wraps ``rich.status.Status``.  In TTY mode the spinner animates;
in non-TTY mode it prints the label once (no animation).
Quiet mode suppresses all output.  KeyboardInterrupt is caught
and swallowed (clean exit).
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from rich.status import Status

from openreview_cli.ui.console import renderer

if TYPE_CHECKING:
    from types import TracebackType

    from rich.console import Console


class Spinner:
    """Context manager that displays an animated (or static) status label.

    Parameters
    ----------
    label:
        The status text shown while the spinner is active.
    spinner:
        Rich spinner style name (e.g. ``"dots"``, ``"line"``).
        Default ``"dots"``.
    quiet:
        If True, all output is suppressed.
    console:
        Rich Console instance to render to.  Defaults to the application-wide
        ``SGRenderer`` singleton.
    """

    def __init__(
        self,
        label: str,
        *,
        spinner: str = "dots",
        quiet: bool = False,
        console: Console | None = None,
    ) -> None:
        self._label = label
        self._spinner = spinner
        self._quiet = quiet
        self._console = console or renderer.console
        self._is_interactive = self._console.is_interactive
        self._status: Status | None = None

    # ------------------------------------------------------------------
    # Context manager protocol
    # ------------------------------------------------------------------

    def __enter__(self) -> Spinner:
        if self._quiet or renderer.no_spinner:
            return self

        if self._is_interactive:
            self._status = Status(
                self._label,
                spinner=self._spinner,
                console=self._console,
            )
            self._status.start()
        else:
            print(f"{self._label}...", file=sys.stderr)

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool | None:
        # Clean up Rich status first (if any)
        if self._status is not None:
            self._status.stop()

        # Suppress KeyboardInterrupt so the application can exit gracefully
        if isinstance(exc_val, KeyboardInterrupt):
            return True

        return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(self, label: str) -> None:
        """Change the displayed label text."""
        self._label = label
        if self._status is not None:
            self._status.update(label)
