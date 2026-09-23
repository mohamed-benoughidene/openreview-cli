"""TUI domain wrapper for a document's clause-graph metrics.

Runs the same pipeline the CLI uses -- ``parse_document`` ->
``ClauseHierarchyBuilder`` -> ``compute_metrics`` -> ``compute_health`` -- so
the TUI and the CLI can never disagree about a document's numbers.

Every import of ``openreview_cli.parsing`` / ``openreview_cli.graph`` is made
inside ``graph_summary_via_tui`` (with ``pymupdf`` inside the PDF guard): the
TUI keeps non-trivial module-level imports out of its startup path, matching
the policy documented in ``openreview_cli.tui.domain.pii``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

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


def _guard_password_protected_pdf(path: Path) -> None:
    """Raise a ``ParseError`` for an encrypted PDF before parsing it.

    ``PdfParser.parse`` prompts for a password via ``getpass`` when stdin is a
    TTY; in the running TUI stdin *is* a TTY, so that prompt would block the
    worker thread forever. Opening the PDF here first lets the screen refuse an
    encrypted document deterministically, without ever prompting.

    Only regular files are inspected: a directory named ``*.pdf`` is left to
    ``parse_document`` so it surfaces as the usual ``OSError``.
    """
    if path.suffix.lower() != ".pdf" or not path.is_file():
        return

    import pymupdf

    from openreview_cli.parsing.models import ParseError, ParseErrorCategory

    document: Any = pymupdf.open(str(path))  # type: ignore[no-untyped-call]
    try:
        if document.needs_pass:
            raise ParseError(
                exit_code=8,
                category=ParseErrorCategory.password_protected,
                message="This contract is password-protected.",
                action="Provide an unlocked copy of the document.",
            )
    finally:
        document.close()


def graph_summary_via_tui(document_path: Path) -> GraphSummary:
    """Parse *document_path* and summarise its clause graph and health.

    Returns the real ``GraphMetrics`` object and the real ``HealthScore.score``
    read off ``compute_health`` -- no weight or formula is recomputed here.

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
    _guard_password_protected_pdf(path)

    _document, clauses = parse_document(path)
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
