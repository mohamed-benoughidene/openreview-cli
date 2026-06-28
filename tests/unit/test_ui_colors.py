"""Unit tests for semantic color roles."""

from openreview_cli.ui.colors import (
    ACCENT,
    CODE,
    ERROR,
    MUTED,
    PRIMARY,
    SUCCESS,
    WARNING,
)

NO_COLOR_REFERENCE = frozenset(
    {
        "red",
        "green",
        "yellow",
        "cyan",
        "magenta",
        "bright_black",
    }
)


def test_primary_has_all_fields() -> None:
    assert PRIMARY.color == "bold cyan"
    assert PRIMARY.no_color == "bold"
    assert PRIMARY.icon == "→"
    assert PRIMARY.icon_ascii == "->"


def test_success_has_all_fields() -> None:
    assert SUCCESS.color == "bold green"
    assert SUCCESS.no_color == "bold"
    assert SUCCESS.icon == "✓"
    assert SUCCESS.icon_ascii == "[OK]"


def test_warning_has_all_fields() -> None:
    assert WARNING.color == "bold yellow"
    assert WARNING.no_color == "bold underline"
    assert WARNING.icon == "⚠"
    assert WARNING.icon_ascii == "[!]"


def test_error_has_all_fields() -> None:
    assert ERROR.color == "bold red"
    assert ERROR.no_color == "bold underline"
    assert ERROR.icon == "✗"
    assert ERROR.icon_ascii == "[ERR]"


def test_muted_has_all_fields() -> None:
    assert MUTED.color == "dim"
    assert MUTED.no_color == "dim"
    assert MUTED.icon == "•"
    assert MUTED.icon_ascii == "*"


def test_accent_has_all_fields() -> None:
    assert ACCENT.color == "bold magenta"
    assert ACCENT.no_color == "bold"
    assert ACCENT.icon == "★"
    assert ACCENT.icon_ascii == "[*]"


def test_code_has_all_fields() -> None:
    assert CODE.color == "bold bright_black on grey15"
    assert CODE.no_color == ""
    assert CODE.icon == "$"
    assert CODE.icon_ascii == "$"


def test_all_no_color_fallbacks_contain_no_color_references() -> None:
    """Every no_color fallback string must not name any ANSI color."""
    roles = [PRIMARY, SUCCESS, WARNING, ERROR, MUTED, ACCENT, CODE]
    for role in roles:
        assert isinstance(role.no_color, str)
        words = role.no_color.lower().split()
        # CODE.no_color is "" — trivially passes
        for word in words:
            assert word not in NO_COLOR_REFERENCE, (
                f"{role} no_color={role.no_color!r} contains color reference {word!r}"
            )


def test_all_exported_as_colorrole() -> None:
    """Every constant should be a ColorRole (imported from types)."""
    from openreview_cli.types import ColorRole

    roles = [PRIMARY, SUCCESS, WARNING, ERROR, MUTED, ACCENT, CODE]
    for role in roles:
        assert isinstance(role, ColorRole)
