"""Minimal markdown renderer — stdlib + Rich only, no external parser.

``render_markdown()`` takes a markdown string and returns ``Rich.Text``
with appropriate ``Style`` for headings, bold, inline code, and bullet
lists.  Unknown syntax passes through as plain text.
"""

from __future__ import annotations

import re

from rich.style import Style
from rich.text import Text

from openreview_cli.ui.console import get_icon, renderer

# Regex for inline **bold** and `code`
_BOLD_PATTERN = re.compile(r"\*\*(.+?)\*\*")
_CODE_PATTERN = re.compile(r"`(.+?)`")

# Heading prefix patterns
_H1_PREFIX = "# "
_H2_PREFIX = "## "
_H3_PREFIX = "### "

# Bullet prefix pattern (any number of spaces then "- ")
_BULLET_PATTERN = re.compile(r"^(\s*)- ")


def _style_bold(m: re.Match[str]) -> tuple[str, Style]:
    """Return the bold text and its Style."""
    text = m.group(1)
    return text, Style(bold=True)


def _style_code(m: re.Match[str]) -> tuple[str, Style]:
    """Return the inline code text and its Style (dim + reverse)."""
    text = m.group(1)
    return text, Style(dim=True, reverse=True)


def _apply_inline(line: str) -> Text:
    """Apply bold and inline code styles to *line*.

    Works by splitting the line into plain segments and styled spans
    via regex substitution.
    """
    combined = re.split(r"(\*\*.+?\*\*|`.+?`)", line)
    parts: list[Text] = []

    for chunk in combined:
        bold_match = _BOLD_PATTERN.fullmatch(chunk)
        code_match = _CODE_PATTERN.fullmatch(chunk)

        if bold_match:
            text, style = _style_bold(bold_match)
            parts.append(Text(text, style=style))
        elif code_match:
            text, style = _style_code(code_match)
            parts.append(Text(text, style=style))
        else:
            parts.append(Text(chunk))

    return Text.assemble(*parts)


def _process_line(line: str) -> Text:
    """Process a single line of markdown and return a Rich Text."""
    stripped = line.lstrip()

    # Heading level 3 — bold + italic
    if stripped.startswith(_H3_PREFIX):
        content = stripped[len(_H3_PREFIX) :].strip()
        return Text(content, style=Style(bold=True, italic=True))

    # Heading level 2 — bold + underline
    if stripped.startswith(_H2_PREFIX):
        content = stripped[len(_H2_PREFIX) :].strip()
        return Text(content, style=Style(bold=True, underline=True))

    # Heading level 1 — bold
    if stripped.startswith(_H1_PREFIX):
        content = stripped[len(_H1_PREFIX) :].strip()
        return Text(content, style=Style(bold=True))

    # Bullet list
    bullet_match = _BULLET_PATTERN.match(stripped)
    if bullet_match:
        bullet_char = get_icon("pending", ascii_fallback=not renderer.supports_unicode)
        content = stripped[bullet_match.end() :]
        styled = _apply_inline(content)
        return Text.assemble(
            Text(f"{bullet_char} "),
            styled,
        )

    # Fenced code block markers — skip (just return empty)
    if stripped.startswith("```"):
        return Text("")

    # Plain text (including unknown syntax) — apply inline styles
    return _apply_inline(line)


def render_markdown(text: str) -> Text:
    """Render a minimal markdown *text* to a Rich ``Text`` object.

    Supports: ``# h1``, ``## h2``, ``### h3``, ``- bullet``,
    ``**bold**``, and inline ``code``.  Unknown markup passes
    through as literal text.

    Returns
    -------
    Rich ``Text`` with appropriate styles applied.
    """
    if not text:
        return Text("")

    lines = text.split("\n")
    result_lines: list[Text] = [_process_line(line) for line in lines]

    if not result_lines:
        return Text("")

    # Insert newline Texts between lines so multi-line output has breaks
    assembled: list[Text] = []
    for i, line_text in enumerate(result_lines):
        if i > 0:
            assembled.append(Text("\n"))
        assembled.append(line_text)

    return Text.assemble(*assembled)
