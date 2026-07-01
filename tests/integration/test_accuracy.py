from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "pdf"


@pytest.mark.integration
@pytest.mark.accuracy
def test_clause_boundary_accuracy() -> None:
    from openreview_cli.parsing.stream import stream_clauses

    fixtures = [
        (FIXTURES / "simple_contract.pdf", 10),
        (FIXTURES / "complex_numbering.pdf", 10),
        (FIXTURES / "flat_document.pdf", 5),
    ]

    for fixture_path, expected_min in fixtures:
        clauses = list(stream_clauses(fixture_path))
        assert len(clauses) >= expected_min, (
            f"{fixture_path.name}: expected >= {expected_min} clauses, got {len(clauses)}"
        )
