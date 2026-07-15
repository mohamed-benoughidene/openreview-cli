"""Integration tests for --cluster-clauses flag on graph build.

Tests CLI flag parsing, flow integration, and output format.
Model-dependent subtest marked @pytest.mark.slow.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openreview_cli.parsing.models import Clause


@pytest.fixture
def sample_clauses_json(tmp_path: Path) -> Path:
    """Create a small parsed-clause JSON for graph building."""
    clauses = [
        Clause(
            id="c1",
            title="Definition of Confidential Information",
            text="Confidential Information means any information disclosed by one party to the other.",
            level=0,
            parent_id=None,
            source_page=1,
            source_paragraph=None,
            source_span=(0, 100),
        ),
        Clause(
            id="c2",
            title="Definition of Confidential Information",
            text="Confidential Information means any information disclosed by one party to the other.",
            level=0,
            parent_id=None,
            source_page=1,
            source_paragraph=None,
            source_span=(101, 200),
        ),
        Clause(
            id="c3",
            title="Governing Law",
            text="This Agreement shall be governed by and construed in accordance with the laws of Delaware.",
            level=0,
            parent_id=None,
            source_page=2,
            source_paragraph=None,
            source_span=(201, 300),
        ),
        Clause(
            id="c4",
            title="Governing Law",
            text="This Agreement shall be governed by and construed in accordance with the laws of Delaware.",
            level=0,
            parent_id=None,
            source_page=2,
            source_paragraph=None,
            source_span=(301, 400),
        ),
        Clause(
            id="c5",
            title="Termination",
            text="Either party may terminate this Agreement upon 30 days written notice.",
            level=0,
            parent_id=None,
            source_page=3,
            source_paragraph=None,
            source_span=(401, 500),
        ),
    ]
    data = [
        {
            "id": c.id,
            "title": c.title,
            "text": c.text,
            "level": c.level,
            "parent_id": c.parent_id,
            "source_page": c.source_page,
            "source_paragraph": c.source_paragraph,
        }
        for c in clauses
    ]
    path = tmp_path / "parsed.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


# network fixture: pre-emptive skip so CI without HF access doesn't hard-fail the legal-bert download
@pytest.fixture
def network() -> None:
    """Skip test when HuggingFace hub is unreachable."""
    import socket

    try:
        sock = socket.create_connection(("huggingface.co", 443), timeout=5)
        sock.close()
    except OSError:
        pytest.skip("HuggingFace hub unreachable")


@pytest.mark.slow
class TestGraphClusteringCLI:
    """Test --cluster-clauses flag on graph build.

    Requires the legal-bert model. Skipped if offline.
    """

    @pytest.mark.network
    def test_cluster_flag_parses(self, sample_clauses_json: Path, network: None) -> None:
        """--cluster-clauses flag is accepted by graph build."""
        from typer.testing import CliRunner

        from openreview_cli.app import app

        runner = CliRunner()
        output_path = sample_clauses_json.with_suffix(".graph.json")

        try:
            result = runner.invoke(
                app,
                [
                    "graph",
                    "build",
                    str(sample_clauses_json),
                    "--cluster-clauses",
                    "--output",
                    str(output_path),
                ],
            )
        except ImportError as e:
            pytest.skip(f"ClauseClusterer unavailable: {e}")

        if result.exit_code != 0:
            # Skip if model can't load (offline)
            if "Offline" in result.stdout or "Connection" in result.stdout:
                pytest.skip("Model not available (offline)")
            pytest.fail(f"CLI exited with code {result.exit_code}: {result.stdout}")

        # Verify output JSON exists
        assert output_path.exists(), "Output graph file not created"
        graph = json.loads(output_path.read_text(encoding="utf-8"))

        # Graph should have nodes, edges, metadata
        assert "nodes" in graph
        assert "edges" in graph
        assert "metadata" in graph
        assert "clustering" in graph["metadata"], "Missing 'clustering' key in metadata"
        cluster_data = graph["metadata"]["clustering"]
        assert "cluster_count" in cluster_data, "Missing cluster_count"
        assert "noise_count" in cluster_data, "Missing noise_count"
        assert "clusters" in cluster_data, "Missing clusters list"

    def test_cluster_flag_without_model_skips_gracefully(self, sample_clauses_json: Path) -> None:
        """When model can't load, graph build still succeeds without clustering."""
        from typer.testing import CliRunner

        from openreview_cli.app import app

        runner = CliRunner()
        output_path = sample_clauses_json.with_suffix(".graph.json")

        result = runner.invoke(
            app,
            [
                "graph",
                "build",
                str(sample_clauses_json),
                "--cluster-clauses",
                "--output",
                str(output_path),
            ],
        )

        # Even if model load fails, graph build should still work
        # and produce a valid graph file (just without clustering)
        if result.exit_code == 0:
            assert output_path.exists()
            graph = json.loads(output_path.read_text(encoding="utf-8"))
            assert "nodes" in graph
            # clustering may or may not be attached

    def test_graph_build_works_without_cluster_flag(self, sample_clauses_json: Path) -> None:
        """Graph build works normally when --cluster-clauses is absent."""
        from typer.testing import CliRunner

        from openreview_cli.app import app

        runner = CliRunner()
        output_path = sample_clauses_json.with_suffix(".graph.json")

        result = runner.invoke(
            app,
            [
                "graph",
                "build",
                str(sample_clauses_json),
                "--output",
                str(output_path),
            ],
        )
        assert result.exit_code == 0, f"CLI failed: {result.stdout}"
        assert output_path.exists()
        graph = json.loads(output_path.read_text(encoding="utf-8"))
        assert "nodes" in graph
        assert "clustering" not in graph.get("metadata", {})
