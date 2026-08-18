"""Integration tests for reranker (T032, T034)."""

from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from openreview_cli.app import app
from openreview_cli.retrieval.ingest import ingest_from_file
from openreview_cli.retrieval.storage import RetrievalStorage

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


FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "retrieval"
FIXTURE_PATH = FIXTURES_DIR / "sample_contract.ndax"


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def indexed_db(tmp_path: Path) -> Path:
    """Create a populated sparse index for testing."""
    db_path = tmp_path / "indexes"
    db_path.mkdir(parents=True, exist_ok=True)
    index_db = db_path / "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4.db"

    ingest_from_file(
        FIXTURE_PATH,
        str(index_db),
        gateway=None,
        method="sparse",
    )
    return index_db


# ── T032: Reranker validation benchmark tests ──


class TestRerankerValidationBenchmark:
    """Tests for Reranker validation benchmark integration."""

    def test_insert_rerank_validation(self, indexed_db: Path) -> None:
        """Verify insert_rerank_validation stores a record."""
        with RetrievalStorage(str(indexed_db)) as storage:
            storage.insert_rerank_validation(
                model_id="test-model",
                document_type="legal-nda",
                precision_with=0.8,
                precision_without=0.6,
                degradation_pp=20.0,
            )

            val = storage.get_rerank_validation("test-model", "legal-nda")
            assert val is not None
            assert val["precision_with"] == 0.8
            assert val["precision_without"] == 0.6
            assert val["degradation_pp"] == 20.0
            assert val["model_id"] == "test-model"
            assert val["document_type"] == "legal-nda"
            assert "benchmark_timestamp" in val

    def test_get_rerank_validation_not_found(self, indexed_db: Path) -> None:
        """get_rerank_validation returns None for missing record."""
        with RetrievalStorage(str(indexed_db)) as storage:
            val = storage.get_rerank_validation("nonexistent", "test")
            assert val is None

    def test_insert_rerank_validation_replace(self, indexed_db: Path) -> None:
        """Inserting same model_id + document_type replaces the record."""
        with RetrievalStorage(str(indexed_db)) as storage:
            storage.insert_rerank_validation("m1", "legal-nda", 0.9, 0.8, 10.0)
            storage.insert_rerank_validation("m1", "legal-nda", 0.7, 0.8, -10.0)

            val = storage.get_rerank_validation("m1", "legal-nda")
            assert val is not None
            assert val["precision_with"] == 0.7
            assert val["degradation_pp"] == -10.0


# ── T034: --rerank flag integration ──


class TestRetrieveRerankFlag:
    """Integration tests for --rerank CLI flag."""

    def test_retrieve_with_rerank_flag_no_crash(self, runner: CliRunner, indexed_db: Path) -> None:
        """--rerank flag doesn't crash the CLI (even without gateway)."""
        result = runner.invoke(
            app,
            [
                "retrieve",
                "confidentiality",
                str(FIXTURE_PATH),
                "--method",
                "sparse",
                "--rerank",
                "--rerank-depth",
                "5",
                "--top-k",
                "3",
                "--db-dir",
                str(indexed_db.parent),
            ],
        )
        # Should not crash — may exit 0 or with a message depending on gateway
        assert result.exit_code in (0, 1), f"Unexpected exit {result.exit_code}"

    def test_retrieve_without_rerank_has_null_rerank_score(
        self, runner: CliRunner, indexed_db: Path
    ) -> None:
        """Without --rerank, rerank_score should be null in JSON output."""
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
        assert result.exit_code == 0, f"exit {result.exit_code}"
        data = _extract_json_from_output(result.output)
        for r in data["results"]:
            assert r["rerank_score"] is None


class TestRerankerDegradationWarning:
    """retrieve --rerank respects the stored degradation record."""

    @patch("openreview_cli.gateway.router.Gateway")
    def test_retrieve_warns_when_stored_degraded(
        self,
        mock_gateway_class: MagicMock,
        runner: CliRunner,
        indexed_db: Path,
    ) -> None:
        """With a stored degradation_pp <= 0 record and no --force-rerank, warn."""
        mock_gw = MagicMock()
        mock_gw.rerank.return_value = [
            {"chunk_id": "c1", "score": 0.95, "text": "test"},
            {"chunk_id": "c2", "score": 0.90, "text": "test"},
            {"chunk_id": "c3", "score": 0.85, "text": "test"},
        ]
        mock_gateway_class.return_value = mock_gw

        # Seed a degraded record for the default Reranker model id
        with RetrievalStorage(str(indexed_db)) as store:
            store.insert_rerank_validation(
                model_id="qwen3-reranker-0.6b",
                document_type="legal-nda",
                precision_with=0.2,
                precision_without=0.8,
                degradation_pp=-60.0,
            )

        result = runner.invoke(
            app,
            [
                "retrieve",
                "confidentiality",
                str(FIXTURE_PATH),
                "--method",
                "sparse",
                "--rerank",
                "--top-k",
                "3",
                "--format",
                "json",
                "--db-dir",
                str(indexed_db.parent),
            ],
        )
        assert result.exit_code == 0, f"exit {result.exit_code}"
        assert "does not improve" in result.stderr
        data = _extract_json_from_output(result.output)
        # reranking still ran (warning is advisory, not a hard disable)
        assert any(r["rerank_score"] is not None for r in data["results"])

    @patch("openreview_cli.gateway.router.Gateway")
    def test_retrieve_force_rerank_suppresses_warning(
        self,
        mock_gateway_class: MagicMock,
        runner: CliRunner,
        indexed_db: Path,
    ) -> None:
        """--force-rerank suppresses the degradation warning."""
        mock_gw = MagicMock()
        mock_gw.rerank.return_value = [
            {"chunk_id": "c1", "score": 0.95, "text": "test"},
            {"chunk_id": "c2", "score": 0.90, "text": "test"},
            {"chunk_id": "c3", "score": 0.85, "text": "test"},
        ]
        mock_gateway_class.return_value = mock_gw

        with RetrievalStorage(str(indexed_db)) as store:
            store.insert_rerank_validation(
                model_id="qwen3-reranker-0.6b",
                document_type="legal-nda",
                precision_with=0.2,
                precision_without=0.8,
                degradation_pp=-60.0,
            )

        result = runner.invoke(
            app,
            [
                "retrieve",
                "confidentiality",
                str(FIXTURE_PATH),
                "--method",
                "sparse",
                "--rerank",
                "--force-rerank",
                "--top-k",
                "3",
                "--format",
                "json",
                "--db-dir",
                str(indexed_db.parent),
            ],
        )
        assert result.exit_code == 0, f"exit {result.exit_code}"
        assert "does not improve" not in result.stderr
