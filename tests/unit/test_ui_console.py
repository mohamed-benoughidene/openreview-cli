"""Unit tests for the SGRenderer console wrapper and icon mapping."""

import sys

import pytest

from openreview_cli.ui.console import (
    SGRenderer,
    get_icon,
    renderer,
)

# ---------------------------------------------------------------------------
# SGRenderer — capabilities & singleton
# ---------------------------------------------------------------------------


def test_singleton_same_instance_across_imports() -> None:
    """Module-level *renderer* is shared — re-import yields the same object."""
    from openreview_cli.ui.console import renderer as r2

    assert renderer is r2


def test_no_color_env_disables_color(monkeypatch: pytest.MonkeyPatch) -> None:
    """When NO_COLOR is set, color_system should be None."""
    monkeypatch.setenv("NO_COLOR", "1")
    r = SGRenderer()
    assert not r.supports_color


def test_no_color_env_with_empty_value_enables_color(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty NO_COLOR is not considered 'set' per the spec convention."""
    monkeypatch.setenv("NO_COLOR", "")
    r = SGRenderer()
    assert r.supports_color


def test_no_color_flag_disables_color() -> None:
    """Passing no_color=True forces color off."""
    r = SGRenderer(no_color=True)
    assert not r.supports_color


def test_is_interactive_accessible() -> None:
    """is_interactive should map to the underlying Console property."""
    r = SGRenderer()
    # In test context this is typically False
    assert isinstance(r.is_interactive, bool)


def test_console_width_accessible() -> None:
    """Console width should be a positive integer."""
    r = SGRenderer()
    assert isinstance(r.console.width, int)
    assert r.console.width > 0


def test_supports_unicode_default() -> None:
    """Default SGRenderer should support unicode on most platforms."""
    r = SGRenderer()
    assert isinstance(r.supports_unicode, bool)


def test_supports_unicode_disabled() -> None:
    """Passing no_unicode=True should disable unicode support."""
    r = SGRenderer(no_unicode=True)
    assert not r.supports_unicode


def test_force_color_and_no_color_no_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Setting both NO_COLOR and FORCE_COLOR must not raise."""
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setenv("FORCE_COLOR", "1")
    # Must not raise
    r = SGRenderer()
    assert not r.supports_color


def test_force_color_zero_disables_color(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FORCE_COLOR=0 should disable color (same as NO_COLOR)."""
    monkeypatch.setenv("FORCE_COLOR", "0")
    r = SGRenderer()
    assert not r.supports_color


# ---------------------------------------------------------------------------
# Terminal detection properties
# ---------------------------------------------------------------------------


def test_is_terminal_accessible() -> None:
    """TTY detection — is_terminal delegates to the underlying Console."""
    r = SGRenderer()
    assert isinstance(r.console.is_terminal, bool)


# ---------------------------------------------------------------------------
# Icon mapping — ICONS / ICONS_ASCII
# ---------------------------------------------------------------------------

EXPECTED_ICONS = {
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

EXPECTED_ICONS_ASCII = {
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


def test_icons_dict_has_all_entries() -> None:
    from openreview_cli.ui.console import ICONS

    assert ICONS == EXPECTED_ICONS


def test_icons_ascii_dict_has_all_entries() -> None:
    from openreview_cli.ui.console import ICONS_ASCII

    assert ICONS_ASCII == EXPECTED_ICONS_ASCII


def test_get_icon_unicode() -> None:
    """get_icon returns unicode icon by default."""
    assert get_icon("check") == "✓"


def test_get_icon_ascii_fallback() -> None:
    """get_icon(..., ascii_fallback=True) returns ASCII variant."""
    assert get_icon("check", ascii_fallback=True) == "[OK]"


def test_get_icon_unknown_key_raises_key_error() -> None:
    """Requesting a non-existent icon should raise KeyError."""
    with pytest.raises(KeyError):
        get_icon("nonexistent")


def test_get_icon_unknown_key_ascii_raises_key_error() -> None:
    """Requesting a non-existent icon in ASCII mode should also raise."""
    with pytest.raises(KeyError):
        get_icon("nonexistent", ascii_fallback=True)


def test_get_icon_auto_fallback_no_color(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When NO_COLOR is set, get_icon should fall back to ASCII."""
    monkeypatch.setenv("NO_COLOR", "1")
    assert get_icon("check") == "[OK]"


def test_get_icon_auto_fallback_force_color_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When FORCE_COLOR=0, get_icon should fall back to ASCII."""
    monkeypatch.setenv("FORCE_COLOR", "0")
    assert get_icon("check") == "[OK]"


def test_get_icon_no_fallback_force_color_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When FORCE_COLOR=1, get_icon should use Unicode."""
    monkeypatch.setenv("FORCE_COLOR", "1")
    monkeypatch.delenv("NO_COLOR", raising=False)
    assert get_icon("check") == "✓"


def test_get_icon_win32_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """On win32 platform, get_icon should fall back to ASCII."""

    # Save original platform for restore
    import platform

    monkeypatch.setattr(platform, "system", lambda: "Windows")
    # We can't easily mock sys.platform for the module's import-time
    # check; instead test the win32 code path via platform check.
    # The implementation checks sys.platform, which we can patch:
    monkeypatch.setattr(sys, "platform", "win32")
    assert get_icon("pending") == "[ ]"


def test_get_icon_all_meanings_have_ascii_entries() -> None:
    """Every Unicode icon meaning should have a corresponding ASCII entry."""
    from openreview_cli.ui.console import ICONS, ICONS_ASCII

    assert set(ICONS.keys()) == set(ICONS_ASCII.keys())
    assert len(ICONS) == 12


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_no_color_env_also_none_color_system(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When NO_COLOR var is '0', it's still set, so color is off."""
    monkeypatch.setenv("NO_COLOR", "0")
    r = SGRenderer()
    assert not r.supports_color


# ---------------------------------------------------------------------------
# T049 — Non-interactive detection
# ---------------------------------------------------------------------------


def test_non_interactive_when_stdin_not_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    """is_interactive is False when sys.stdin is not a TTY."""
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    r = SGRenderer()
    assert not r.is_interactive


def test_non_interactive_when_stdout_not_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    """is_interactive is False when sys.stdout is not a TTY."""
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False)
    r = SGRenderer()
    assert not r.is_interactive


def test_non_interactive_when_both_not_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    """is_interactive is False when neither stdin nor stdout is a TTY."""
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False)
    r = SGRenderer()
    assert not r.is_interactive


def test_interactive_when_both_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    """is_interactive is True when both stdin and stdout are TTYs."""
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    r = SGRenderer()
    assert r.is_interactive


def test_non_interactive_flag_disables_interactive() -> None:
    """Passing non_interactive=True forces is_interactive to False even in TTY."""
    r = SGRenderer(non_interactive=True)
    assert not r.is_interactive


def test_force_non_interactive_method_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    """force_non_interactive() on the singleton disables interactivity."""
    from openreview_cli.ui.console import renderer as _r

    # Don't assert initial interactive state — the singleton's Console
    # was constructed at import time when isatty may have been False.
    _r.force_non_interactive()
    assert not _r.is_interactive
    # Reset for other tests
    _r._non_interactive = False


def test_force_non_interactive_fresh_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    """A fresh SGRenderer can be made non-interactive after construction."""
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    r = SGRenderer()
    assert r.is_interactive
    r.force_non_interactive()
    assert not r.is_interactive


# ---------------------------------------------------------------------------
# T069 — NO_COLOR + no-unicode combined
# ---------------------------------------------------------------------------


def test_no_color_and_no_unicode_detected_together(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SGRenderer with NO_COLOR env + no-unicode flag disables both."""
    monkeypatch.setenv("NO_COLOR", "1")
    r = SGRenderer(no_unicode=True)
    assert not r.supports_color
    assert not r.supports_unicode


def test_get_icon_no_color_and_no_unicode_ascii(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """get_icon with NO_COLOR env + explicit ascii_fallback returns ASCII."""
    monkeypatch.setenv("NO_COLOR", "1")
    assert get_icon("check") == "[OK]"
    assert get_icon("error") == "[ERR]"
    assert get_icon("warning") == "[!]"
    assert get_icon("info") == "[i]"


def test_get_icon_no_color_env_with_explicit_unicode_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """NO_COLOR env causes ASCII fallback even when ascii_fallback is not passed."""
    monkeypatch.setenv("NO_COLOR", "1")
    for name in ("check", "error", "warning", "info", "pending", "running"):
        assert get_icon(name) == EXPECTED_ICONS_ASCII[name]


def test_no_color_panels_use_ascii_borders(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When NO_COLOR + no-unicode, panels render with ASCII icons and no border colour.

    The border_style is '' (empty) so Rich draws ═══ plain lines.  Verify
    panels produce output without ANSI colour escapes when both NO_COLOR
    and no_unicode are active.
    """
    import importlib

    import openreview_cli.ui.components.panel as panel_mod
    import openreview_cli.ui.console as console_mod

    original = console_mod.renderer
    console_mod.renderer = console_mod.SGRenderer(no_color=True, no_unicode=True)
    importlib.reload(panel_mod)

    try:
        # info — should show [i] and no ANSI colour codes
        panel_mod.info_panel("nocolor info")
        captured = capsys.readouterr()
        assert "[i]" in captured.out
        assert "\x1b[" not in captured.out, "Expected no ANSI colour codes"

        # warning — should show [!]
        panel_mod.warning_panel("nocolor warning")
        captured = capsys.readouterr()
        assert "[!]" in captured.out
        assert "\x1b[" not in captured.out

        # success — should show [OK]
        panel_mod.success_panel("nocolor success")
        captured = capsys.readouterr()
        assert "[OK]" in captured.out
        assert "\x1b[" not in captured.out
    finally:
        console_mod.renderer = original
        importlib.reload(panel_mod)


def test_no_color_console_does_not_emit_ansi_in_panel_titles(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Panel titles have no ANSI colour codes when NO_COLOR is active."""
    import importlib

    import openreview_cli.ui.components.panel as panel_mod
    import openreview_cli.ui.console as console_mod

    original = console_mod.renderer
    console_mod.renderer = console_mod.SGRenderer(no_color=True)
    importlib.reload(panel_mod)

    try:
        panel_mod.info_panel("test", title="Panel Title")
        captured = capsys.readouterr()
        assert "Panel Title" in captured.out
        assert "\x1b[" not in captured.out
    finally:
        console_mod.renderer = original
        importlib.reload(panel_mod)
