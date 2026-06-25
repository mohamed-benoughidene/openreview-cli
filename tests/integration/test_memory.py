from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "pdf"


@pytest.mark.memory
def test_peak_memory_500_page_pdf() -> None:
    import tracemalloc

    tracemalloc.start()
    from openreview_cli.parsing.stream import stream_clauses

    clauses = list(stream_clauses(FIXTURES / "500_page.pdf"))
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert peak < 100 * 1024 * 1024, f"Peak memory {peak / 1024 / 1024:.1f} MB exceeds 100 MB"
    assert len(clauses) > 0
