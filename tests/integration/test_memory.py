from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "pdf"


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
