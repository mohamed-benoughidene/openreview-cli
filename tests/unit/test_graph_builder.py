from __future__ import annotations

import json
from pathlib import Path

import pytest

from openreview_cli.graph.builder import ClauseHierarchyBuilder, build_from_parsed
from openreview_cli.graph.models import EdgeType
from openreview_cli.parsing.models import Clause


def make_clause(
    id: str,
    text: str = "Some clause text",
    level: int = 0,
    parent_id: str | None = None,
    title: str | None = None,
) -> Clause:
    return Clause(
        id=id,
        title=title,
        text=text,
        level=level,
        parent_id=parent_id,
        source_page=None,
        source_paragraph=None,
        source_span=None,
        paragraph_count=None,
    )


class TestClauseHierarchyBuilder:
    def test_parent_id_maps_to_parent_child_edge(self) -> None:
        builder = ClauseHierarchyBuilder()
        clauses = [
            make_clause("c1", "Article 1", level=0, parent_id=None),
            make_clause("c2", "Section 1.1", level=1, parent_id="c1"),
        ]
        graph = builder.build(clauses)
        assert len(graph.nodes) == 2

        parent_edges = [e for e in graph.edges if e.edge_type == EdgeType.parent_child]
        assert len(parent_edges) == 1
        assert parent_edges[0].source_id == "c1"
        assert parent_edges[0].target_id == "c2"

    def test_null_parent_id_means_root(self) -> None:
        builder = ClauseHierarchyBuilder()
        clauses = [
            make_clause("c1", "Article 1", level=0, parent_id=None),
            make_clause("c2", "Article 2", level=0, parent_id=None),
        ]
        graph = builder.build(clauses)
        assert len(graph.roots) == 2

    def test_dangling_parent_id_becomes_root(self) -> None:
        builder = ClauseHierarchyBuilder()
        clauses = [
            make_clause("c2", "Section 1.1", level=1, parent_id="c1"),
        ]
        graph = builder.build(clauses)
        # No parent-child edge since c1 not in nodes
        pc_edges = [e for e in graph.edges if e.edge_type == EdgeType.parent_child]
        assert len(pc_edges) == 0
        assert "c2" in graph.roots

    def test_single_clause(self) -> None:
        builder = ClauseHierarchyBuilder()
        clauses = [make_clause("c1", "Article 1", level=0)]
        graph = builder.build(clauses)
        assert len(graph.nodes) == 1
        assert len(graph.edges) == 0

    def test_mixed_hierarchy(self) -> None:
        builder = ClauseHierarchyBuilder()
        clauses = [
            make_clause("c1", "Article 1", level=0, parent_id=None),
            make_clause("c2", "Section 1.1", level=1, parent_id="c1"),
            make_clause("c3", "Section 1.2", level=1, parent_id="c1"),
            make_clause("c4", "Subsection 1.2.1", level=2, parent_id="c3"),
        ]
        graph = builder.build(clauses)
        parent_edges = [e for e in graph.edges if e.edge_type == EdgeType.parent_child]
        assert len(parent_edges) == 3

    def test_cross_ref_edges_detected(self) -> None:
        """Cross-references in clause text produce cross_ref edges."""
        builder = ClauseHierarchyBuilder()
        clauses = [
            make_clause("c1", "Article 1 text", level=0, parent_id=None, title="Article 1"),
            make_clause(
                "c2",
                "See cross-reference to Section 1.",
                level=1,
                parent_id="c1",
                title="Section 1.1",
            ),
        ]
        graph = builder.build(clauses)
        cross_refs = [e for e in graph.edges if e.edge_type == EdgeType.cross_ref]
        assert len(cross_refs) >= 1

    def test_def_ref_edges_detected(self) -> None:
        """Definition references in clause text produce def_ref edges."""
        builder = ClauseHierarchyBuilder()
        clauses = [
            make_clause(
                "c1",
                '"Confidential Information" means non-public data.',
                level=0,
                parent_id=None,
                title="Article 1",
            ),
            make_clause(
                "c2",
                'The "Confidential Information" shall be protected.',
                level=1,
                parent_id="c1",
                title="Section 1.1",
            ),
        ]
        graph = builder.build(clauses)
        def_refs = [e for e in graph.edges if e.edge_type == EdgeType.def_ref]
        assert len(def_refs) >= 1
        assert def_refs[0].metadata.get("term") == "Confidential Information"


class TestBuildFromParsed:
    def test_convenience_loads_from_json(self, tmp_path: Path) -> None:
        clauses_data = [
            {
                "id": "c1",
                "title": "Article 1",
                "text": "Article 1 text",
                "level": 0,
                "parent_id": None,
                "source_page": None,
                "source_paragraph": None,
                "source_span": None,
                "paragraph_count": None,
            },
            {
                "id": "c2",
                "title": "Section 1.1",
                "text": "Section 1.1 text",
                "level": 1,
                "parent_id": "c1",
                "source_page": None,
                "source_paragraph": None,
                "source_span": None,
                "paragraph_count": None,
            },
        ]
        file_path = tmp_path / "parsed.json"
        file_path.write_text(json.dumps(clauses_data))

        graph = build_from_parsed(str(file_path))
        assert len(graph.nodes) == 2
        pc_edges = [e for e in graph.edges if e.edge_type == EdgeType.parent_child]
        assert len(pc_edges) == 1

    def test_non_existent_file(self) -> None:
        with pytest.raises(FileNotFoundError):
            build_from_parsed("/nonexistent/file.json")
