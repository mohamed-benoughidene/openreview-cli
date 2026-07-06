from __future__ import annotations

from pathlib import Path

import pytest

from openreview_cli.graph.models import (
    ContractGraph,
    EdgeType,
    GraphEdge,
    GraphNode,
)


class TestGraphNode:
    def test_creates_with_valid_fields(self) -> None:
        node = GraphNode(id="clause-1", label="Section 1", text="Some text", level=0)
        assert node.id == "clause-1"
        assert node.label == "Section 1"
        assert node.text == "Some text"
        assert node.level == 0
        assert node.metadata == {}

    def test_creates_with_metadata(self) -> None:
        node = GraphNode(
            id="clause-1",
            label="Section 1",
            text="Text",
            level=0,
            metadata={"source_page": 1},
        )
        assert node.metadata == {"source_page": 1}


class TestEdgeType:
    def test_enum_values(self) -> None:
        assert EdgeType.parent_child.value == "parent_child"
        assert EdgeType.cross_ref.value == "cross_ref"
        assert EdgeType.def_ref.value == "def_ref"


class TestGraphEdge:
    def test_creates_with_source_target_type(self) -> None:
        edge = GraphEdge(
            source_id="clause-1",
            target_id="clause-2",
            edge_type=EdgeType.parent_child,
        )
        assert edge.source_id == "clause-1"
        assert edge.target_id == "clause-2"
        assert edge.edge_type == EdgeType.parent_child

    def test_creates_with_metadata(self) -> None:
        edge = GraphEdge(
            source_id="c1",
            target_id="c2",
            edge_type=EdgeType.cross_ref,
            metadata={"pattern_matched": "Section"},
        )
        assert edge.metadata == {"pattern_matched": "Section"}


class TestContractGraph:
    def test_adjacency_property(self) -> None:
        graph = ContractGraph(
            nodes={
                "c1": GraphNode(id="c1", label="1", text="t", level=0),
                "c2": GraphNode(id="c2", label="2", text="t", level=1),
            },
            edges=[GraphEdge("c1", "c2", EdgeType.parent_child)],
        )
        adj = graph.adjacency
        assert "c1" in adj
        assert len(adj["c1"]) == 1
        assert adj["c1"][0].target_id == "c2"

    def test_roots_no_parent_edges(self) -> None:
        graph = ContractGraph(
            nodes={
                "c1": GraphNode("c1", "1", "t", 0),
                "c2": GraphNode("c2", "2", "t", 1),
            },
            edges=[GraphEdge("c1", "c2", EdgeType.parent_child)],
        )
        assert graph.roots == ["c1"]

    def test_roots_node_without_parent_edge(self) -> None:
        graph = ContractGraph(
            nodes={
                "c1": GraphNode("c1", "1", "t", 0),
                "c2": GraphNode("c2", "2", "t", 1),
            },
            edges=[],
        )
        assert sorted(graph.roots) == ["c1", "c2"]

    def test_orphan_ids_root_with_children_is_orphan(self) -> None:
        """Root with children but no parent is orphaned per spec."""
        graph = ContractGraph(
            nodes={
                "c1": GraphNode("c1", "1", "t", 0),
                "c2": GraphNode("c2", "2", "t", 1),
            },
            edges=[GraphEdge("c1", "c2", EdgeType.parent_child)],
        )
        # c1 has no incoming parent_child edge but has outgoing → orphan
        assert graph.orphan_ids == ["c1"]

    def test_orphan_ids_detects_orphans(self) -> None:
        graph = ContractGraph(
            nodes={
                "c1": GraphNode("c1", "1", "t", 0),
                "c2": GraphNode("c2", "2", "t", 1),
                "c3": GraphNode("c3", "3", "t", 2),
                "c4": GraphNode("c4", "4", "t", 2),
            },
            edges=[
                GraphEdge("c1", "c2", EdgeType.parent_child),
                GraphEdge("c3", "c4", EdgeType.parent_child),
            ],
        )
        assert "c3" in graph.orphan_ids
        assert "c2" not in graph.orphan_ids

    def test_json_round_trip(self) -> None:
        original = ContractGraph(
            nodes={
                "c1": GraphNode("c1", "1", "text1", 0),
                "c2": GraphNode("c2", "2", "text2", 1),
            },
            edges=[
                GraphEdge("c1", "c2", EdgeType.parent_child),
                GraphEdge("c2", "c1", EdgeType.cross_ref, {"pattern_matched": "test"}),
            ],
            metadata={"version": "1.0"},
        )
        json_str = original.to_json()
        restored = ContractGraph.from_json(json_str)
        assert len(restored.nodes) == 2
        assert restored.nodes["c1"].label == "1"
        assert len(restored.edges) == 2
        assert restored.edges[0].edge_type == EdgeType.parent_child
        assert restored.edges[1].metadata == {"pattern_matched": "test"}
        assert restored.metadata == {"version": "1.0"}

    def test_empty_graph(self) -> None:
        graph = ContractGraph()
        assert len(graph.nodes) == 0
        assert len(graph.edges) == 0
        assert graph.roots == []
        assert graph.orphan_ids == []

    def test_single_node(self) -> None:
        graph = ContractGraph(nodes={"c1": GraphNode("c1", "1", "text", 0)})
        assert len(graph.nodes) == 1
        assert len(graph.edges) == 0
        assert graph.roots == ["c1"]
        assert graph.orphan_ids == []

    def test_self_referencing_edge_stored(self) -> None:
        graph = ContractGraph(
            nodes={"c1": GraphNode("c1", "1", "text", 0)},
            edges=[GraphEdge("c1", "c1", EdgeType.cross_ref)],
        )
        assert len(graph.edges) == 1

    def test_to_file_from_file(self, tmp_path: Path) -> None:
        original = ContractGraph(
            nodes={"c1": GraphNode("c1", "1", "text", 0)},
            edges=[],
        )
        file_path = tmp_path / "graph.json"
        original.to_file(str(file_path))

        restored = ContractGraph.from_file(str(file_path))
        assert restored.nodes["c1"].id == "c1"
        assert len(restored.edges) == 0

    def test_from_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            ContractGraph.from_file("/nonexistent/path.json")
