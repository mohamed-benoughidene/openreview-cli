"""Unit tests for safe .ndax loading (R4 / D-5).

The retrieve and ingest CLI commands crash with a raw UnicodeDecodeError
traceback when handed a non-.ndax file (e.g. a PDF) because they do a bare
``json.load`` on the file bytes. These tests pin the required behavior:

- non-.ndax (PDF/binary) input  -> clean CLI error, no traceback, exit 1
- malformed JSON                 -> clean CLI error, no traceback, exit 1
- valid JSON that is not a list  -> clean CLI error, no traceback, exit 1
- valid .ndax                    -> normal path (exit 2 "not indexed" for
  retrieve on a file that was never ingested — NOT the "not a valid" error)
- the helper ``_load_ndax_chunks`` behaves the same way at unit level
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from openreview_cli.app import _load_ndax_chunks, app

VALID_NDAX = b'[{"document_id": "abc", "text": "hi"}]'


@pytest.fixture(autouse=True)
def _no_init(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep CLI invocations hermetic: skip config/auth/database setup.

    ``_root`` calls ``_init`` on every invocation; it writes to the real
    config dir and opens log files. These tests only exercise the
    file-loading path, so stub ``_init`` out entirely.
    """

    def _stub_init(debug: bool = False) -> None:
        pass

    monkeypatch.setattr("openreview_cli.app._init", _stub_init)


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestRetrieveCli:
    """`openreview retrieve "<query>" <file>` must reject bad .ndax cleanly."""

    def test_retrieve_pdf_file_is_clean_error(self, runner: CliRunner, tmp_path: Path) -> None:
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n")

        result = runner.invoke(app, ["retrieve", "confidentiality", str(pdf)])

        assert result.exit_code == 1
        assert "not a valid" in result.output
        assert "Traceback" not in result.output

    def test_retrieve_malformed_json_is_clean_error(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        bad = tmp_path / "bad.ndax"
        bad.write_bytes(b"not json")

        result = runner.invoke(app, ["retrieve", "confidentiality", str(bad)])

        assert result.exit_code == 1
        assert "not a valid" in result.output
        assert "Traceback" not in result.output

    def test_retrieve_non_list_json_is_clean_error(self, runner: CliRunner, tmp_path: Path) -> None:
        obj = tmp_path / "object.ndax"
        obj.write_bytes(b"{}")

        result = runner.invoke(app, ["retrieve", "confidentiality", str(obj)])

        assert result.exit_code == 1
        assert "not a valid" in result.output
        assert "Traceback" not in result.output

    def test_retrieve_list_of_non_chunks_is_clean_error(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        weird = tmp_path / "weird.ndax"
        weird.write_bytes(b'["a", "b", "c"]')

        result = runner.invoke(app, ["retrieve", "confidentiality", str(weird)])

        assert result.exit_code == 1
        assert "not a valid" in result.output
        assert "Traceback" not in result.output

    def test_retrieve_valid_ndax_not_ingested_is_not_valid_error(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Valid .ndax must NOT be rejected as invalid; it takes the normal
        'not indexed' path (exit 2) because the file was never ingested."""
        valid = tmp_path / "valid.ndax"
        valid.write_bytes(VALID_NDAX)

        result = runner.invoke(app, ["retrieve", "confidentiality", str(valid)])

        assert result.exit_code == 2
        assert "not indexed" in result.output.lower()
        assert "not a valid" not in result.output
        assert "Traceback" not in result.output


class TestIngestCli:
    """`openreview ingest <file>` must get the same clean handling."""

    def test_ingest_pdf_file_is_clean_error(self, runner: CliRunner, tmp_path: Path) -> None:
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n")

        result = runner.invoke(app, ["ingest", str(pdf)])

        assert result.exit_code == 1
        assert "not a valid" in result.output
        assert "Traceback" not in result.output

    def test_ingest_malformed_json_is_clean_error(self, runner: CliRunner, tmp_path: Path) -> None:
        bad = tmp_path / "bad.ndax"
        bad.write_bytes(b"not json")

        result = runner.invoke(app, ["ingest", str(bad)])

        assert result.exit_code == 1
        assert "not a valid" in result.output
        assert "Traceback" not in result.output

    def test_ingest_non_list_json_is_clean_error(self, runner: CliRunner, tmp_path: Path) -> None:
        obj = tmp_path / "object.ndax"
        obj.write_bytes(b"{}")

        result = runner.invoke(app, ["ingest", str(obj)])

        assert result.exit_code == 1
        assert "not a valid" in result.output
        assert "Traceback" not in result.output


class TestLoadNdaxChunks:
    """Helper-level behavior of ``_load_ndax_chunks``."""

    def test_pdf_raises_clean_exit(self, tmp_path: Path) -> None:
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")

        with pytest.raises(typer.Exit) as exc_info:
            _load_ndax_chunks(pdf)
        assert exc_info.value.exit_code == 1

    def test_malformed_json_raises_clean_exit(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.ndax"
        bad.write_bytes(b"not json")

        with pytest.raises(typer.Exit) as exc_info:
            _load_ndax_chunks(bad)
        assert exc_info.value.exit_code == 1

    def test_non_list_json_raises_clean_exit(self, tmp_path: Path) -> None:
        obj = tmp_path / "object.ndax"
        obj.write_bytes(b"{}")

        with pytest.raises(typer.Exit) as exc_info:
            _load_ndax_chunks(obj)
        assert exc_info.value.exit_code == 1

    def test_list_of_non_chunks_raises_clean_exit(self, tmp_path: Path) -> None:
        weird = tmp_path / "weird.ndax"
        weird.write_bytes(b'["a", "b"]')

        with pytest.raises(typer.Exit) as exc_info:
            _load_ndax_chunks(weird)
        assert exc_info.value.exit_code == 1

    def test_valid_ndax_returns_chunks(self, tmp_path: Path) -> None:
        valid = tmp_path / "valid.ndax"
        valid.write_bytes(VALID_NDAX)

        chunks: list[dict[str, Any]] = _load_ndax_chunks(valid)

        assert chunks == [{"document_id": "abc", "text": "hi"}]

    def test_empty_list_is_accepted(self, tmp_path: Path) -> None:
        """An empty list is structurally valid JSON; emptiness is the
        caller's concern (ingest has its own 'No chunks found' guard)."""
        empty = tmp_path / "empty.ndax"
        empty.write_bytes(b"[]")

        chunks: list[dict[str, Any]] = _load_ndax_chunks(empty)

        assert chunks == []
