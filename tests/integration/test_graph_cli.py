from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from openreview_cli.app import app
from openreview_cli.graph.models import ContractGraph, EdgeType, GraphEdge, GraphNode
from openreview_cli.storage.database import init_database
from openreview_cli.storage.graphs import save_graph

runner = CliRunner()


def _write_graph_json(path: Path, graph: ContractGraph) -> None:
    path.write_text(graph.to_json(), encoding="utf-8")


def _write_parsed_json(path: Path) -> None:
    """Write a minimal parsed contract JSON for graph build."""
    clauses = [
        {
            "id": "1",
            "title": "Preamble",
            "text": "This agreement is made...",
            "level": 0,
            "parent_id": None,
        },
        {
            "id": "2",
            "title": "Definitions",
            "text": "Capitalized terms...",
            "level": 1,
            "parent_id": "1",
        },
        {
            "id": "3",
            "title": "Term",
            "text": "This Agreement shall commence...",
            "level": 2,
            "parent_id": "2",
        },
    ]
    path.write_text(json.dumps(clauses), encoding="utf-8")


def _sample_graph_a() -> ContractGraph:
    nodes: dict[str, GraphNode] = {
        "1": GraphNode(id="1", label="Preamble", text="...", level=0),
        "2": GraphNode(id="2", label="Definitions", text="...", level=1),
        "3": GraphNode(id="3", label="Term", text="Term text", level=2),
    }
    edges = [
        GraphEdge(source_id="1", target_id="2", edge_type=EdgeType.parent_child),
        GraphEdge(source_id="2", target_id="3", edge_type=EdgeType.parent_child),
    ]
    return ContractGraph(nodes=nodes, edges=edges)


def _sample_graph_b() -> ContractGraph:
    nodes: dict[str, GraphNode] = {
        "1": GraphNode(id="1", label="Preamble", text="...", level=0),
        "2": GraphNode(id="2", label="Definitions", text="...", level=1),
        "4": GraphNode(id="4", label="New Clause", text="new", level=2),
    }
    edges = [
        GraphEdge(source_id="1", target_id="2", edge_type=EdgeType.parent_child),
        GraphEdge(source_id="2", target_id="4", edge_type=EdgeType.parent_child),
    ]
    return ContractGraph(nodes=nodes, edges=edges)


class TestGraphDiffCli:
    def test_diff_human_readable(self, tmp_path: Path) -> None:
        fa = tmp_path / "a.graph.json"
        fb = tmp_path / "b.graph.json"
        _write_graph_json(fa, _sample_graph_a())
        _write_graph_json(fb, _sample_graph_b())
        result = runner.invoke(app, ["graph", "diff", str(fa), str(fb)])
        assert result.exit_code == 0
        assert "added" in result.stdout.lower() or "removed" in result.stdout.lower()
        assert "New Clause" in result.stdout

    def test_diff_json(self, tmp_path: Path) -> None:
        fa = tmp_path / "a.graph.json"
        fb = tmp_path / "b.graph.json"
        _write_graph_json(fa, _sample_graph_a())
        _write_graph_json(fb, _sample_graph_b())
        result = runner.invoke(app, ["graph", "diff", str(fa), str(fb), "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "added_nodes" in data
        assert "removed_nodes" in data
        assert "added_edges" in data
        assert "removed_edges" in data

    def test_diff_identical(self, tmp_path: Path) -> None:
        fa = tmp_path / "a.graph.json"
        fb = tmp_path / "b.graph.json"
        _write_graph_json(fa, _sample_graph_a())
        _write_graph_json(fb, _sample_graph_a())
        result = runner.invoke(app, ["graph", "diff", str(fa), str(fb)])
        assert result.exit_code == 0
        assert "No differences" in result.stdout

    def test_diff_missing_file(self, tmp_path: Path) -> None:
        result = runner.invoke(
            app, ["graph", "diff", str(tmp_path / "nonexistent.json"), str(tmp_path / "x.json")]
        )
        assert result.exit_code == 1


class TestGraphStoreCli:
    def test_build_with_store(self, tmp_path: Path) -> None:
        parsed_path = tmp_path / "simple-contract.json"
        _write_parsed_json(parsed_path)
        db_path = tmp_path / "test.db"
        init_database(db_path)

        result = runner.invoke(
            app,
            [
                "graph",
                "build",
                str(parsed_path),
                "--store",
                "--contract-id",
                "test-contract",
                "--db-path",
                str(db_path),
            ],
        )
        assert result.exit_code == 0

        from openreview_cli.storage.graphs import load_graph as _load_graph

        loaded = _load_graph(db_path, "test-contract")
        assert loaded is not None
        assert len(loaded.nodes) > 0

    def test_build_with_store_no_contract_id(self, tmp_path: Path) -> None:
        parsed_path = tmp_path / "simple-contract.json"
        _write_parsed_json(parsed_path)
        db_path = tmp_path / "test.db"
        init_database(db_path)

        result = runner.invoke(
            app,
            [
                "graph",
                "build",
                str(parsed_path),
                "--store",
                "--db-path",
                str(db_path),
            ],
        )
        assert result.exit_code == 0

        from openreview_cli.storage.graphs import load_graph as _load_graph

        loaded = _load_graph(db_path, "simple-contract")
        assert loaded is not None

    def test_view_from_db(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        init_database(db_path)
        save_graph(db_path, "v-contract", _sample_graph_a())

        view_result = runner.invoke(
            app,
            [
                "graph",
                "view",
                "--from-db",
                "--contract-id",
                "v-contract",
                "--db-path",
                str(db_path),
            ],
        )
        assert view_result.exit_code == 0
        assert "Preamble" in view_result.stdout

    def test_metrics_from_db(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        init_database(db_path)
        save_graph(db_path, "m-contract", _sample_graph_a())

        result = runner.invoke(
            app,
            [
                "graph",
                "metrics",
                "--from-db",
                "--contract-id",
                "m-contract",
                "--db-path",
                str(db_path),
            ],
        )
        assert result.exit_code == 0
        assert "Density" in result.stdout

    def test_health_from_db(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        init_database(db_path)
        save_graph(db_path, "h-contract", _sample_graph_a())

        result = runner.invoke(
            app,
            [
                "graph",
                "health",
                "--from-db",
                "--contract-id",
                "h-contract",
                "--db-path",
                str(db_path),
            ],
        )
        assert result.exit_code == 0
        assert "Health Score" in result.stdout

    def test_graph_view_rejects_both_file_and_db(self, tmp_path: Path) -> None:
        fa = tmp_path / "a.graph.json"
        _write_graph_json(fa, _sample_graph_a())
        result = runner.invoke(
            app,
            [
                "graph",
                "view",
                str(fa),
                "--from-db",
                "--contract-id",
                "x",
                "--db-path",
                str(tmp_path / "x.db"),
            ],
        )
        assert result.exit_code != 0
