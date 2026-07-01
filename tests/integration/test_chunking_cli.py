from pathlib import Path

import pytest
from typer.testing import CliRunner

from openreview_cli.app import app

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
runner = CliRunner()


pytestmark = pytest.mark.integration


def test_chunk_cli_smoke() -> None:
    """T020a: Chunk command runs on a real PDF and produces output."""
    pdf = FIXTURES_DIR / "pdf" / "simple_contract.pdf"
    if not pdf.exists():
        pytest.skip("simple_contract.pdf fixture not found")
    result = runner.invoke(app, ["chunk", str(pdf)])
    assert result.exit_code == 0
    assert "Chunk" in result.output


def test_pii_safe_chunking() -> None:
    """T011/T014: Full pipeline (parse → strip_pii_clauses → stream_chunks)
    produces chunks with no raw PII."""
    from openreview_cli.chunking.stream import stream_chunks
    from openreview_cli.parsing.stream import parse_document
    from openreview_cli.pii.engine import strip_pii_clauses

    pdf = FIXTURES_DIR / "nda_with_pii.pdf"
    if not pdf.exists():
        pytest.skip("nda_with_pii.pdf fixture not found")

    doc, clauses = parse_document(pdf)
    stripped, result = strip_pii_clauses(clauses, doc)
    chunks = list(stream_chunks(stripped))

    assert len(chunks) > 0, "Expected at least one chunk"
    assert len(result.mapping) > 0, "Expected at least one PII mapping entry"

    for chunk in chunks:
        for original in result.mapping.values():
            assert original not in chunk.text, f"Raw PII '{original}' found in chunk '{chunk.id}'"
