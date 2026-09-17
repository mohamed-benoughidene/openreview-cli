"""Unit tests for the TUI three-colour status tag mapping (P1/T3)."""

from __future__ import annotations

import pytest
from textual.color import Color, ColorParseError


def test_status_color_tag_maps_amber_to_valid_color() -> None:
    from openreview_cli.tui.screens.result import status_color_tag

    assert status_color_tag("amber") == "orange"
    # Every mapped value must be a colour Textual can actually parse.
    for color in ("green", "amber", "red"):
        Color.parse(status_color_tag(color))


def test_raw_amber_is_not_a_valid_color_name() -> None:
    """Guard: this fails if someone regresses to emitting the raw value."""
    with pytest.raises(ColorParseError):
        Color.parse("amber")
