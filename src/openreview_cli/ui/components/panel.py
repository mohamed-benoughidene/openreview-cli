"""Semantic panel components: info, warning, error, success.

Each function renders a ``rich.panel.Panel`` via the module-level
``SGRenderer`` singleton and handles colour/Unicode detection
automatically.
"""

from __future__ import annotations

from rich.panel import Panel
from rich.text import Text

from openreview_cli.ui.console import get_icon, renderer


def _panel_title(icon: str, title: str = "") -> Text:
    """Build a Panel title from *icon* and optional *title* as a plain
    ``Text`` so that ASCII fallbacks like ``[i]`` are not parsed as Rich
    markup."""
    if title:
        return Text(f" {icon} {title} ")
    return Text(f" {icon} ")


def info_panel(message: str, title: str = "") -> None:
    """Print an info panel (cyan border, ℹ prefix)."""  # noqa: RUF002
    icon = get_icon("info", ascii_fallback=not renderer.supports_unicode)
    border = "" if not renderer.supports_color else "cyan"
    panel = Panel(
        message,
        title=_panel_title(icon, title),
        border_style=border,
    )
    renderer.console.print(panel)


def warning_panel(message: str, title: str = "") -> None:
    """Print a warning panel (yellow border, ⚠ prefix)."""
    icon = get_icon("warning", ascii_fallback=not renderer.supports_unicode)
    border = "" if not renderer.supports_color else "yellow"
    panel = Panel(
        message,
        title=_panel_title(icon, title),
        border_style=border,
    )
    renderer.console.print(panel)


def error_panel(
    what: str,
    why: str,
    fix: str,
    exit_code: int = 1,
) -> None:
    """Print an error panel (red border, ✗ prefix) and exit.

    Displays a three-part structure: *What failed*, *Why*, *How to fix*,
    then raises ``SystemExit(exit_code)``.
    """
    icon = get_icon("error", ascii_fallback=not renderer.supports_unicode)
    border = "" if not renderer.supports_color else "red"
    if "help" not in fix.lower():
        fix = fix + "\n\nRun `openreview --help` for usage."
    body = (
        f"[bold]What failed:[/bold] {what}\n\n"
        f"[bold]Why:[/bold] {why}\n\n"
        f"[bold]How to fix:[/bold] {fix}"
    )
    panel = Panel(
        body,
        title=_panel_title(icon),
        border_style=border,
    )
    renderer.console.print(panel)
    raise SystemExit(exit_code)


def success_panel(message: str, title: str = "") -> None:
    """Print a success panel (green border, ✓ prefix)."""
    icon = get_icon("check", ascii_fallback=not renderer.supports_unicode)
    border = "" if not renderer.supports_color else "green"
    panel = Panel(
        message,
        title=_panel_title(icon, title),
        border_style=border,
    )
    renderer.console.print(panel)
