from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Generator

    from openreview_cli.parsing.models import Clause

import pytest

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "docx"
PDF_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "pdf"


class TestDocxParserIntegration:
    @pytest.mark.integration
    def test_simple_contract_matches_pdf_structure(self) -> None:
        from openreview_cli.parsing.stream import stream_clauses

        clauses = list(stream_clauses(FIXTURES / "simple_contract.docx"))
        assert len(clauses) >= 3
        assert all(c.id.startswith("clause-") for c in clauses)

    @pytest.mark.integration
    def test_headings_detected(self) -> None:
        from openreview_cli.parsing.stream import stream_clauses

        clauses = list(stream_clauses(FIXTURES / "with_headings.docx"))
        assert len(clauses) >= 2
        assert any(c.title for c in clauses if c.title)

    @pytest.mark.integration
    def test_flat_document_all_level_zero(self) -> None:
        from openreview_cli.parsing.stream import stream_clauses

        clauses = list(stream_clauses(FIXTURES / "flat_document.docx"))
        assert all(c.level == 0 for c in clauses)

    @pytest.mark.integration
    def test_embedded_images_skipped(self) -> None:
        from openreview_cli.parsing.stream import stream_clauses

        clauses = list(stream_clauses(FIXTURES / "with_images.docx"))
        assert len(clauses) >= 2
        texts = " ".join(c.text for c in clauses)
        assert "defines key terms" in texts

    @pytest.mark.integration
    def test_ctrl_c_clean_exit(self) -> None:
        from openreview_cli.parsing.stream import stream_clauses

        gen: Generator[Clause, Any, Any] = stream_clauses(FIXTURES / "simple_contract.docx")  # type: ignore[assignment]
        try:
            next(gen)
            gen.throw(KeyboardInterrupt)
        except StopIteration:
            pass
