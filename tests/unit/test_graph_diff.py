from __future__ import annotations

from openreview_cli.graph.diff import GraphDiff, compute_graph_diff
from openreview_cli.graph.models import ContractGraph, EdgeType, GraphEdge, GraphNode


def _make_graph(
    node_ids: list[str],
    labels: dict[str, str] | None = None,
    edges: list[tuple[str, str, str]] | None = None,
) -> ContractGraph:
    nodes: dict[str, GraphNode] = {}
    for nid in node_ids:
        label = (labels or {}).get(nid, nid)
        nodes[nid] = GraphNode(id=nid, label=label, text=f"Text for {nid}", level=0)
    edge_list: list[GraphEdge] = []
    for src, tgt, etype in edges or []:
        edge_list.append(GraphEdge(source_id=src, target_id=tgt, edge_type=EdgeType(etype)))
    return ContractGraph(nodes=nodes, edges=edge_list)


class TestComputeGraphDiff:
    def test_identical_graphs(self) -> None:
        g = _make_graph(["1", "2"], edges=[("1", "2", "parent_child")])
        diff = compute_graph_diff(g, g)
        assert diff.added_nodes == []
        assert diff.removed_nodes == []
        assert diff.added_edges == []
        assert diff.removed_edges == []
        assert diff.relabeled_nodes == []

    def test_added_nodes(self) -> None:
        g1 = _make_graph(["1", "2"])
        g2 = _make_graph(["1", "2", "3"])
        diff = compute_graph_diff(g1, g2)
        assert [n.id for n in diff.added_nodes] == ["3"]
        assert diff.removed_nodes == []

    def test_removed_nodes(self) -> None:
        g1 = _make_graph(["1", "2", "3"])
        g2 = _make_graph(["1", "2"])
        diff = compute_graph_diff(g1, g2)
        assert [n.id for n in diff.removed_nodes] == ["3"]
        assert diff.added_nodes == []

    def test_added_and_removed_nodes(self) -> None:
        g1 = _make_graph(["1", "2", "3"])
        g2 = _make_graph(["1", "2", "4"])
        diff = compute_graph_diff(g1, g2)
        assert [n.id for n in diff.added_nodes] == ["4"]
        assert [n.id for n in diff.removed_nodes] == ["3"]

    def test_relabeled_nodes(self) -> None:
        g1 = _make_graph(["1", "2"], labels={"1": "Old Label"})
        g2 = _make_graph(["1", "2"], labels={"1": "New Label"})
        diff = compute_graph_diff(g1, g2)
        assert len(diff.relabeled_nodes) == 1
        old, new = diff.relabeled_nodes[0]
        assert old.label == "Old Label"
        assert new.label == "New Label"

    def test_added_edges(self) -> None:
        g1 = _make_graph(["1", "2"])
        g2 = _make_graph(["1", "2"], edges=[("1", "2", "parent_child")])
        diff = compute_graph_diff(g1, g2)
        assert len(diff.added_edges) == 1
        assert diff.added_edges[0].source_id == "1"
        assert diff.added_edges[0].target_id == "2"

    def test_removed_edges(self) -> None:
        g1 = _make_graph(["1", "2"], edges=[("1", "2", "parent_child")])
        g2 = _make_graph(["1", "2"])
        diff = compute_graph_diff(g1, g2)
        assert len(diff.removed_edges) == 1
        assert diff.removed_edges[0].source_id == "1"

    def test_mixed_changes(self) -> None:
        g1 = _make_graph(
            ["1", "2", "3"],
            labels={"1": "A", "2": "B"},
            edges=[("1", "2", "parent_child"), ("2", "3", "parent_child")],
        )
        g2 = _make_graph(
            ["1", "2", "4"],
            labels={"1": "A", "2": "B Renamed"},
            edges=[("1", "2", "parent_child"), ("2", "4", "parent_child")],
        )
        diff = compute_graph_diff(g1, g2)
        assert [n.id for n in diff.added_nodes] == ["4"]
        assert [n.id for n in diff.removed_nodes] == ["3"]
        assert len(diff.relabeled_nodes) == 1
        assert diff.relabeled_nodes[0][1].label == "B Renamed"
        assert len(diff.added_edges) == 1
        assert diff.added_edges[0].target_id == "4"
        assert len(diff.removed_edges) == 1
        assert diff.removed_edges[0].target_id == "3"

    def test_graph_diff_dataclass_repr(self) -> None:
        diff = GraphDiff()
        assert diff.added_nodes == []
        assert diff.removed_nodes == []
        assert diff.added_edges == []
        assert diff.removed_edges == []
        assert diff.relabeled_nodes == []
