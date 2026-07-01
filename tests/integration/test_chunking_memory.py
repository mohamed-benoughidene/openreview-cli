import tracemalloc

import pytest

from openreview_cli.chunking.models import ChunkConfig
from openreview_cli.chunking.stream import stream_chunks
from openreview_cli.parsing.models import Clause

pytestmark = pytest.mark.memory


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


@pytest.mark.integration
def test_chunking_memory_50page() -> None:
    """T027: Chunking memory stays under 10 MB peak (SC-005)."""
    MAX_CHUNKING_MEMORY_BYTES = 10 * 1024 * 1024

    tracemalloc.start()
    try:
        config = ChunkConfig()
        clauses = _synthetic_50page_contract()
        chunks = list(stream_chunks(clauses, config))
        _current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert peak < MAX_CHUNKING_MEMORY_BYTES, (
        f"Chunking {len(clauses)} clauses into {len(chunks)} chunks "
        f"peaked at {peak / 1024 / 1024:.2f} MB, expected <10 MB"
    )
