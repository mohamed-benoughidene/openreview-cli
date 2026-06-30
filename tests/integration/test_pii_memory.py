"""Memory budget validation for PII stripping (T050 from Phase 3).

Validates peak memory <100 MB (excluding NLP model load) during PII
stripping of a 500-page document with 2000+ PII entities, and processing
time <30 seconds.
"""

import time
from pathlib import Path

import pytest

from openreview_cli.parsing.models import Clause, Document
from openreview_cli.pii.engine import PiiEngine, strip_pii


@pytest.mark.memory
def test_pii_memory_500_pages_2000_entities() -> None:
    """Process a 500-page Clause list with 2000+ PII entities under 100 MB / 30 s.

    The spaCy/Presidio model is warmed up before tracemalloc starts so the
    peak reflects per-document processing overhead, not the one-time model load.
    """
    import tracemalloc

    # -- Build 500 clauses (~2000 chars each) with 2000+ PII entities -------
    pii_templates = [
        "john.doe@email.com",
        "+1 (555) 123-4567",
        "192-34-5678",
        "4111-1111-1111-1111",
        "192.168.1.1",
        "John A. Doe",
        "123 Main St, Springfield, IL 62701",
        "john.doe@company.org",
    ]
    num_pii_templates = len(pii_templates)

    clauses: list[Clause] = []
    entity_count = 0

    for page_num in range(1, 501):
        text = (
            f"This is page {page_num}. This contract document contains various "
            "confidential information that must be protected. "
        )
        # 4 entities per page x 500 pages = 2000
        for i in range(4):
            pii = pii_templates[(page_num * 4 + i) % num_pii_templates]
            text += (
                f"The following information is confidential: {pii}. "
                "It should not be disclosed to unauthorized parties. "
            )
            entity_count += 1

        clauses.append(
            Clause(
                id=f"clause-{page_num:04d}",
                title=f"Section {page_num}",
                text=text,
                level=1,
                parent_id=None,
                source_page=page_num,
                source_paragraph=None,
                source_span=None,
            )
        )

    document = Document(
        source_path=Path("/dev/null/contract.pdf"),
        format="pdf",
        page_count=500,
        clause_count=len(clauses),
        parse_duration_seconds=5.0,
        warnings=[],
    )

    # -- Warm the NLP model so tracemalloc captures only processing overhead --
    engine = PiiEngine(threshold=0.7)
    engine._ensure_analyzer()

    # -- Measure PII stripping memory + time ---------------------------------
    tracemalloc.start()
    start = time.perf_counter()

    result = strip_pii(clauses, document, engine=engine)

    duration = time.perf_counter() - start
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    engine.close()

    max_peak = 100 * 1024 * 1024
    max_seconds = 30.0

    print(
        f"\nPII Memory Report:\n"
        f"  Pages:        {document.page_count}\n"
        f"  Clauses:      {len(clauses)}\n"
        f"  Entities in:  {entity_count}\n"
        f"  Entities out: {len(result.entities)}\n"
        f"  Peak memory:  {peak / 1024 / 1024:.1f} MB\n"
        f"  Duration:     {duration:.2f}s\n"
    )

    assert peak < max_peak, (
        f"Peak memory {peak / 1024 / 1024:.1f} MB exceeds {max_peak / 1024 / 1024:.0f} MB"
    )
    assert duration < max_seconds, f"Processing time {duration:.2f}s exceeds {max_seconds:.0f}s"
