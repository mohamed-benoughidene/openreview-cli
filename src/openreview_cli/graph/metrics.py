from __future__ import annotations

from dataclasses import dataclass

from openreview_cli.graph.models import ContractGraph, EdgeType


@dataclass
class GraphMetrics:
    """Five heuristic structural metrics for a contract graph.

    All metrics are computed without ML — pure graph analysis.
    """

    density: float = 0.0
    max_depth: int = 0
    orphan_ratio: float = 0.0
    broken_ref_count: int = 0
    definition_coverage: float = 1.0


def compute_density(graph: ContractGraph) -> float:
    """Ratio of actual edges to possible edges in the directed graph.

    density = edge_count / (node_count * (node_count - 1))
    Returns 0.0 for 0 or 1 nodes.
    """
    n = len(graph.nodes)
    if n <= 1:
        return 0.0
    return len(graph.edges) / (n * (n - 1))


def compute_max_depth(graph: ContractGraph) -> int:
    """Longest path from root to leaf following only parent_child edges."""
    if not graph.nodes:
        return 0

    # Build parent-child adjacency
    children: dict[str, list[str]] = {}
    for edge in graph.edges:
        if edge.edge_type == EdgeType.parent_child:
            children.setdefault(edge.source_id, []).append(edge.target_id)

    memo: dict[str, int] = {}

    def _depth(node_id: str) -> int:
        if node_id in memo:
            return memo[node_id]
        kids = children.get(node_id, [])
        if not kids:
            memo[node_id] = 1
            return 1
        max_child = max(_depth(k) for k in kids)
        memo[node_id] = max_child + 1
        return memo[node_id]

    max_d = 0
    for root in graph.roots:
        d = _depth(root)
        max_d = max(max_d, d)
    return max_d


def compute_orphan_ratio(graph: ContractGraph) -> float:
    """Fraction of nodes with no incoming parent_child edge but with children.

    Standalone nodes (no parent, no children) are not orphaned.
    """
    if len(graph.nodes) == 0:
        return 0.0
    return len(graph.orphan_ids) / len(graph.nodes)


def compute_broken_ref_count(graph: ContractGraph) -> int:
    """Count cross-ref edges where the target node does not exist."""
    broken = 0
    for edge in graph.edges:
        if edge.edge_type == EdgeType.cross_ref and edge.target_id not in graph.nodes:
            broken += 1
    return broken


def compute_definition_coverage(graph: ContractGraph) -> float:
    """Ratio of referenced terms that have a corresponding definition node.

    1.0 = every referenced term is defined somewhere.
    1.0 if no terms are referenced (trivially perfect).
    """
    referenced_terms: set[str] = set()
    defined_terms: set[str] = set()

    for edge in graph.edges:
        if edge.edge_type == EdgeType.def_ref:
            term = edge.metadata.get("term", "")
            if term:
                referenced_terms.add(term)
                if edge.target_id in graph.nodes:
                    defined_terms.add(term)

    if not referenced_terms:
        return 1.0
    return len(defined_terms & referenced_terms) / len(referenced_terms)


def compute_metrics(graph: ContractGraph) -> GraphMetrics:
    """Compute all five heuristic metrics from a ContractGraph."""
    return GraphMetrics(
        density=compute_density(graph),
        max_depth=compute_max_depth(graph),
        orphan_ratio=compute_orphan_ratio(graph),
        broken_ref_count=compute_broken_ref_count(graph),
        definition_coverage=compute_definition_coverage(graph),
    )


__all__ = [
    "GraphMetrics",
    "compute_metrics",
]
