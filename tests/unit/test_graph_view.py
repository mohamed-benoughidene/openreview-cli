from __future__ import annotations

from openreview_cli.graph.models import ContractGraph, EdgeType, GraphEdge, GraphNode
from openreview_cli.graph.view import compute_annotations, render_tree


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
                "c2": GraphNode("c2", "Section 1.1", "Section text", 1, parent_id="missing"),
            },
            edges=[GraphEdge("c1", "c2", EdgeType.parent_child)],
        )
        output = render_tree(graph)
        assert "[ORPHAN]" in output

    def test_cross_ref_to_a_missing_section_does_not_crash(self) -> None:
        """A cross_ref edge whose target is not a node renders without raising."""
        graph = ContractGraph(
            nodes={"c1": GraphNode("c1", "Article 1", "See Section 9.9.", 0)},
            edges=[GraphEdge("c1", "missing-section-9.9", EdgeType.cross_ref)],
        )
        output = render_tree(graph)
        assert "[1 refs out]" in output

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


class TestComputeAnnotations:
    """T2.2: the shared annotation helper behind both tree renderers."""

    def test_outgoing_cross_reference(self) -> None:
        graph = ContractGraph(
            nodes={"c1": GraphNode("c1", "Article 1", "See Section 2.", 0)},
            edges=[GraphEdge("c1", "c2", EdgeType.cross_ref)],
        )
        assert compute_annotations(graph) == {"c1": ["[1 refs out]"]}

    def test_cross_reference_count_accumulates(self) -> None:
        graph = ContractGraph(
            nodes={"c1": GraphNode("c1", "Article 1", "See Sections 2 and 3.", 0)},
            edges=[
                GraphEdge("c1", "c2", EdgeType.cross_ref),
                GraphEdge("c1", "c3", EdgeType.cross_ref),
            ],
        )
        assert compute_annotations(graph) == {"c1": ["[2 refs out]"]}

    def test_definition_reference_count(self) -> None:
        graph = ContractGraph(
            nodes={"c1": GraphNode("c1", "Article 1", "uses terms", 0)},
            edges=[GraphEdge("c1", "c2", EdgeType.def_ref, {"term": "Confidential"})],
        )
        assert compute_annotations(graph) == {"c1": ["[DEF-REF: 1]"]}

    def test_node_that_defines_a_term(self) -> None:
        graph = ContractGraph(
            nodes={
                "c1": GraphNode("c1", "Article 1", "defines terms", 0),
                "c2": GraphNode("c2", "Section 1.1", "uses terms", 1),
            },
            edges=[GraphEdge("c2", "c1", EdgeType.def_ref, {"term": "Confidential"})],
        )
        assert compute_annotations(graph) == {
            "c1": ['[DEFINES: "Confidential"]'],
            "c2": ["[DEF-REF: 1]"],
        }

    def test_orphan_node(self) -> None:
        graph = ContractGraph(
            nodes={
                "c1": GraphNode("c1", "Article 1", "Article text", 0),
                "c2": GraphNode("c2", "Section 1.1", "Section text", 1, parent_id="missing"),
            },
        )
        assert compute_annotations(graph) == {"c2": ["[ORPHAN]"]}

    def test_unannotated_nodes_are_absent(self) -> None:
        assert compute_annotations(_simple_hierarchy()) == {}

    def test_annotation_order_matches_render_tree(self) -> None:
        graph = ContractGraph(
            nodes={
                "c1": GraphNode("c1", "Article 1", "defines terms", 0),
                "c2": GraphNode("c2", "Section 1.1", "uses terms", 1),
            },
            edges=[
                GraphEdge("c1", "c2", EdgeType.cross_ref),
                GraphEdge("c2", "c1", EdgeType.def_ref, {"term": "Confidential"}),
            ],
        )
        assert compute_annotations(graph) == {
            "c1": ["[1 refs out]", '[DEFINES: "Confidential"]'],
            "c2": ["[DEF-REF: 1]"],
        }

    def test_render_tree_output_is_pinned(self) -> None:
        """Characterisation pin: the extraction must not shift CLI output."""
        graph = ContractGraph(
            nodes={
                "c1": GraphNode("c1", "Article 1", "Definitions and terms", 0),
                "c2": GraphNode("c2", "Section 1.1", "See Section 2.", 1),
                "c3": GraphNode("c3", "Section 1.2", "orphan text", 1, parent_id="missing"),
            },
            edges=[
                GraphEdge("c1", "c2", EdgeType.parent_child),
                GraphEdge("c1", "c3", EdgeType.parent_child),
                GraphEdge("c2", "c9", EdgeType.cross_ref),
                GraphEdge("c2", "c1", EdgeType.def_ref, {"term": "Confidential"}),
            ],
        )
        assert render_tree(graph) == (
            'Article 1  Definitions and terms  [DEFINES: "Confidential"]\n'
            "  Section 1.1  See Section 2.  [1 refs out] [DEF-REF: 1]\n"
            "  Section 1.2  orphan text  [ORPHAN]"
        )
