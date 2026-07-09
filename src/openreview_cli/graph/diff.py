from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openreview_cli.graph.models import ContractGraph, GraphEdge, GraphNode


@dataclass
class GraphDiff:
    added_nodes: list[GraphNode] = field(default_factory=list)
    removed_nodes: list[GraphNode] = field(default_factory=list)
    added_edges: list[GraphEdge] = field(default_factory=list)
    removed_edges: list[GraphEdge] = field(default_factory=list)
    relabeled_nodes: list[tuple[GraphNode, GraphNode]] = field(default_factory=list)


def compute_graph_diff(g1: ContractGraph, g2: ContractGraph) -> GraphDiff:
    """Compare two ContractGraphs and return a GraphDiff.

    Comparison is by node ID, then label, then edges.
    """
    diff = GraphDiff()
    g1_ids = set(g1.nodes)
    g2_ids = set(g2.nodes)

    added_ids = g2_ids - g1_ids
    removed_ids = g1_ids - g2_ids
    common_ids = g1_ids & g2_ids

    diff.added_nodes = [g2.nodes[nid] for nid in sorted(added_ids)]
    diff.removed_nodes = [g1.nodes[nid] for nid in sorted(removed_ids)]

    # Relabeled nodes: same ID, different label
    for nid in sorted(common_ids):
        if g1.nodes[nid].label != g2.nodes[nid].label:
            diff.relabeled_nodes.append((g1.nodes[nid], g2.nodes[nid]))

    # Edge comparison
    def _edge_key(e: GraphEdge) -> tuple[str, str, str]:
        return (e.source_id, e.target_id, e.edge_type.value)

    g1_edge_map = {_edge_key(e): e for e in g1.edges}
    g2_edge_map = {_edge_key(e): e for e in g2.edges}
    g1_keys = set(g1_edge_map)
    g2_keys = set(g2_edge_map)

    diff.added_edges = [g2_edge_map[k] for k in sorted(g2_keys - g1_keys)]
    diff.removed_edges = [g1_edge_map[k] for k in sorted(g1_keys - g2_keys)]

    return diff
