import time
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "pdf"


@pytest.mark.integration
@pytest.mark.benchmark
def test_parse_speed_50_page_pdf() -> None:
    from openreview_cli.parsing.stream import stream_clauses

    start = time.perf_counter()
    clauses = list(stream_clauses(FIXTURES / "50_page.pdf"))
    elapsed = time.perf_counter() - start

    assert elapsed < 3.0, f"Parse took {elapsed:.2f}s, expected <3.0s"
    assert len(clauses) > 0
