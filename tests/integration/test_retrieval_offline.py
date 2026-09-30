"""Integration tests for offline mode (T048, T049)."""

from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any, cast

import pytest
from typer.testing import CliRunner

from openreview_cli.app import app
from openreview_cli.retrieval.ingest import ingest_document

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "retrieval"
FIXTURE_PATH = FIXTURES_DIR / "sample_contract.ndax"


def _extract_json_from_output(output: str) -> dict[str, Any]:
    """Extract JSON dict from mixed stdout+stderr output."""
    start = output.find("{")
    if start < 0:
        msg = f"No JSON object found in output:\n{output[:500]}"
        raise ValueError(msg)
    depth = 0
    end = start
    for i in range(start, len(output)):
        if output[i] == "{":
            depth += 1
        elif output[i] == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if depth != 0:
        msg = f"Unmatched braces in output:\n{output[:500]}"
        raise ValueError(msg)
    return cast("dict[str, Any]", json_lib.loads(output[start:end]))


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def indexed_db(tmp_path: Path) -> Path:
    """Create a sparse-only populated index (no embeddings)."""
    db_path = tmp_path / "indexes"
    db_path.mkdir(parents=True, exist_ok=True)
    index_db = db_path / "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4.db"

    with open(FIXTURE_PATH) as f:
        chunks: list[dict[str, Any]] = json_lib.load(f)

    ingest_document(
        chunks,
        str(index_db),
    )
    return index_db


class TestOfflineIntegration:
    """T048: keyword-only offline mode integration tests."""

    def test_sparse_retrieve_works_offline(self, runner: CliRunner, indexed_db: Path) -> None:
        """`openreview retrieve` works without a gateway."""
        result = runner.invoke(
            app,
            [
                "retrieve",
                "confidentiality",
                str(FIXTURE_PATH),
                "--top-k",
                "3",
                "--format",
                "json",
                "--db-dir",
                str(indexed_db.parent),
            ],
        )
        assert result.exit_code == 0, f"Exit {result.exit_code}: {result.output[:200]}"
        data = _extract_json_from_output(result.output)
        assert data["method"] == "sparse"
        assert len(data["results"]) > 0


class TestOfflineE2E:
    """T049: Full offline end-to-end workflow."""

    def test_sparse_only_ingest_and_retrieve(self, tmp_path: Path, runner: CliRunner) -> None:
        """Complete offline workflow: sparse ingest → retrieve — no network needed."""
        # Read fixture chunks
        with open(FIXTURE_PATH) as f:
            chunks: list[dict[str, Any]] = json_lib.load(f)

        doc_id = chunks[0]["document_id"][:32]

        # Ingest sparse-only using hash-based file name (matches CLI convention)
        db_dir = tmp_path / "indexes"
        db_dir.mkdir(parents=True, exist_ok=True)
        index_db = db_dir / f"{doc_id}.db"

        meta = ingest_document(
            chunks,
            str(index_db),
        )
        assert meta["method"] == "sparse"

        # Now retrieve using the CLI — same file, same db-dir, auto-resolved
        result = runner.invoke(
            app,
            [
                "retrieve",
                "confidentiality",
                str(FIXTURE_PATH),
                "--top-k",
                "3",
                "--format",
                "json",
                "--db-dir",
                str(db_dir),
            ],
        )
        assert result.exit_code == 0, f"Exit {result.exit_code}: {result.output[:200]}"
        data = _extract_json_from_output(result.output)
        assert len(data["results"]) > 0
        assert data["method"] == "sparse"

    def test_sparse_ingest_creates_no_embedding_table(self, tmp_path: Path) -> None:
        """Keyword ingest must not create any embedding storage."""
        with open(FIXTURE_PATH) as f:
            chunks: list[dict[str, Any]] = json_lib.load(f)

        db_path = tmp_path / "no_embeddings.db"
        ingest_document(
            chunks,
            str(db_path),
        )

        # Verify no embedding storage was created
        import sqlite3

        conn = sqlite3.connect(str(db_path))
        try:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='chunk_embeddings'"
            ).fetchall()
            assert rows == [], "Keyword ingest must not create chunk_embeddings"
        finally:
            conn.close()
