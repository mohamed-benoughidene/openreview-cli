"""Integration tests for bilateral comparison error handling.

Tests error paths: missing files, corrupt documents, empty documents.
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from openreview_cli.app import app


class TestMissingFile:
    """Tests for missing file handling."""

    def test_missing_first_file_exits_error(self) -> None:
        """Missing first file should exit code 1."""
        runner = CliRunner()
        result = runner.invoke(
            app,
            ["precheck", "compare", "/nonexistent/a.pdf", "/nonexistent/b.pdf"],
        )
        assert result.exit_code != 0


class TestCorruptFile:
    """Tests for corrupt file handling."""

    def test_corrupt_file_exits_error(self, tmp_path: Path) -> None:
        """Corrupt PDF should exit with error code."""
        corrupt = tmp_path / "corrupt.pdf"
        corrupt.write_bytes(b"not a pdf at all")
        runner = CliRunner()

        good = tmp_path / "good.pdf"
        good.write_bytes(
            b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
            b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
            b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n"
            b"0000000115 00000 n \ntrailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n190\n%%EOF"
        )

        result = runner.invoke(
            app,
            ["precheck", "compare", str(corrupt), str(good)],
        )
        assert result.exit_code != 0
