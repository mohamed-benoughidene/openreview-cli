"""Unit tests for the TUI clause-graph domain wrapper.

No Textual, no ``run_test``: the wrapper is the whole surface under test. The
document is a real fixture parsed by the real parser, so the graph the summary
carries is the graph the screens go on to render -- one parse, one build.

``with_headings.docx`` is unnumbered but has real heading levels, so
``link_parent_ids`` turns it into a three-clause hierarchy with two
``parent_child`` edges: concrete nodes and edges to assert against.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from openreview_cli.graph.models import ContractGraph, EdgeType
from openreview_cli.parsing import stream as stream_module
from openreview_cli.tui.domain.graph import graph_summary_via_tui

_FIXTURE = Path("docx/with_headings.docx")


def test_the_summary_carries_the_graph_it_counted(fixtures_dir: Path) -> None:
    """The built graph travels with the summary -- the screens render one object."""
    summary = graph_summary_via_tui(fixtures_dir / _FIXTURE)

    assert isinstance(summary.graph, ContractGraph)
    assert [node.label for node in summary.graph.nodes.values()] == [
        "Article I",
        "Section 1.1",
        "Section 1.2",
    ]

    labels = {node.id: node.label for node in summary.graph.nodes.values()}
    hierarchy = [
        (labels[edge.source_id], labels[edge.target_id])
        for edge in summary.graph.edges
        if edge.edge_type == EdgeType.parent_child
    ]
    assert hierarchy == [("Article I", "Section 1.1"), ("Article I", "Section 1.2")]

    # Summary and graph cannot disagree: the counts are read off this object.
    assert (len(summary.graph.nodes), len(summary.graph.edges)) == (
        summary.node_count,
        summary.edge_count,
    )
    assert summary.parent_child_edge_count == 2


def test_the_document_is_parsed_exactly_once(
    fixtures_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Keeping the graph must not add a second parse+build path (design G6)."""
    parsed: list[Path] = []
    real_parse_document = stream_module.parse_document

    def counting_parse_document(*args: Any, **kwargs: Any) -> Any:
        parsed.append(Path(args[0]))
        return real_parse_document(*args, **kwargs)

    monkeypatch.setattr(stream_module, "parse_document", counting_parse_document)

    document = fixtures_dir / _FIXTURE
    summary = graph_summary_via_tui(document)

    assert parsed == [document]
    # ...and that single parse is what the graph came from.
    assert len(summary.graph.nodes) == summary.node_count != 0


def test_a_missing_document_raises_file_not_found(tmp_path: Path) -> None:
    """The metrics screen's guard is unchanged by the new field."""
    with pytest.raises(FileNotFoundError):
        graph_summary_via_tui(tmp_path / "absent.pdf")
