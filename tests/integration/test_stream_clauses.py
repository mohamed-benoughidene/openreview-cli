from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
PDF = FIXTURES / "pdf"
DOCX = FIXTURES / "docx"


class TestStreamClauses:
    def test_routes_to_pdf_parser_for_pdf(self) -> None:
        from openreview_cli.parsing.stream import stream_clauses
        clauses = list(stream_clauses(PDF / "simple_contract.pdf"))
        assert all(c.source_page is not None for c in clauses)

    def test_routes_to_docx_parser_for_docx(self) -> None:
        from openreview_cli.parsing.stream import stream_clauses
        clauses = list(stream_clauses(DOCX / "simple_contract.docx"))
        assert all(c.source_paragraph is not None for c in clauses)

    def test_unsupported_format_raises(self) -> None:
        from openreview_cli.parsing.stream import stream_clauses
        from openreview_cli.parsing.models import ParseError
        with pytest.raises(ParseError) as exc:
            list(stream_clauses(FIXTURES / "test.txt"))
        assert exc.value.category == "unsupported_format"

    def test_non_existent_path_raises(self) -> None:
        from openreview_cli.parsing.stream import stream_clauses
        from openreview_cli.parsing.models import ParseError
        with pytest.raises(ParseError) as exc:
            list(stream_clauses(FIXTURES / "nonexistent.pdf"))
        assert exc.value.category == "file_not_found"

    def test_cross_format_equivalence_simple(self) -> None:
        from openreview_cli.parsing.stream import stream_clauses
        pdf_clauses = list(stream_clauses(PDF / "simple_contract.pdf"))
        docx_clauses = list(stream_clauses(DOCX / "simple_contract.docx"))
        pdf_count = len(pdf_clauses)
        docx_count = len(docx_clauses)
        diff = abs(pdf_count - docx_count) / max(pdf_count, docx_count)
        assert diff <= 0.1

    def test_cross_format_equivalence_flat(self) -> None:
        from openreview_cli.parsing.stream import stream_clauses
        pdf_clauses = list(stream_clauses(PDF / "flat_document.pdf"))
        docx_clauses = list(stream_clauses(DOCX / "flat_document.docx"))
        assert all(c.level == 0 for c in pdf_clauses)
        assert all(c.level == 0 for c in docx_clauses)


class TestCrossFormatHierarchy:
    def test_parent_id_chain_integrity(self) -> None:
        from openreview_cli.parsing.stream import stream_clauses
        for path in [PDF / "simple_contract.pdf", DOCX / "simple_contract.docx"]:
            clauses = list(stream_clauses(path))
            ids = {c.id for c in clauses}
            for clause in clauses:
                if clause.parent_id is not None:
                    assert clause.parent_id in ids

    def test_warnings_match_across_formats(self) -> None:
        pass  # Placeholder — warnings not fully implemented yet
