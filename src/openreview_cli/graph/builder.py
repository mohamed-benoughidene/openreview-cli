from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from openreview_cli.graph.detectors import (
    CrossReferenceDetector,
    DefinitionDetector,
)
from openreview_cli.graph.models import (
    ContractGraph,
    EdgeType,
    GraphEdge,
    GraphNode,
)
from openreview_cli.parsing.models import Clause

# Numbering patterns for label extraction (matching data-model.md §5.1)
_LABEL_PATTERNS: list[tuple[str, int]] = [
    # Priority 1: ARTICLE/Article/SECTION/Section + Roman/Number → level 0
    (r"\b(?:ARTICLE|Article|SECTION|Section)\s+([A-Z0-9][A-Za-z0-9.]*)", 0),
    # Priority 2: Clause/clause + digit → level 0
    (r"\b(?:Clause|clause)\s+(\d+)", 0),
    # Priority 3: Digit-dotted → level 1
    (r"^(\d+\.\d+(?:\.\d+)*)\b", 1),
    # Priority 4: Section + digit.digit → level 1
    (r"\bSection\s+(\d+\.\d+)\b", 1),
    # Priority 5: Parenthesised letter → level 2
    (r"^\(([a-z])\)", 2),
    # Priority 6: Parenthesised digit → level 2
    (r"^\((\d+)\)", 2),
    # Priority 7: Parenthesised Roman → level 2
    (r"^\(([ivxlcdm]+)\)", 2),
]


def _extract_label_and_level(clause: Clause) -> tuple[str, int]:
    """Extract section label and derive level from numbering pattern.

    Uses clause title first, falls back to first line of clause text.
    Returns (label_string, derived_level).
    """
    text_source = (clause.title or "").strip() or clause.text.split("\n")[0].strip()
    for pattern_str, default_level in _LABEL_PATTERNS:
        m = re.search(pattern_str, text_source)
        if m:
            return m.group(0).strip(), default_level
    return f"Clause {clause.id}", 0


class ClauseHierarchyBuilder:
    """Build a ContractGraph from a list of Clause objects.

    Produces three types of edges:
    - parent_child: from Clause.parent_id
    - cross_ref: from regex detection in clause text
    - def_ref: from definition detection in clause text
    """

    def build(self, clauses: list[Clause]) -> ContractGraph:
        nodes: dict[str, GraphNode] = {}
        edges: list[GraphEdge] = []

        # Create nodes from clauses
        for clause in clauses:
            label, level = _extract_label_and_level(clause)
            node = GraphNode(
                id=clause.id,
                label=label,
                text=clause.text,
                level=level,
                metadata={
                    "source_page": clause.source_page,
                    "source_paragraph": clause.source_paragraph,
                    "paragraph_count": clause.paragraph_count,
                    "title": clause.title,
                },
            )
            nodes[clause.id] = node

        # Build parent-child edges from Clause.parent_id
        for clause in clauses:
            if clause.parent_id and clause.parent_id in nodes and clause.parent_id != clause.id:
                edges.append(
                    GraphEdge(
                        source_id=clause.parent_id,
                        target_id=clause.id,
                        edge_type=EdgeType.parent_child,
                    )
                )

        graph = ContractGraph(
            nodes=nodes,
            edges=edges,
            metadata={"clause_count": len(clauses)},
        )

        # Detect cross-references
        self._add_cross_ref_edges(graph, clauses)

        # Detect definition references
        self._add_def_ref_edges(graph, clauses)

        return graph

    def _add_cross_ref_edges(self, graph: ContractGraph, clauses: list[Clause]) -> None:
        """Scan clause text for cross-references and add edges."""
        detector = CrossReferenceDetector()

        # Build index mapping numeric suffixes extracted from labels to node IDs
        numeric_index: dict[str, str] = {}
        for nid, node in graph.nodes.items():
            m = re.search(r"(\d+(?:\.\d+)*)", node.label)
            if m:
                numeric_index[m.group(1)] = nid

        for clause in clauses:
            refs = detector.detect(clause.text)
            seen_targets: set[str] = set()
            for ref_number in refs:
                target_id = numeric_index.get(ref_number)
                if target_id and target_id != clause.id and target_id not in seen_targets:
                    seen_targets.add(target_id)
                    graph.edges.append(
                        GraphEdge(
                            source_id=clause.id,
                            target_id=target_id,
                            edge_type=EdgeType.cross_ref,
                            metadata={"pattern_matched": "Section\\s+(\\d+(?:\\.\\d+)*)"},
                        )
                    )

    def _add_def_ref_edges(self, graph: ContractGraph, clauses: list[Clause]) -> None:
        """Scan clause text for definition references and add edges."""
        detector = DefinitionDetector()
        definitions = detector.extract_definitions(clauses)

        for clause in clauses:
            refs = detector.count_references(clause.text, definitions)
            seen_terms: set[str] = set()
            for term, target_id in refs:
                if target_id and target_id != clause.id and term not in seen_terms:
                    seen_terms.add(term)
                    graph.edges.append(
                        GraphEdge(
                            source_id=clause.id,
                            target_id=target_id,
                            edge_type=EdgeType.def_ref,
                            metadata={"term": term},
                        )
                    )


def build_from_parsed(path: str | Path) -> ContractGraph:
    """Load parsed clauses from a JSON file and build a ContractGraph.

    Accepts a JSON file path containing a list of Clause-compatible dicts
    as produced by ``openreview parse --format json``.

    Raises FileNotFoundError if the path does not exist.
    Raises json.JSONDecodeError if the file is not valid JSON.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {path}")

    clause_dicts: list[dict[str, Any]] = json.loads(p.read_text(encoding="utf-8"))

    clauses: list[Clause] = []
    for cd in clause_dicts:
        clauses.append(
            Clause(
                id=cd["id"],
                title=cd.get("title"),
                text=cd["text"],
                level=cd.get("level", 0),
                parent_id=cd.get("parent_id"),
                source_page=cd.get("source_page"),
                source_paragraph=cd.get("source_paragraph"),
                source_span=cd.get("source_span"),
                paragraph_count=cd.get("paragraph_count"),
            )
        )

    builder = ClauseHierarchyBuilder()
    return builder.build(clauses)


__all__ = [
    "ClauseHierarchyBuilder",
    "build_from_parsed",
]
