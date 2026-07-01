import time

import pytest

from openreview_cli.chunking.models import ChunkConfig
from openreview_cli.chunking.stream import stream_chunks
from openreview_cli.parsing.models import Clause

pytestmark = pytest.mark.integration


def _synthetic_50page_contract() -> list[Clause]:
    """Generate ~50 pages worth of clauses (~125,000 chars)."""
    clauses: list[Clause] = []
    articles = [
        "Definitions",
        "Term",
        "Payment",
        "Delivery",
        "Warranty",
        "Indemnification",
        "Insurance",
        "Confidentiality",
        "IP Rights",
        "Termination",
        "Dispute Resolution",
        "Governing Law",
        "Assignment",
        "Notices",
        "Waiver",
        "Severability",
        "Entire Agreement",
        "Amendments",
        "Counterparts",
        "Signatures",
    ]
    for i, title in enumerate(articles):
        words_per_page = 400
        text = " ".join([f"word_{j}" for j in range(words_per_page)])
        clauses.append(
            Clause(
                id=f"art-{i}",
                title=title,
                text=text,
                level=0,
                parent_id=None,
                source_page=i,
                source_paragraph=None,
                source_span=None,
            )
        )
    return clauses


def test_chunking_performance_50page() -> None:
    """T026: Chunk a 50-page contract in <2 seconds (SC-001)."""
    config = ChunkConfig()
    clauses = _synthetic_50page_contract()
    start = time.perf_counter()
    chunks = list(stream_chunks(clauses, config))
    elapsed = time.perf_counter() - start
    assert elapsed < 2.0, (
        f"Chunking {len(clauses)} clauses into {len(chunks)} chunks "
        f"took {elapsed:.3f}s, expected <2.0s"
    )
    assert len(chunks) >= len(clauses)
