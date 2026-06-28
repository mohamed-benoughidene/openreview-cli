"""Header UI components: separator, breadcrumb, and step indicator.

Provides three functions for rendering horizontal rules, breadcrumb
navigation trails, and step indicators (spec §2.11).  All functions
respect ``NO_COLOR`` via the ``SGRenderer`` singleton.
"""

from __future__ import annotations

import shutil

from rich.text import Text

from openreview_cli.ui.colors import ACCENT, MUTED, PRIMARY
from openreview_cli.ui.console import get_icon, renderer

# ---------------------------------------------------------------------------
# Separator
# ---------------------------------------------------------------------------


def separator(char: str = "─") -> None:
    """Print a horizontal rule filling the terminal width with *char*."""
    term_width = shutil.get_terminal_size(fallback=(80, 24)).columns
    renderer.console.print(char * term_width)


# ---------------------------------------------------------------------------
# Breadcrumb
# ---------------------------------------------------------------------------


def breadcrumb(steps: list[str], current: int) -> None:
    """Print a breadcrumb trail with `` > `` separators.

    Parameters
    ----------
    steps:
        Ordered list of step labels.
    current:
        Index of the current (active) step.  Clamped to ``[0, len(steps))``.
    """
    if not steps:
        return

    # Clamp current index
    idx = max(0, min(current, len(steps) - 1))

    parts: list[Text] = []
    for i, step in enumerate(steps):
        if i == idx:
            # Active step — use primary style
            style = PRIMARY.color if renderer.supports_color else PRIMARY.no_color
        else:
            # Inactive step — muted
            style = MUTED.color if renderer.supports_color else MUTED.no_color

        parts.append(Text(step, style=style))

        if i < len(steps) - 1:
            sep = MUTED.color if renderer.supports_color else MUTED.no_color
            parts.append(Text(" > ", style=sep))

    line = Text.assemble(*parts)
    renderer.console.print(line)


# ---------------------------------------------------------------------------
# Step indicator  (spec §2.11)
# ---------------------------------------------------------------------------


def step_indicator(current: int, total: int, title: str) -> None:
    """Print a step indicator in the spec §2.11 format.

    The format is::

        ✓ ▶ ○ ○  Step 2 of 4: Title

    Where ``✓`` marks completed steps, ``▶`` marks the current step,
    and ``○`` marks pending steps.

    Parameters
    ----------
    current:
        1-based index of the current step.
    total:
        Total number of steps.
    title:
        Human-readable title for the current step.
    """
    use_ascii = not renderer.supports_unicode

    ok_icon = get_icon("check", ascii_fallback=use_ascii)
    current_icon = ">" if use_ascii else "▶"
    pending_icon = get_icon("pending", ascii_fallback=use_ascii)

    dots: list[str] = []
    for i in range(1, total + 1):
        if i < current:
            dots.append(ok_icon)
        elif i == current:
            dots.append(current_icon)
        else:
            dots.append(pending_icon)

    dots_str = " ".join(dots)

    # Style — primary for the step number, accent for the title
    step_style = PRIMARY.color if renderer.supports_color else PRIMARY.no_color
    title_style = ACCENT.color if renderer.supports_color else ACCENT.no_color

    line = Text.assemble(
        Text(f"{dots_str}  "),
        Text(f"Step {current} of {total}", style=step_style),
        Text(": ", style=step_style),
        Text(title, style=title_style),
    )
    renderer.console.print(line)
