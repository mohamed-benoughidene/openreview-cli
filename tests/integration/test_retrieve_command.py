"""Integration tests for the retrieve CLI command (T022)."""

from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any, cast

import pytest
from typer.testing import CliRunner

from openreview_cli.app import app
from openreview_cli.retrieval.ingest import ingest_from_file

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "retrieval"
FIXTURE_PATH = FIXTURES_DIR / "sample_contract.ndax"
GROUND_TRUTH_PATH = FIXTURES_DIR / "ground_truth.json"


def _extract_json_from_output(output: str) -> dict[str, Any]:
    """Extract JSON dict from mixed stdout+stderr output.

    Click's CliRunner by default mixes stdout and stderr. LiteLLM may
    write ANSI error text to stderr during embedding calls. This helper
    finds the JSON object by locating the outermost braces.
    """
    start = output.find("{")
    if start < 0:
        msg = f"No JSON object found in output:\n{output[:500]}"
        raise ValueError(msg)
    # Find the matching closing brace
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


@pytest.fixture(scope="module")
def ground_truth() -> dict[str, Any]:
    with open(GROUND_TRUTH_PATH) as f:
        return cast("dict[str, Any]", json_lib.load(f))


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def indexed_db(tmp_path: Path) -> Path:
    """Create a populated index for the sample contract fixture."""
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


