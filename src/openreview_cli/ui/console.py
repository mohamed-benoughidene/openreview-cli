"""Console abstraction and icon mapping for the openreview-cli UI.

Provides ``SGRenderer`` — a thin wrapper around ``rich.console.Console``
with automatic capability detection (NO_COLOR, color flags, Unicode
support) — plus Unicode/ASCII icon dictionaries and a ``get_icon()``
helper.
"""

from __future__ import annotations

import locale
import os
import sys
from typing import Literal

from rich.console import Console

# ---------------------------------------------------------------------------
# Icon mapping
# ---------------------------------------------------------------------------

ICONS: dict[str, str] = {
    "check": "✓",
    "error": "✗",
    "warning": "⚠",
    "info": "ℹ",  # noqa: RUF001
    "pending": "○",
    "running": "◷",
    "arrow": "▶",
    "bullet": "●",
    "separator": "━",
    "step_marker": "→",
    "file_path": "📄",
    "lock": "🔒",
}

ICONS_ASCII: dict[str, str] = {
    "check": "[OK]",
    "error": "[ERR]",
    "warning": "[!]",
    "info": "[i]",
    "pending": "[ ]",
    "running": "[...]",
    "arrow": ">",
    "bullet": "*",
    "separator": "-",
    "step_marker": "->",
    "file_path": "[file]",
    "lock": "[**]",
}


def get_icon(name: str, ascii_fallback: bool = False) -> str:
    """Return the icon for *name*, preferring Unicode unless fallback
    conditions apply.

    Auto-fallback (when ``ascii_fallback`` is ``False``) is triggered by:
    * the ``NO_COLOR`` environment variable being set (any non-empty value),
    * ``FORCE_COLOR`` being explicitly ``"0"``,
    * ``sys.platform == "win32"``, or
    * a ``UnicodeEncodeError`` when encoding with the terminal encoding.
    """
    if ascii_fallback:
        return ICONS_ASCII[name]

    # Auto-detect fallback conditions
    no_color = os.environ.get("NO_COLOR")
    if no_color:
        return ICONS_ASCII[name]

    force_color = os.environ.get("FORCE_COLOR")
    if force_color == "0":
        return ICONS_ASCII[name]

    if sys.platform == "win32":
        return ICONS_ASCII[name]

    # Try Unicode — fall back if the terminal can't encode it
    icon = ICONS[name]
    try:
        icon.encode(sys.stdout.encoding or "utf-8")
    except (UnicodeEncodeError, UnicodeError):
        return ICONS_ASCII[name]
    else:
        return icon


# ---------------------------------------------------------------------------
# SGRenderer
# ---------------------------------------------------------------------------


class SGRenderer:
    """Thin wrapper around ``rich.console.Console`` with automatic
    capability detection.

    Reads ``NO_COLOR``, ``FORCE_COLOR``, locale encoding, and optional
    constructor flags to decide whether colour and Unicode should be
    enabled.

    Usage::

        console = SGRenderer().console
        console.print("Hello", style="bold green")
    """

    def __init__(
        self,
        no_color: bool = False,
        no_unicode: bool = False,
        non_interactive: bool = False,
    ) -> None:
        # Detect NO_COLOR from environment (any non-empty value)
        env_no_color = os.environ.get("NO_COLOR")
        env_force_color = os.environ.get("FORCE_COLOR")

        # Determine color system
        if no_color or (env_no_color is not None and env_no_color != ""):
            self._color_system: Literal["auto", None] = None
        elif env_force_color == "0":
            self._color_system = None
        else:
            self._color_system = "auto"

        # Build Console
        self._console = Console(color_system=self._color_system)

        # Unicode support
        if no_unicode:
            self._supports_unicode = False
        else:
            encoding = locale.getpreferredencoding()
            self._supports_unicode = encoding.lower() in (
                "utf-8",
                "utf8",
            )

        # Non-interactive override flag
        self._non_interactive = non_interactive

        # T076: Global CLI flag state
        self.verbose: bool = False
        self.quiet: bool = False
        self.no_spinner: bool = False
        self.output_format: str = "table"

    # -- public properties ------------------------------------------------

    @property
    def console(self) -> Console:
        return self._console

    @property
    def is_interactive(self) -> bool:
        if self._non_interactive:
            return False
        return self._console.is_interactive and sys.stdin.isatty() and sys.stdout.isatty()

    @property
    def supports_unicode(self) -> bool:
        return self._supports_unicode

    @property
    def supports_color(self) -> bool:
        return self._color_system is not None

    # -- non-interactive override -----------------------------------------

    def force_non_interactive(self) -> None:
        """Override the renderer to non-interactive mode.

        Called by commands when ``--non-interactive`` or ``--yes`` is
        passed, even if stdin/stdout are TTYs.
        """
        self._non_interactive = True

    def set_no_color(self) -> None:
        """Disable color output (called from ``--no-color`` / ``NO_COLOR``)."""
        self._color_system = None
        self._console = Console(color_system=None)

    def set_no_unicode(self) -> None:
        """Disable Unicode icons (called from ``--no-unicode``)."""
        self._supports_unicode = False


# Module-level singleton — shared across the application.
renderer = SGRenderer()
