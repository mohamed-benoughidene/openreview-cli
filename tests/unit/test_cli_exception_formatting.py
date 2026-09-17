"""Exception text must render as a single clean line (P2T3).

The CLI catches failures inside commands and prints ``Error: <message>``.
Library exceptions (pydantic, httpx, OS errors) sometimes stringify to
multi-line blobs; ``_format_exception`` collapses them to one human-readable
line so scripts and terminals stay readable. Each call site keeps its own
exit code and any surrounding context (e.g. the target output path).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

import openreview_cli.app as app_mod
from openreview_cli.app import _format_exception

# ── _format_exception unit behaviour ──────────────────────────────────────


def test_format_exception_collapses_newlines() -> None:
    exc = ValueError("line one\n    line two\nline three")
    assert _format_exception(exc) == "line one line two line three"


def test_format_exception_prefers_message_attribute() -> None:
    class _PreferredMessageError(Exception):
        def __init__(self) -> None:
            super().__init__("fallback")
            self.message = "preferred message"

    assert _format_exception(_PreferredMessageError()) == "preferred message"


def test_format_exception_truncates() -> None:
    assert len(_format_exception(ValueError("x" * 5000))) == 500


def test_format_exception_falls_back_to_class_name() -> None:
    """An empty message must not collapse to an empty string."""
    assert _format_exception(ValueError()) == "ValueError"


# ── application at CLI catch sites (exit codes preserved) ──────────────────


def test_write_output_file_collapses_multiline_error_and_keeps_exit_1(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The --output write failure collapses to one line, keeps path + exit 1."""
    target = tmp_path / "out.json"

    def _boom(*_args: object, **_kwargs: object) -> int:
        raise OSError("disk full\n    while writing\nsecondary detail")

    monkeypatch.setattr("pathlib.Path.write_text", _boom)

    with pytest.raises(typer.Exit) as exc_info:
        app_mod._write_output_file(target, "{}")

    assert exc_info.value.exit_code == 1
    err = capsys.readouterr().err
    assert str(target) in err
    assert "disk full while writing secondary detail" in err
    # Exactly one line of error output (no embedded newlines).
    assert err.strip().count("\n") == 0


def test_precheck_review_collapses_exception_and_keeps_exit_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failing review pipeline prints one line and preserves exit code 2."""
    config_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    log_dir = tmp_path / "logs"
    for path in (config_dir, data_dir, log_dir):
        path.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(app_mod, "get_config_dir", lambda: config_dir)
    monkeypatch.setattr(app_mod, "get_data_dir", lambda: data_dir)
    monkeypatch.setattr(app_mod, "get_log_dir", lambda: log_dir)

    def _boom(**_kwargs: object) -> object:
        raise RuntimeError("pipeline failed\n    at stage two\nwith detail")

    monkeypatch.setattr("openreview_cli.review.run_review", _boom)

    result = CliRunner().invoke(app_mod.app, ["precheck", "review", "doc.pdf"])

    assert result.exit_code == 2, (result.exit_code, result.output)
    combined = (result.stdout or "") + (result.stderr or "")
    assert "Error: pipeline failed at stage two with detail" in combined
    assert "Traceback" not in combined
