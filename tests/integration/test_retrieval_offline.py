"""Integration tests for offline mode (T048, T049)."""

from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

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
    return json_lib.loads(output[start:end])


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
        gateway=None,
        method="sparse",
    )
    return index_db


class TestOfflineIntegration:
    """T048: Sparse-only offline mode integration tests."""

    def test_sparse_retrieve_works_offline(self, runner: CliRunner, indexed_db: Path) -> None:
        """`openreview retrieve --method sparse` works without gateway."""
        result = runner.invoke(
            app,
            [
                "retrieve",
                "confidentiality",
                str(FIXTURE_PATH),
                "--method",
                "sparse",
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

    def test_dense_offline_fallback_notice(self, runner: CliRunner, indexed_db: Path) -> None:
        """Dense retrieval without gateway falls back to BM25 and shows notice."""
        result = runner.invoke(
            app,
            [
                "retrieve",
                "confidentiality",
                str(FIXTURE_PATH),
                "--method",
                "dense",
                "--top-k",
                "3",
                "--db-dir",
                str(indexed_db.parent),
            ],
        )
        assert result.exit_code == 0, f"Exit {result.exit_code}: {result.output[:200]}"
        # Should contain fallback notice on stderr
        assert (
            "Dense retrieval unavailable" in result.output or "unavailable" in result.output.lower()
        )

    @patch("openreview_cli.gateway.router.Gateway")
    def test_hybrid_offline_fallback_notice(
        self,
        mock_gateway_class: MagicMock,
        runner: CliRunner,
        indexed_db: Path,
    ) -> None:
        """Hybrid retrieval with offline gateway falls back and shows notice."""
        mock_gw = MagicMock()
        mock_gw.embed.side_effect = ConnectionError("Connection refused")
        mock_gateway_class.return_value = mock_gw

        result = runner.invoke(
            app,
            [
                "retrieve",
                "confidentiality",
                str(FIXTURE_PATH),
                "--method",
                "hybrid",
                "--top-k",
                "3",
                "--db-dir",
                str(indexed_db.parent),
            ],
        )
        assert result.exit_code == 0, f"Exit {result.exit_code}: {result.output[:200]}"
        # Notice should be present (fallback message)
        assert (
            "Dense retrieval unavailable" in result.output or "unavailable" in result.output.lower()
        )


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
            gateway=None,
            method="sparse",
        )
        assert meta["method"] == "sparse"
        assert meta["embedding_model"] is None

        # Now retrieve using the CLI — same file, same db-dir, auto-resolved
        result = runner.invoke(
            app,
            [
                "retrieve",
                "confidentiality",
                str(FIXTURE_PATH),
                "--method",
                "sparse",
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

    def test_sparse_ingest_skips_embedding(self, tmp_path: Path) -> None:
        """Sparse-only ingest should not create chunk_embeddings table data."""
        with open(FIXTURE_PATH) as f:
            chunks: list[dict[str, Any]] = json_lib.load(f)

        db_path = tmp_path / "no_embeddings.db"
        ingest_document(
            chunks,
            str(db_path),
            gateway=None,
            method="sparse",
        )

        # Verify no embeddings were stored
        import sqlite3

        conn = sqlite3.connect(str(db_path))
        try:
            count = conn.execute("SELECT COUNT(*) FROM chunk_embeddings").fetchone()[0]
            assert count == 0, "Sparse ingest should not store embeddings"
        finally:
            conn.close()
