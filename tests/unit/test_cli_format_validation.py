"""P2T2 — every ``--format`` value must be validated (reject unknown with exit 2).

An unknown format must never silently fall through to a default output
branch.  ``_validate_enum`` prints ``Error: --format must be ...`` and exits
with ``EXIT_USAGE`` (2).
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from openreview_cli.app import _emit_reviews, app
from openreview_cli.pii.cache import PiiCache
from openreview_cli.pii.models import PiiEntity, PiiResult
from openreview_cli.pii.persist import write_audit_trail_row

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


# ── pii list --all: opt-in listing of audit-only (clean) documents ────────


def _isolate_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from openreview_cli.config.paths import get_data_dir
    from openreview_cli.storage import init_database

    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    db_path = get_data_dir() / "openreview.db"
    init_database(db_path)
    return db_path


def _clean_result() -> PiiResult:
    return PiiResult(
        stripped_text="Hello world",
        mapping={},
        entities=[],
        page_count=1,
        duration_seconds=0.0,
        warnings=[],
        failed_pages=None,
    )


def _pii_result() -> PiiResult:
    return replace(
        _clean_result(),
        stripped_text="[PERSON_1] signed",
        mapping={"PERSON_1": "Alice"},
        entities=[PiiEntity("PERSON", "Alice", 0, 5, 0.9, "[PERSON_1]", "nlp")],
    )


def test_pii_list_default_excludes_an_audit_only_document(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = _isolate_db(tmp_path, monkeypatch)
    write_audit_trail_row(
        db_path,
        document_hash="d" * 64,
        config_hash="cfg",
        pii_result=_clean_result(),
        status="success",
    )
    result = _invoke(["pii", "list", "--format", "json"])
    assert result.exit_code == 0, (result.exit_code, _combined(result))
    assert json.loads(result.output) == []


def test_pii_list_all_includes_an_audit_only_document_with_zero_entities(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = _isolate_db(tmp_path, monkeypatch)
    write_audit_trail_row(
        db_path,
        document_hash="d" * 64,
        config_hash="cfg",
        pii_result=_clean_result(),
        status="success",
    )
    result = _invoke(["pii", "list", "--all", "--format", "json"])
    assert result.exit_code == 0, (result.exit_code, _combined(result))
    rows = json.loads(result.output)
    assert len(rows) == 1
    assert rows[0]["document_hash"] == "d" * 64
    assert rows[0]["entity_count"] == 0


def test_pii_list_all_matches_the_default_for_a_pii_bearing_document(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = _isolate_db(tmp_path, monkeypatch)
    PiiCache(db_path).put("c" * 64, "cfg", "/tmp/review.txt", "/tmp/mapping.enc")
    write_audit_trail_row(
        db_path,
        document_hash="c" * 64,
        config_hash="cfg",
        pii_result=_pii_result(),
        status="success",
    )
    default = _invoke(["pii", "list", "--format", "json"])
    all_rows = _invoke(["pii", "list", "--all", "--format", "json"])
    assert default.exit_code == 0, (default.exit_code, _combined(default))
    assert all_rows.exit_code == 0, (all_rows.exit_code, _combined(all_rows))
    default_parsed = json.loads(default.output)
    all_parsed = json.loads(all_rows.output)
    assert len(default_parsed) == 1
    assert default_parsed == all_parsed


def test_pii_list_all_on_an_empty_db_returns_empty_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _isolate_db(tmp_path, monkeypatch)
    result = _invoke(["pii", "list", "--all", "--format", "json"])
    assert result.exit_code == 0, (result.exit_code, _combined(result))
    assert json.loads(result.output) == []