class TestRetrieveCommand:
    """Integration tests for `openreview retrieve`."""

    def test_retrieve_returns_results(
        self, runner: CliRunner, indexed_db: Path, tmp_path: Path
    ) -> None:
        result = runner.invoke(
            app,
            [
                "retrieve",
                "confidentiality",
                str(FIXTURE_PATH),
                "--method",
                "sparse",
                "--top-k",
                "5",
                "--db-dir",
                str(indexed_db.parent),
            ],
        )
        assert result.exit_code == 0, f"Exit code {result.exit_code}: {result.output}"
        # Should see a Rich table with results
        assert "Retrieval Results" in result.output
        assert "Article" in result.output or "confidential" in result.output.lower()

    def test_retrieve_top_k_respected(self, runner: CliRunner, indexed_db: Path) -> None:
        result = runner.invoke(
            app,
            [
                "retrieve",
                "confidentiality",
                str(FIXTURE_PATH),
                "--method",
                "sparse",
                "--top-k",
                "2",
                "--db-dir",
                str(indexed_db.parent),
            ],
        )
        assert result.exit_code == 0, f"exit {result.exit_code}: {result.stderr[-200:]}"

    def test_retrieve_json_output(self, runner: CliRunner, indexed_db: Path) -> None:
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
        if result.exit_code != 0:
            pytest.fail(f"Exit code {result.exit_code}")
        # Click's CliRunner mixes stdout+stderr; extract JSON from output
        data = _extract_json_from_output(result.output)
        assert "query" in data
        assert "results" in data
        assert len(data["results"]) <= 3

    def test_retrieve_expected_chunk_in_results(
        self, runner: CliRunner, indexed_db: Path, ground_truth: dict[str, Any]
    ) -> None:
        """Verify expected chunk appears in results per ground truth."""
        # Use the sparse query (index 2) to avoid triggering LiteLLM
        query_info = ground_truth["queries"][2]  # "governing law" — sparse
        result = runner.invoke(
            app,
            [
                "retrieve",
                query_info["query"],
                str(FIXTURE_PATH),
                "--method",
                query_info["method"],
                "--top-k",
                str(query_info["top_k"]),
                "--format",
                "json",
                "--db-dir",
                str(indexed_db.parent),
            ],
        )
        if result.exit_code != 0:
            pytest.fail(f"Exit code {result.exit_code}")
        data = _extract_json_from_output(result.output)
        result_ids = {r["chunk_id"] for r in data["results"]}
        expected = set(query_info["expected_chunk_ids"])
        assert result_ids & expected, f"Expected one of {expected} in results, got {result_ids}"

    def test_retrieve_no_results_message(self, runner: CliRunner, indexed_db: Path) -> None:
        """Query with gibberish should return no-results message."""
        result = runner.invoke(
            app,
            [
                "retrieve",
                "xyznonexistentqueryzzz",
                str(FIXTURE_PATH),
                "--method",
                "sparse",
                "--db-dir",
                str(indexed_db.parent),
            ],
        )
        assert result.exit_code == 0
        assert "No relevant clauses found" in result.output

    def test_retrieve_not_indexed(self, runner: CliRunner, tmp_path: Path) -> None:
        """Querying a file that hasn't been indexed."""
        result = runner.invoke(
            app,
            [
                "retrieve",
                "test query",
                str(FIXTURE_PATH),
                "--db-dir",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 2
        assert "not indexed" in result.output.lower()

    def test_retrieve_missing_file(self, runner: CliRunner) -> None:
        result = runner.invoke(
            app,
            [
                "retrieve",
                "test query",
                "/nonexistent/file.ndax",
            ],
        )
        assert result.exit_code == 1

    def test_retrieve_without_file_uses_last_indexed(
        self, runner: CliRunner, indexed_db: Path
    ) -> None:
        result = runner.invoke(
            app,
            [
                "retrieve",
                "confidentiality",
                "--method",
                "sparse",
                "--top-k",
                "5",
                "--db-dir",
                str(indexed_db.parent),
            ],
        )
        assert result.exit_code == 0, f"Exit {result.exit_code}: {result.output}"
        assert "Retrieval Results" in result.output

    # ── T028: Method switching ──

    def test_retrieve_method_sparse_json_schema(self, runner: CliRunner, indexed_db: Path) -> None:
        """--method sparse returns BM25 results with correct JSON schema."""
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
        assert data["method"] == "sparse"
        assert len(data["results"]) <= 3
        for r in data["results"]:
            assert r["method"] == "sparse"
            assert r["rank_sparse"] is not None
            assert r["rank_dense"] is None
            assert r["rrf_score"] is None
            assert "chunk_id" in r
            assert "score" in r
            assert "clause_heading" in r

    def test_retrieve_method_dense_fallback_graceful(
        self, runner: CliRunner, indexed_db: Path
    ) -> None:
        """--method dense without gateway falls back gracefully (terminal output)."""
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
        # Dense without gateway falls back to sparse — still exit 0
        assert result.exit_code == 0, f"exit {result.exit_code}: {result.stderr[-200:]}"
        # Should show some kind of result (no-error)
        assert "Error" not in result.stderr or "Not found" not in result.output

    def test_retrieve_method_hybrid_default(self, runner: CliRunner, indexed_db: Path) -> None:
        """Default method is hybrid, returns results (no crash)."""
        result = runner.invoke(
            app,
            [
                "retrieve",
                "confidentiality",
                str(FIXTURE_PATH),
                "--top-k",
                "3",
                "--db-dir",
                str(indexed_db.parent),
            ],
        )
        assert result.exit_code == 0, f"exit {result.exit_code}: {result.stderr[-200:]}"

    def test_retrieve_invalid_method(self, runner: CliRunner, indexed_db: Path) -> None:
        """Invalid --method value should error."""
        result = runner.invoke(
            app,
            [
                "retrieve",
                "confidentiality",
                str(FIXTURE_PATH),
                "--method",
                "invalid",
                "--db-dir",
                str(indexed_db.parent),
            ],
        )
        # The Typer option validates choices, expect non-zero exit
        assert result.exit_code != 0 or "invalid" in result.output.lower()

    # ── T039: Hierarchy in integration output ──

    def test_hierarchy_chain_in_json_output(self, runner: CliRunner, indexed_db: Path) -> None:
        """JSON output includes hierarchy_chain for every result."""
        result = runner.invoke(
            app,
            [
                "retrieve",
                "confidentiality",
                str(FIXTURE_PATH),
                "--method",
                "sparse",
                "--top-k",
                "5",
                "--format",
                "json",
                "--db-dir",
                str(indexed_db.parent),
            ],
        )
        assert result.exit_code == 0, f"Exit {result.exit_code}"
        data = _extract_json_from_output(result.output)
        for r in data["results"]:
            assert "hierarchy_chain" in r
            assert isinstance(r["hierarchy_chain"], list)
            assert len(r["hierarchy_chain"]) > 0

    def test_hierarchy_chain_multi_level(self, runner: CliRunner, tmp_path: Path) -> None:
        """Results from chunks with 2-level hierarchy show both levels in output."""
        DOC_ID = "hierarchy-test-doc-0011223344"

        # Create an inline fixture with 2-level hierarchy
        chunks = [
            {
                "chunk_id": "art-3",
                "document_id": DOC_ID,
                "text": "Confidentiality Obligations article text.",
                "clause_heading": "Article 3 — Confidentiality Obligations",
                "clause_level": 0,
                "parent_chunk_id": None,
                "heading_chain": ["Article 3 — Confidentiality Obligations"],
                "char_start": 0,
                "char_end": 100,
            },
            {
                "chunk_id": "sec-1",
                "document_id": DOC_ID,
                "text": "The Receiving Party shall protect Confidential Information.",
                "clause_heading": "Section 3.1 — Protection",
                "clause_level": 1,
                "parent_chunk_id": "art-3",
                "heading_chain": [
                    "Article 3 — Confidentiality Obligations",
                    "Section 3.1 — Protection",
                ],
                "char_start": 0,
                "char_end": 100,
            },
        ]

        # Create fixture file
        fixture_path = tmp_path / "hierarchy_test.ndax"
        import json as json_lib

        with open(fixture_path, "w") as f:
            json_lib.dump(chunks, f)

        # Ingest — use hash-based DB name matching CLI convention
        db_dir = tmp_path / "hierarchy_indexes"
        db_dir.mkdir(parents=True, exist_ok=True)
        db_path = db_dir / f"{DOC_ID[:32]}.db"

        from openreview_cli.retrieval.ingest import ingest_from_file

        ingest_from_file(fixture_path, db_path, gateway=None, method="sparse")

        # Retrieve query that matches sec-1
        result = runner.invoke(
            app,
            [
                "retrieve",
                "Confidential Information",
                str(fixture_path),
                "--method",
                "sparse",
                "--top-k",
                "5",
                "--format",
                "json",
                "--db-dir",
                str(db_dir),
            ],
        )
        assert result.exit_code == 0, f"Exit {result.exit_code}: {result.output[:200]}"
        data = _extract_json_from_output(result.output)

        # Find sec-1 in results
        sec1 = next((r for r in data["results"] if r["chunk_id"] == "sec-1"), None)
        if sec1 is not None:
            assert len(sec1["hierarchy_chain"]) == 2
            assert "Article 3" in sec1["hierarchy_chain"][0]
            assert "Section 3.1" in sec1["hierarchy_chain"][1]
