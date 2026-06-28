"""StatusLine — in-place status line with mode prefix and message.

Context manager that displays a ``[mode] message`` status line.
In TTY mode the line is updated in-place via ``\\r`` carriage returns.
In non-TTY mode the final message is printed once to stderr on exit.
``--quiet`` suppresses all output.  Messages longer than 60 characters
are truncated with a ``…`` suffix.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from openreview_cli.ui.console import renderer

if TYPE_CHECKING:
    from types import TracebackType

    from rich.console import Console

_MAX_LABEL_LEN = 60


class StatusLine:
    """Context manager for an in-place status line.

    Parameters
    ----------
    mode:
        Short label shown in brackets, e.g. ``"parsing"``.
    message:
        Initial status message.
    quiet:
        If True, all output is suppressed.
    console:
        Rich Console instance.  Defaults to the application-wide
        ``SGRenderer`` singleton.
    """

    def __init__(
        self,
        mode: str,
        message: str = "",
        *,
        quiet: bool = False,
        console: Console | None = None,
    ) -> None:
        self._mode = mode
        self._message = message
        self._quiet = quiet
        self._console = console or renderer.console
        self._is_interactive = self._console.is_interactive
        self._finalized = False

    # ------------------------------------------------------------------
    # Context manager protocol
    # ------------------------------------------------------------------

    def __enter__(self) -> StatusLine:
        if not self._quiet:
            self._write(self._message)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool | None:
        if not self._quiet:
            if self._is_interactive:
                # Final write with newline to push cursor to next line
                self._write(self._message, newline=True)
            else:
                # Non-TTY: print final message to stderr once
                print(
                    f"[{self._mode}] {self._truncate(self._message)}",
                    file=sys.stderr,
                )
        return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(self, message: str) -> None:
        """Change the displayed message."""
        self._message = message
        if not self._quiet and self._is_interactive:
            self._write(message)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _truncate(self, text: str) -> str:
        """Truncate *text* to ``_MAX_LABEL_LEN`` characters."""
        if len(text) > _MAX_LABEL_LEN:
            return text[:_MAX_LABEL_LEN] + "…"
        return text

    def _write(self, message: str, *, newline: bool = False) -> None:
        """Write the status line to the console."""
        truncated = self._truncate(message)
        line = f"\r[{self._mode}] {truncated}"
        if newline:
            line += "\n"
        self._console.file.write(line)
        self._console.file.flush()


# ---------------------------------------------------------------------------
# format_clause_label  (T046a — clause analysis status labels)
# ---------------------------------------------------------------------------


def _truncate_label(text: str, max_len: int = _MAX_LABEL_LEN) -> str:
    """Truncate *text* to *max_len* characters, appending ``…``."""
    if len(text) > max_len:
        return text[:max_len] + "…"
    return text


def format_clause_label(current: int, total: int, title: str, *, done: bool = False) -> str:
    """Format a clause analysis label for the status line.

    Parameters
    ----------
    current:
        1-based index of the current clause.
    total:
        Total number of clauses.
    title:
        Clause title (may be empty).
    done:
        If True, uses past tense (``Analyzed``) and no ``...`` suffix.

    Returns
    -------
    str
        Formatted label, e.g. ``"Analyzing clause 3 of 12 — Indemnification..."``
        or ``"Analyzed clause 12 of 12 — Indemnification"``.  Truncated at
        ``_MAX_LABEL_LEN`` characters.
    """
    verb = "Analyzed" if done else "Analyzing"
    label = f"{verb} clause {current} of {total}"
    if title:
        label += f" — {title}"
    if not done:
        label += "..."
    return _truncate_label(label)
