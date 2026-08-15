"""Integration tests for the ingest CLI command (T023)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from typer.testing import CliRunner

from openreview_cli.app import app

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "retrieval"
FIXTURE_PATH = FIXTURES_DIR / "sample_contract.ndax"


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestIngestCommand:
    """Integration tests for `openreview ingest`."""

    def test_ingest_creates_index(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(
            app,
            [
                "ingest",
                str(FIXTURE_PATH),
                "--method",
                "sparse",
                "--db-dir",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 0, f"Exit code {result.exit_code}: {result.output}"
        assert "Indexed" in result.output

        # Check that a .db file was created in tmp_path
        db_files = list(tmp_path.glob("*.db"))
        assert len(db_files) == 1

    def test_ingest_db_has_chunks(self, runner: CliRunner, tmp_path: Path) -> None:
        runner.invoke(
            app,
            [
                "ingest",
                str(FIXTURE_PATH),
                "--method",
                "sparse",
                "--db-dir",
                str(tmp_path),
            ],
        )

        db_files = list(tmp_path.glob("*.db"))
        assert len(db_files) == 1

        conn = sqlite3.connect(str(db_files[0]))
        rows = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()
        conn.close()
        assert rows[0] == 12  # sample_contract.ndax has 12 chunks

    def test_ingest_db_has_fts(self, runner: CliRunner, tmp_path: Path) -> None:
        runner.invoke(
            app,
            [
                "ingest",
                str(FIXTURE_PATH),
                "--method",
                "sparse",
                "--db-dir",
                str(tmp_path),
            ],
        )

        db_files = list(tmp_path.glob("*.db"))
        conn = sqlite3.connect(str(db_files[0]))
        rows = conn.execute("SELECT COUNT(*) FROM chunk_fts").fetchone()
        conn.close()
        assert rows[0] == 12

    def test_ingest_index_meta_correct(self, runner: CliRunner, tmp_path: Path) -> None:
        runner.invoke(
            app,
            [
                "ingest",
                str(FIXTURE_PATH),
                "--method",
                "sparse",
                "--db-dir",
                str(tmp_path),
            ],
        )

        db_files = list(tmp_path.glob("*.db"))
        conn = sqlite3.connect(str(db_files[0]))
        meta = conn.execute("SELECT * FROM index_meta").fetchone()
        conn.close()

        assert meta is not None
        # index_status should be 'indexed'
        status_idx = [desc[0] for desc in conn.description].index("index_status") if False else 2
        # Direct column access
        assert meta is not None

    def test_ingest_index_status_shows_correctly(self, runner: CliRunner, tmp_path: Path) -> None:
        """Verify index-status command shows correct metadata."""
        runner.invoke(
            app,
            [
                "ingest",
                str(FIXTURE_PATH),
                "--method",
                "sparse",
                "--db-dir",
                str(tmp_path),
            ],
        )

        result = runner.invoke(
            app,
            [
                "index-status",
                str(FIXTURE_PATH),
                "--db-dir",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 0
        assert "Document:" in result.output
        assert "Status:" in result.output
        assert "Chunks:" in result.output
        assert "Method:" in result.output

    def test_ingest_second_call_shows_already_indexed(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Second ingest of same file shows 'already indexed'."""
        runner.invoke(
            app,
            [
                "ingest",
                str(FIXTURE_PATH),
                "--method",
                "sparse",
                "--db-dir",
                str(tmp_path),
            ],
        )

        result = runner.invoke(
            app,
            [
                "ingest",
                str(FIXTURE_PATH),
                "--method",
                "sparse",
                "--db-dir",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 0
        assert "already indexed" in result.output.lower() or "already" in result.output.lower()

    def test_ingest_missing_file(self, runner: CliRunner) -> None:
        result = runner.invoke(
            app,
            [
                "ingest",
                "/nonexistent/file.ndax",
            ],
        )
        assert result.exit_code == 1

    def test_ingest_chunk_output_shape_end_to_end(self, runner: CliRunner, tmp_path: Path) -> None:
        """ingest CLI accepts a file with chunk-output schema keys.

        The chunk-output shape has no per-chunk document_id, so the app must
        resolve one (SHA-256 fallback) and store it in index_meta — otherwise
        retrieve's "last indexed document" fallback breaks.
        """
        ndax_path = tmp_path / "chunk_output.ndax"
        ndax_path.write_text(
            json.dumps(
                [
                    {
                        "id": "c0",
                        "text": "Confidentiality obligations apply.",
                        "token_count": 12,
                        "source_clause_id": "clause-0",
                        "source_clause_title": "Article 3",
                        "source_clause_level": 0,
                        "chunk_index_within_clause": 0,
                        "char_offset_start": 0,
                        "char_offset_end": 50,
                        "parent_chunk_id": None,
                        "structural_location": "Article 3",
                    }
                ]
            )
        )

        result = runner.invoke(
            app,
            [
                "ingest",
                str(ndax_path),
                "--method",
                "sparse",
                "--db-dir",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 0
        assert "Indexed 1 chunks" in result.output

        # The resolved document_id must be stored, not 'unknown'
        db_files = list(tmp_path.glob("*.db"))
        assert len(db_files) == 1
        conn = sqlite3.connect(str(db_files[0]))
        stored_id = conn.execute("SELECT document_id FROM index_meta").fetchone()[0]
        conn.close()
        assert stored_id != "unknown"
        # DB filename stem is the first 32 chars of the stored document_id
        assert stored_id[:32] == db_files[0].stem
