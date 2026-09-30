from __future__ import annotations

from openreview_cli.graph.models import ContractGraph, EdgeType


def compute_annotations(graph: ContractGraph) -> dict[str, list[str]]:
    """Return the tree annotations for every annotated node, keyed by node id.

    The annotation vocabulary, in the order it is rendered:

    - Outgoing cross-reference count: ``[N refs out]``
    - Definition usage count: ``[DEF-REF: N]``
    - Definition node: ``[DEFINES: "term"]``
    - Orphan status: ``[ORPHAN]``

    Nodes with no annotations are absent from the mapping. This is the single
    source of truth shared by the CLI text renderer (:func:`render_tree`) and
    the TUI tree screen, so the two cannot drift apart.
    """
    ref_counts: dict[str, int] = {}
    def_ref_counts: dict[str, int] = {}
    defines_terms: dict[str, list[str]] = {}

    for edge in graph.edges:
        if edge.edge_type == EdgeType.cross_ref:
            ref_counts[edge.source_id] = ref_counts.get(edge.source_id, 0) + 1
        elif edge.edge_type == EdgeType.def_ref:
            def_ref_counts[edge.source_id] = def_ref_counts.get(edge.source_id, 0) + 1
            term = edge.metadata.get("term", "")
            if term:
                defines_terms.setdefault(edge.target_id, []).append(term)

    orphan_ids = set(graph.orphan_ids)
    annotations: dict[str, list[str]] = {}

    for node_id in graph.nodes:
        node_annotations: list[str] = []

        n_refs = ref_counts.get(node_id, 0)
        if n_refs > 0:
            node_annotations.append(f"[{n_refs} refs out]")

        n_def_refs = def_ref_counts.get(node_id, 0)
        if n_def_refs > 0:
            node_annotations.append(f"[DEF-REF: {n_def_refs}]")

        for term in defines_terms.get(node_id, []):
            node_annotations.append(f'[DEFINES: "{term}"]')

        if node_id in orphan_ids:
            node_annotations.append("[ORPHAN]")

        if node_annotations:
            annotations[node_id] = node_annotations

    return annotations


def render_tree(graph: ContractGraph) -> str:
    """Render clause hierarchy as an indented ASCII text tree.

    Each node is annotated from :func:`compute_annotations` with:

    - Outgoing cross-reference count: ``[N refs out]``
    - Definition usage count: ``[DEF-REF: N]``
    - Definition node: ``[DEFINES: "term"]``
    - Orphan status: ``[ORPHAN]``

    Returns:
        Indented text tree string. Empty string for empty graph.
    """
    adjacency = graph.adjacency
    annotations_by_node = compute_annotations(graph)
    lines: list[str] = []

    def _render(node_id: str, depth: int, visited: set[str]) -> None:
        if node_id in visited:
            return
        visited.add(node_id)
        node = graph.nodes.get(node_id)
        if not node:
            return

        indent = "  " * depth
        text_snippet = node.text[:60].replace("\n", " ").strip()
        parts: list[str] = [f"{indent}{node.label}  {text_snippet}"]

        annotations = annotations_by_node.get(node_id, [])
        if annotations:
            parts.append("  " + " ".join(annotations))

        line = "".join(parts)
        lines.append(line)

        # Render children following parent_child edges
        for edge in adjacency.get(node_id, []):
            if edge.edge_type == EdgeType.parent_child:
                _render(edge.target_id, depth + 1, visited)

    visited: set[str] = set()
    for root in graph.roots:
        _render(root, 0, visited)

    return "\n".join(lines)


__all__ = ["compute_annotations", "render_tree"]
