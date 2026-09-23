"""TUI domain wrapper for a document's clause-graph metrics.

Runs the same pipeline the CLI uses -- ``parse_document`` ->
``ClauseHierarchyBuilder`` -> ``compute_metrics`` -> ``compute_health`` -- so
the TUI and the CLI can never disagree about a document's numbers.

Every import of ``openreview_cli.parsing`` / ``openreview_cli.graph`` is made
inside ``graph_summary_via_tui``: the TUI keeps non-trivial module-level imports
out of its startup path, matching the policy documented in
``openreview_cli.tui.domain.pii``.

The screen must never prompt for a password: Textual owns stdin, so a
``getpass`` prompt would block the worker thread forever. The parser owns that
rule now, so this module passes ``allow_password_prompt=False`` and lets
``parse_document`` raise ``ParseError`` for an encrypted PDF. A former local
guard opened the PDF with pymupdf and refused it outright, which additionally
rejected documents a configured ``OPENREVIEW_PDF_PASSWORD`` could have opened --
inconsistent with the rest of the app, which honours that variable.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openreview_cli.graph.metrics import GraphMetrics


@dataclass(frozen=True, slots=True)
class GraphSummary:
    """Read-only clause-graph summary for one document."""

    filename: str
    node_count: int
    edge_count: int
    parent_child_edge_count: int
    metrics: GraphMetrics
    score: int


def graph_summary_via_tui(document_path: Path) -> GraphSummary:
    """Parse *document_path* and summarise its clause graph and health.

    Returns the real ``GraphMetrics`` object and the real ``HealthScore.score``
    read off ``compute_health`` -- no weight or formula is recomputed here.

    ``parse_document`` is called with ``allow_password_prompt=False``: the
    screen must never prompt, so an encrypted document is refused by the parser
    (honouring ``OPENREVIEW_PDF_PASSWORD`` when one is configured) instead of
    blocking the worker on ``getpass``.

    Raises:
        FileNotFoundError: The path does not exist.
        ParseError: The document is missing/unsupported/empty/encrypted/corrupt
            or contains no extractable text.
        OSError: The path cannot be read (e.g. it is a directory).
    """
    from openreview_cli.graph.builder import ClauseHierarchyBuilder
    from openreview_cli.graph.health import compute_health
    from openreview_cli.graph.metrics import compute_metrics
    from openreview_cli.graph.models import EdgeType
    from openreview_cli.parsing.stream import parse_document

    path = Path(document_path)
    if not path.exists():
        raise FileNotFoundError(f"No file found at '{path}'.")

    _document, clauses = parse_document(path, allow_password_prompt=False)
    graph = ClauseHierarchyBuilder().build(clauses)
    metrics = compute_metrics(graph)
    score = compute_health(metrics).score
    parent_child_edge_count = sum(
        1 for edge in graph.edges if edge.edge_type == EdgeType.parent_child
    )

    return GraphSummary(
        filename=path.name,
        node_count=len(graph.nodes),
        edge_count=len(graph.edges),
        parent_child_edge_count=parent_child_edge_count,
        metrics=metrics,
        score=score,
    )


__all__ = ["GraphSummary", "graph_summary_via_tui"]
