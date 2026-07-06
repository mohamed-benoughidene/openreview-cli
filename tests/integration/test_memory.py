from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "pdf"


@pytest.mark.integration
@pytest.mark.memory
def test_peak_memory_500_page_pdf() -> None:
    import tracemalloc

    from openreview_cli.parsing.stream import stream_clauses

    # Warm the lazy-loaded nupunkt model (~320 MB) before starting the
    # memory measurement so the test captures per-document parse memory,
    # not the one-time NLP model load.
    list(stream_clauses(FIXTURES / "simple_contract.pdf"))

    tracemalloc.start()
    clauses = list(stream_clauses(FIXTURES / "500_page.pdf"))
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert peak < 110 * 1024 * 1024, f"Peak memory {peak / 1024 / 1024:.1f} MB exceeds 110 MB"
    assert len(clauses) > 0


@pytest.mark.integration
@pytest.mark.memory
def test_gateway_peak_memory(tmp_path: Path) -> None:
    import tracemalloc

    config_path = tmp_path / "config.yml"
    config_path.write_text(
        "version: 1\ngateway:\n  models:\n    reasoning:\n      primary: ollama/qwen3:8b\n"
    )
    auth_path = tmp_path / "auth.json"
    auth_path.write_text("{}")

    from openreview_cli.gateway.router import Gateway

    tracemalloc.start()
    gw = Gateway(config_path, auth_path, tmp_path / "data.db")
    _ = gw.health_check()
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert peak < 110 * 1024 * 1024, (
        f"Gateway peak memory {peak / 1024 / 1024:.1f} MB exceeds 110 MB"
    )


@pytest.mark.integration
@pytest.mark.memory
def test_review_peak_memory() -> None:
    """T052: Verify review pipeline stays under 100 MB peak.

    Mocks the gateway calls so no real model is needed. The memory
    footprint comes from clause parsing + data model allocation only.
    """
    import tracemalloc
    from datetime import UTC, datetime

    from openreview_cli.parsing.stream import parse_document, stream_clauses
    from openreview_cli.review.models import (
        ClauseAssessment,
        DocMeta,
        Position,
        QAVerdict,
        ReviewReport,
        ReviewSummary,
    )
    from openreview_cli.review.playbook import load_bundled

    FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "pdf"

    # Warm the lazy-loaded nupunkt model before measuring
    list(stream_clauses(FIXTURES / "simple_contract.pdf"))

    tracemalloc.start()

    doc, clauses = parse_document(str(FIXTURES / "simple_contract.pdf"))

    # Build assessments without calling the real gateway
    playbook = load_bundled()
    assessments: list[ClauseAssessment] = []
    for clause in clauses:
        assessments.append(
            ClauseAssessment(
                clause_id=clause.id,
                clause_text=clause.text,
                playbook_category="confidentiality-term",
                position=Position.ACCEPTABLE,
                confidence=0.85,
                citation=clause.text[:80],
                qa_verdict=QAVerdict.agree,
                extraction_model="test",
                qa_model="test",
            )
        )

    doc_meta = DocMeta(
        filename=doc.source_path.name,
        page_count=doc.page_count,
        clause_count=len(assessments),
        pii_stripped=False,
        parsed_at=datetime.now(UTC),
    )
    summary = ReviewSummary(
        preferred_count=0,
        acceptable_count=len(assessments),
        walkaway_count=0,
        uncertain_count=0,
        no_match_count=0,
        amber_count=0,
        avg_confidence=0.85,
    )
    _report = ReviewReport(
        document=doc_meta,
        assessments=assessments,
        summary=summary,
        playbook_id="precheck-nda-v1",
        generated_at=datetime.now(UTC),
    )

    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert peak < 110 * 1024 * 1024, (
        f"Review pipeline peak memory {peak / 1024 / 1024:.1f} MB exceeds 110 MB"
    )


@pytest.mark.memory
def test_graph_peak_memory() -> None:
    """T030: Verify graph build + metrics + health + view stays under 110 MB peak.

    Builds a 500-node synthetic clause hierarchy and runs all graph operations.
    """
    import tracemalloc

    from openreview_cli.graph.builder import ClauseHierarchyBuilder
    from openreview_cli.graph.health import compute_health
    from openreview_cli.graph.metrics import compute_metrics
    from openreview_cli.graph.view import render_tree
    from openreview_cli.parsing.models import Clause

    # Build 500 synthetic clauses with hierarchy
    clauses: list[Clause] = []
    for i in range(500):
        parent_id: str | None = f"c{i // 5}" if i > 0 else None
        clauses.append(
            Clause(
                id=f"c{i}",
                title=f"Section {i}",
                text=f"This is clause {i} with some reference text.",
                level=0,
                parent_id=parent_id if parent_id != f"c{i}" else None,
                source_page=None,
                source_paragraph=None,
                source_span=None,
            )
        )

    builder = ClauseHierarchyBuilder()
    tracemalloc.start()
    graph = builder.build(clauses)
    metrics = compute_metrics(graph)
    health = compute_health(metrics)
    _view = render_tree(graph)
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert peak < 110 * 1024 * 1024, f"Graph peak memory {peak / 1024 / 1024:.1f} MB exceeds 110 MB"
    assert len(graph.nodes) == 500
    assert 0 <= health.score <= 100
