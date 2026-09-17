"""P2T2 — every ``--format`` value must be validated (reject unknown with exit 2).

An unknown format must never silently fall through to a default output
branch.  ``_validate_enum`` prints ``Error: --format must be ...`` and exits
with ``EXIT_USAGE`` (2).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from openreview_cli.app import _emit_reviews, app

runner = CliRunner()


def _invoke(args: list[str]) -> Any:
    return runner.invoke(app, args)


def _combined(result: Any) -> str:
    """stdout + stderr (Click >= 8.2 keeps the two streams separate)."""
    return (getattr(result, "output", "") or "") + (getattr(result, "stderr", "") or "")


# ── _emit_reviews: validation is the FIRST statement of the body ──────────


def test_emit_reviews_rejects_unknown_format_first() -> None:
    """Validation must run before the "no documents" guard (which exits 1)."""
    with pytest.raises(typer.Exit) as excinfo:
        _emit_reviews([], "yaml", None, None, [], None)
    assert excinfo.value.exit_code == 2


@pytest.mark.parametrize("fmt", ["text", "json", "terminal", "table", "memo"])
def test_emit_reviews_accepts_documented_formats(fmt: str) -> None:
    """Documented formats clear validation and reach the empty-report guard (1)."""
    with pytest.raises(typer.Exit) as excinfo:
        _emit_reviews([], fmt, None, None, [], None)
    assert excinfo.value.exit_code == 1


# ── parse ─────────────────────────────────────────────────────────────────


def test_parse_rejects_unknown_format() -> None:
    result = _invoke(["parse", "nonexistent.pdf", "--format", "xml"])
    assert result.exit_code == 2, (result.exit_code, _combined(result))
    assert "format" in _combined(result).lower()


@pytest.mark.parametrize("fmt", ["text", "json"])
def test_parse_accepts_documented_formats(fmt: str) -> None:
    """Documented values must clear validation (missing file fails later, not 2)."""
    result = _invoke(["parse", "nonexistent.pdf", "--format", fmt])
    assert result.exit_code != 2, (result.exit_code, _combined(result))


# ── chunk ─────────────────────────────────────────────────────────────────


def test_chunk_rejects_unknown_format() -> None:
    result = _invoke(["chunk", "nonexistent.pdf", "--format", "xml"])
    assert result.exit_code == 2, (result.exit_code, _combined(result))
    assert "format" in _combined(result).lower()


@pytest.mark.parametrize("fmt", ["text", "json"])
def test_chunk_accepts_documented_formats(fmt: str) -> None:
    result = _invoke(["chunk", "nonexistent.pdf", "--format", fmt])
    assert result.exit_code != 2, (result.exit_code, _combined(result))


# ── pii list ──────────────────────────────────────────────────────────────


def test_pii_list_rejects_unknown_format(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Redirect the data dir so the (should-be-unreached) DB lookup never
    # touches the real user data directory during the red phase.
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    result = _invoke(["pii", "list", "--format", "xml"])
    assert result.exit_code == 2, (result.exit_code, _combined(result))
    assert "format" in _combined(result).lower()


def test_pii_list_accepts_table_json_and_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The table|json contract must not reject its own documented values/default."""
    from openreview_cli.config.paths import get_data_dir
    from openreview_cli.storage import init_database

    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    init_database(get_data_dir() / "openreview.db")

    for args in (
        ["pii", "list"],
        ["pii", "list", "--format", "table"],
        ["pii", "list", "--format", "json"],
    ):
        result = _invoke(args)
        assert result.exit_code == 0, (args, result.exit_code, _combined(result))
