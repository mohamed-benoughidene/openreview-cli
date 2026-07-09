from __future__ import annotations

from pathlib import Path

from openreview_cli.graph.models import ContractGraph, EdgeType, GraphEdge, GraphNode
from openreview_cli.storage.database import init_database, load_graph, save_graph


def _sample_graph() -> ContractGraph:
    nodes: dict[str, GraphNode] = {
        "1": GraphNode(id="1", label="Preamble", text="...", level=0),
        "2": GraphNode(id="2", label="Definitions", text="...", level=1),
        "3": GraphNode(id="3", label="Term", text="...", level=2),
    }
    edges = [
        GraphEdge(source_id="1", target_id="2", edge_type=EdgeType.parent_child),
        GraphEdge(source_id="2", target_id="3", edge_type=EdgeType.parent_child),
    ]
    return ContractGraph(nodes=nodes, edges=edges, metadata={"source": "test"})


class TestSaveLoadGraph:
    def test_save_and_load_round_trip(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        init_database(db_path)
        graph = _sample_graph()
        save_graph(db_path, "test-contract", graph)
        loaded = load_graph(db_path, "test-contract")
        assert loaded is not None
        assert len(loaded.nodes) == 3
        assert loaded.nodes["1"].label == "Preamble"
        assert loaded.nodes["2"].label == "Definitions"
        assert len(loaded.edges) == 2
        assert loaded.metadata.get("source") == "test"

    def test_load_missing_contract(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        init_database(db_path)
        loaded = load_graph(db_path, "nonexistent")
        assert loaded is None

    def test_save_multiple_contracts(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        init_database(db_path)
        g1 = _sample_graph()
        g2 = _sample_graph()
        g2.nodes["1"].label = "Modified Preamble"
        save_graph(db_path, "contract-a", g1)
        save_graph(db_path, "contract-b", g2)
        loaded_a = load_graph(db_path, "contract-a")
        loaded_b = load_graph(db_path, "contract-b")
        assert loaded_a is not None
        assert loaded_b is not None
        assert loaded_a.nodes["1"].label == "Preamble"
        assert loaded_b.nodes["1"].label == "Modified Preamble"

    def test_save_overwrites_existing(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        init_database(db_path)
        g1 = _sample_graph()
        save_graph(db_path, "c1", g1)
        g2 = _sample_graph()
        g2.nodes["1"].label = "Updated"
        save_graph(db_path, "c1", g2)
        loaded = load_graph(db_path, "c1")
        assert loaded is not None
        assert loaded.nodes["1"].label == "Updated"
        assert len(loaded.nodes) == 3

    def test_node_position_and_metadata(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        init_database(db_path)
        node = GraphNode(
            id="x1",
            label="Custom",
            text="...",
            level=0,
            metadata={"key": "value", "num": 42},
        )
        graph = ContractGraph(
            nodes={"x1": node},
            edges=[],
            metadata={},
        )
        save_graph(db_path, "c1", graph)
        loaded = load_graph(db_path, "c1")
        assert loaded is not None
        assert loaded.nodes["x1"].metadata.get("key") == "value"
        assert loaded.nodes["x1"].metadata.get("num") == 42

    def test_contract_graph_save_to_db(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        init_database(db_path)
        graph = _sample_graph()
        graph.save_to_db(str(db_path), "contract-x")
        loaded = ContractGraph.load_from_db(str(db_path), "contract-x")
        assert loaded is not None
        assert len(loaded.nodes) == 3

    def test_contract_graph_load_from_db_missing(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        init_database(db_path)
        loaded = ContractGraph.load_from_db(str(db_path), "ghost")
        assert loaded is None

    def test_graph_with_no_edges(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        init_database(db_path)
        graph = ContractGraph(
            nodes={"n1": GraphNode(id="n1", label="Solo", text="...", level=0)},
            edges=[],
        )
        save_graph(db_path, "solo", graph)
        loaded = load_graph(db_path, "solo")
        assert loaded is not None
        assert len(loaded.nodes) == 1
        assert loaded.nodes["n1"].label == "Solo"
        assert len(loaded.edges) == 0
