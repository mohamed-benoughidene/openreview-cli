"""Integration tests for index-status and index-clear CLI commands (T050-T053)."""

from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from openreview_cli.app import app
from openreview_cli.retrieval.ingest import ingest_document

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "retrieval"
FIXTURE_PATH = FIXTURES_DIR / "sample_contract.ndax"


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def indexed_env(tmp_path: Path) -> tuple[Path, Path, str]:
    """Create a sparse-only indexed environment.

    Returns:
        (db_dir, fixture_copy_path, doc_hash) where doc_hash[:32] is the
        stem used for the SQLite db file.
    """
    # Copy fixture to tmp_path so we can compute hash from the copy
    fixture_copy = tmp_path / "sample_contract.ndax"
    fixture_copy.write_bytes(FIXTURE_PATH.read_bytes())

    with open(fixture_copy) as f:
        chunks: list[dict[str, Any]] = json_lib.load(f)

    doc_id = chunks[0]["document_id"]
    doc_hash = doc_id[:32]

    db_dir = tmp_path / "indexes"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / f"{doc_hash}.db"

    ingest_document(chunks, str(db_path), gateway=None, method="sparse")
    return db_dir, fixture_copy, doc_hash


class TestIndexStatus:
    """T050/T052: index-status command."""

    def test_index_status_shows_metadata(
        self, runner: CliRunner, indexed_env: tuple[Path, Path, str]
    ) -> None:
        """index-status shows correct metadata for indexed document."""
        db_dir, fixture_copy, doc_hash = indexed_env

        result = runner.invoke(
            app,
            ["index-status", str(fixture_copy), "--db-dir", str(db_dir)],
        )
        assert result.exit_code == 0, f"Exit {result.exit_code}: {result.output[:300]}"
        output = result.output

        # Should show document name
        assert fixture_copy.name in output
        # Should show chunk count (12 chunks in fixture)
        assert "12" in output or "Chunks:" in output
        # Should show status
        assert "indexed" in output.lower() or "Indexed" in output
        # Should show method
        assert "sparse" in output.lower() or "Sparse" in output or "none" in output.lower()

    def test_index_status_error_no_index(self, runner: CliRunner, tmp_path: Path) -> None:
        """index-status prints error when no index exists."""
        fixture_copy = tmp_path / "sample_contract.ndax"
        fixture_copy.write_bytes(FIXTURE_PATH.read_bytes())

        result = runner.invoke(
            app,
            ["index-status", str(fixture_copy), "--db-dir", str(tmp_path / "nonexistent")],
        )
        assert result.exit_code == 2, f"Exit {result.exit_code}: {result.output[:300]}"
        assert "not indexed" in result.output.lower() or "Document not indexed" in result.output

    def test_index_status_no_file(self, runner: CliRunner) -> None:
        """index-status requires a file argument."""
        result = runner.invoke(app, ["index-status"])
        assert result.exit_code != 0
        assert "Error" in result.output or "FILE" in result.output

    def test_index_status_file_not_found(self, runner: CliRunner) -> None:
        """index-status errors on nonexistent file."""
        result = runner.invoke(app, ["index-status", "/nonexistent/file.ndax"])
        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "Error" in result.output

    def test_index_status_metadata_values(self, runner: CliRunner, tmp_path: Path) -> None:
        """Verify specific metadata fields from index-status output."""
        # Create fixture copy and index manually
        fixture_copy = tmp_path / "test_contract.ndax"
        fixture_copy.write_bytes(FIXTURE_PATH.read_bytes())

        with open(fixture_copy) as f:
            chunks: list[dict[str, Any]] = json_lib.load(f)

        doc_id = chunks[0]["document_id"][:32]
        db_dir = tmp_path / "idx"
        db_dir.mkdir(parents=True, exist_ok=True)
        db_path = db_dir / f"{doc_id}.db"

        ingest_document(chunks, str(db_path), gateway=None, method="sparse")

        result = runner.invoke(
            app,
            ["index-status", str(fixture_copy), "--db-dir", str(db_dir)],
        )
        assert result.exit_code == 0
        output = result.output

        # Check for metadata fields in human-readable output
        assert "Chunks:" in output or "chunks" in output.lower()
        assert "Status:" in output or "status" in output.lower()
        assert "Method:" in output or "method" in output.lower()


class TestIndexClear:
    """T051/T053: index-clear command."""

    def test_index_clear_removes_db(
        self, runner: CliRunner, indexed_env: tuple[Path, Path, str]
    ) -> None:
        """index-clear removes the index database file."""
        db_dir, fixture_copy, doc_hash = indexed_env
        db_path = db_dir / f"{doc_hash}.db"
        assert db_path.exists(), "DB should exist before clear"

        result = runner.invoke(
            app,
            ["index-clear", str(fixture_copy), "--db-dir", str(db_dir)],
        )
        assert result.exit_code == 0, f"Exit {result.exit_code}: {result.output[:300]}"
        assert not db_path.exists(), "DB should be removed after clear"
        assert "cleared" in result.output.lower()

    def test_index_clear_error_no_index(self, runner: CliRunner, tmp_path: Path) -> None:
        """index-clear errors when no index exists."""
        fixture_copy = tmp_path / "sample_contract.ndax"
        fixture_copy.write_bytes(FIXTURE_PATH.read_bytes())

        result = runner.invoke(
            app,
            ["index-clear", str(fixture_copy), "--db-dir", str(tmp_path / "empty")],
        )
        assert result.exit_code == 2, f"Exit {result.exit_code}: {result.output[:300]}"
        assert "not indexed" in result.output.lower()

    def test_index_clear_no_file(self, runner: CliRunner) -> None:
        """index-clear requires a file argument."""
        result = runner.invoke(app, ["index-clear"])
        assert result.exit_code != 0
        assert "Error" in result.output or "FILE" in result.output

    def test_index_clear_file_not_found(self, runner: CliRunner) -> None:
        """index-clear errors on nonexistent file."""
        result = runner.invoke(app, ["index-clear", "/nonexistent/file.ndax"])
        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "Error" in result.output

    def test_index_clear_all_flag(self, runner: CliRunner, tmp_path: Path) -> None:
        """index-clear --all clears all indexes in the db dir."""
        # Create two separate indexes
        db_dir = tmp_path / "indexes"
        db_dir.mkdir(parents=True, exist_ok=True)

        # Create two dummy DB files
        (db_dir / "doc1.db").write_text("dummy")
        (db_dir / "doc2.db").write_text("dummy")
        assert len(list(db_dir.glob("*.db"))) == 2

        result = runner.invoke(
            app,
            ["index-clear", "--all", "--db-dir", str(db_dir)],
        )
        assert result.exit_code == 0
        assert "Cleared" in result.output or "cleared" in result.output
        assert len(list(db_dir.glob("*.db"))) == 0

    def test_index_clear_reingest_possible(
        self, runner: CliRunner, indexed_env: tuple[Path, Path, str]
    ) -> None:
        """After index-clear, re-ingesting should succeed."""
        db_dir, fixture_copy, doc_hash = indexed_env
        db_path = db_dir / f"{doc_hash}.db"

        # Clear
        runner.invoke(app, ["index-clear", str(fixture_copy), "--db-dir", str(db_dir)])
        assert not db_path.exists()

        # Re-ingest (via direct call since CLI ingest reads ndax data)
        with open(fixture_copy) as f:
            chunks: list[dict[str, Any]] = json_lib.load(f)
        meta = ingest_document(chunks, str(db_path), gateway=None, method="sparse")
        assert meta["index_status"] == "indexed"
        assert db_path.exists()
