from __future__ import annotations

from openreview_cli.graph.models import ContractGraph, EdgeType, GraphEdge, GraphNode
from openreview_cli.graph.view import render_tree


def _simple_hierarchy() -> ContractGraph:
    return ContractGraph(
        nodes={
            "c1": GraphNode("c1", "Article 1", "Article 1 text", 0),
            "c2": GraphNode("c2", "Section 1.1", "Section 1.1 text", 1),
        },
        edges=[GraphEdge("c1", "c2", EdgeType.parent_child)],
    )


class TestRenderTree:
    def test_indentation_roots_at_zero(self) -> None:
        graph = _simple_hierarchy()
        output = render_tree(graph)
        lines = output.split("\n")
        assert len(lines) >= 2
        assert not lines[0].startswith("  ")
        assert lines[1].startswith("  ")

    def test_cross_ref_annotation(self) -> None:
        graph = ContractGraph(
            nodes={
                "c1": GraphNode("c1", "Article 1", "Article text", 0),
                "c2": GraphNode("c2", "Section 1.1", "Section text", 1),
            },
            edges=[
                GraphEdge("c1", "c2", EdgeType.parent_child),
                GraphEdge("c1", "c2", EdgeType.cross_ref),
            ],
        )
        output = render_tree(graph)
        assert "[1 refs out]" in output

    def test_def_ref_annotation(self) -> None:
        graph = ContractGraph(
            nodes={
                "c1": GraphNode("c1", "Article 1", "defines terms", 0),
                "c2": GraphNode("c2", "Section 1.1", "uses terms", 1),
            },
            edges=[
                GraphEdge("c1", "c2", EdgeType.parent_child),
                GraphEdge("c2", "c1", EdgeType.def_ref, {"term": "Confidential"}),
            ],
        )
        output = render_tree(graph)
        assert "[DEF-REF: 1]" in output

    def test_defines_annotation(self) -> None:
        graph = ContractGraph(
            nodes={
                "c1": GraphNode("c1", "Article 1", "defines terms", 0),
                "c2": GraphNode("c2", "Section 1.1", "uses terms", 1),
            },
            edges=[
                GraphEdge("c2", "c1", EdgeType.def_ref, {"term": "Confidential"}),
            ],
        )
        output = render_tree(graph)
        assert '[DEFINES: "Confidential"]' in output

    def test_orphan_marking(self) -> None:
        graph = ContractGraph(
            nodes={
                "c1": GraphNode("c1", "Article 1", "Article text", 0),
                "c2": GraphNode("c2", "Section 1.1", "Section text", 1),
            },
            edges=[GraphEdge("c1", "c2", EdgeType.parent_child)],
        )
        output = render_tree(graph)
        assert "[ORPHAN]" in output

    def test_empty_graph_empty_output(self) -> None:
        graph = ContractGraph()
        output = render_tree(graph)
        assert output == ""

    def test_single_node_single_line(self) -> None:
        graph = ContractGraph(
            nodes={"c1": GraphNode("c1", "Article 1", "Article text", 0)},
            edges=[],
        )
        output = render_tree(graph)
        assert len(output.split("\n")) == 1
        assert "Article 1" in output
