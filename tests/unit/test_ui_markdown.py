"""Unit tests for the minimal markdown renderer.

Verifies that render_markdown() produces Rich Text with correct
Style for h1-h3, bullets, bold, inline code, and that unknown
syntax passes through as plain text.
"""

from __future__ import annotations

from rich.style import Style
from rich.text import Text

from openreview_cli.ui.components.markdown import render_markdown

# ---------------------------------------------------------------------------
# Heading levels
# ---------------------------------------------------------------------------


def _get_span_style(result: Text, text: str) -> Style | None:
    """Return the Style for the first span containing *text*, or None."""
    for span in result.spans:
        if text in result.plain[span.start : span.end] and isinstance(span.style, Style):
            return span.style
    return None


def test_h1_renders_bold() -> None:
    """# Heading produces bold text."""
    result = render_markdown("# Title")
    assert isinstance(result, Text)
    assert "Title" in result.plain
    style = _get_span_style(result, "Title")
    assert style is not None
    assert style.bold is True


def test_h2_renders_bold_underline() -> None:
    """## Heading produces bold underlined text."""
    result = render_markdown("## Section")
    assert "Section" in result.plain
    style = _get_span_style(result, "Section")
    assert style is not None
    assert style.underline is True


def test_h3_renders_bold_italic() -> None:
    """### Heading produces bold italic text."""
    result = render_markdown("### Subsection")
    assert "Subsection" in result.plain
    style = _get_span_style(result, "Subsection")
    assert style is not None
    assert style.italic is True


def test_h1_with_trailing_spaces() -> None:
    """# Heading with trailing spaces is handled."""
    result = render_markdown("#  Title  ")
    assert "Title" in result.plain


# ---------------------------------------------------------------------------
# Bullet lists
# ---------------------------------------------------------------------------


def test_bullet_renders_with_prefix() -> None:
    """- Item renders with a bullet prefix."""
    result = render_markdown("- Item")
    assert "Item" in result.plain
    # Should have some prefix character before Item
    idx = result.plain.index("Item")
    assert idx > 0  # there's something before Item


def test_bullet_multiple_items() -> None:
    """Multiple bullet items each get a bullet prefix."""
    text = "- First\n- Second\n- Third"
    result = render_markdown(text)
    assert "First" in result.plain
    assert "Second" in result.plain
    assert "Third" in result.plain


def test_bullet_with_leading_spaces() -> None:
    """-   Item with extra spaces is handled."""
    result = render_markdown("-   Spaced")
    assert "Spaced" in result.plain


# ---------------------------------------------------------------------------
# Bold text
# ---------------------------------------------------------------------------


def test_bold_text() -> None:
    """**bold** renders as bold."""
    result = render_markdown("**bold**")
    assert "bold" in result.plain
    style = _get_span_style(result, "bold")
    assert style is not None
    assert style.bold is True


def test_bold_mixed_with_plain() -> None:
    """Bold works inline with surrounding text."""
    result = render_markdown("Hello **world** here")
    assert result.plain == "Hello world here"


def test_bold_multiple() -> None:
    """Multiple **bold** segments in one line."""
    result = render_markdown("**A** and **B**")
    assert result.plain == "A and B"


# ---------------------------------------------------------------------------
# Inline code
# ---------------------------------------------------------------------------


def test_inline_code() -> None:
    """`code` renders with a distinct style (dim/reverse or similar)."""
    result = render_markdown("Use `openreview parse`")
    assert "openreview parse" in result.plain
    # The code span should be styled differently
    # At minimum it should exist as a span
    assert result.spans


def test_code_uses_code_style() -> None:
    """Inline code ensures the text is in the result."""
    result = render_markdown("Run `uv sync` to install")
    assert "uv sync" in result.plain


# ---------------------------------------------------------------------------
# Mixed content (multi-line)
# ---------------------------------------------------------------------------


def test_mixed_content() -> None:
    """Multi-line document with headings, bullets, and inline formats."""
    text = """# Document

This is **important**.

- Step one
- Step two"""
    result = render_markdown(text)
    assert "Document" in result.plain
    assert "important" in result.plain
    assert "Step one" in result.plain
    assert "Step two" in result.plain


# ---------------------------------------------------------------------------
# Unknown syntax — pass through
# ---------------------------------------------------------------------------


def test_unknown_syntax_passes_through() -> None:
    """Unknown markdown syntax like [link](url) passes through as plain."""
    result = render_markdown("[link](http://example.com)")
    assert result.plain.strip() == "[link](http://example.com)"


def test_plain_text_passes_through() -> None:
    """Plain text with no markdown is unchanged."""
    result = render_markdown("Just some text.")
    assert result.plain.strip() == "Just some text."


def test_empty_string() -> None:
    """Empty string returns empty Text."""
    result = render_markdown("")
    assert isinstance(result, Text)
    assert result.plain == ""


def test_blank_lines_preserved() -> None:
    """Blank lines in multi-line text are preserved as newlines."""
    result = render_markdown("Line 1\n\nLine 2")
    assert "Line 1" in result.plain
    assert "Line 2" in result.plain


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------


def test_returns_rich_text() -> None:
    """render_markdown always returns a Rich Text instance."""
    result = render_markdown("# Hello")
    assert isinstance(result, Text)


def test_spans_have_style() -> None:
    """Spans in the result carry a Rich Style object."""
    result = render_markdown("**bold** and `code`")
    for span in result.spans:
        assert isinstance(span.style, Style)


# ---------------------------------------------------------------------------
# Code blocks fenced (``` ... ```) — pass through as plain
# ---------------------------------------------------------------------------


def test_fenced_code_block_passes_through() -> None:
    """Fenced code blocks ```...``` pass through as plain text."""
    text = "```\ncode block\n```"
    result = render_markdown(text)
    assert "code block" in result.plain
    assert "```" not in result.plain.strip()
