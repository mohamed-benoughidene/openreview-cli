"""Semantic color roles for the openreview-cli UI.

Each ``ColorRole`` carries the Rich-style style string, a no-color
fallback, a Unicode icon, and an ASCII replacement — all derived from
the spec's design tokens.
"""

from openreview_cli.types import ColorRole

PRIMARY = ColorRole(
    color="bold cyan",
    no_color="bold",
    icon="→",
    icon_ascii="->",
)

SUCCESS = ColorRole(
    color="bold green",
    no_color="bold",
    icon="✓",
    icon_ascii="[OK]",
)

WARNING = ColorRole(
    color="bold yellow",
    no_color="bold underline",
    icon="⚠",
    icon_ascii="[!]",
)

ERROR = ColorRole(
    color="bold red",
    no_color="bold underline",
    icon="✗",
    icon_ascii="[ERR]",
)

MUTED = ColorRole(
    color="dim",
    no_color="dim",
    icon="•",
    icon_ascii="*",
)

ACCENT = ColorRole(
    color="bold magenta",
    no_color="bold",
    icon="★",
    icon_ascii="[*]",
)

CODE = ColorRole(
    color="bold bright_black on grey15",
    no_color="",
    icon="$",
    icon_ascii="$",
)

# Convenience grouping for iteration / validation
_ALL_ROLES = (PRIMARY, SUCCESS, WARNING, ERROR, MUTED, ACCENT, CODE)
