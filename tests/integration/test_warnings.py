from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
PDF = FIXTURES / "pdf"
DOCX = FIXTURES / "docx"


class TestWarnings:
    @pytest.mark.integration
    def test_tracked_changes_warning(self) -> None:
        from docx import Document

        from openreview_cli.parsing.docx_parser import detect_tracked_changes

        doc = Document(str(DOCX / "tracked_changes.docx"))
        assert detect_tracked_changes(doc) is True

    @pytest.mark.integration
    def test_flat_document_no_headings(self) -> None:
        from openreview_cli.parsing.stream import stream_clauses

        clauses = list(stream_clauses(PDF / "flat_document.pdf"))
        assert all(c.level == 0 for c in clauses)

    @pytest.mark.integration
    def test_non_latin_script_detection(self) -> None:
        from openreview_cli.parsing.clause_detector import detect_non_english

        assert detect_non_english("مرحبا بالعالم") is not None
        assert detect_non_english("Hello World") is None
        assert detect_non_english("Привет мир") is not None
        assert detect_non_english("你好世界") is not None

    @pytest.mark.integration
    def test_tofu_detection(self) -> None:
        from openreview_cli.parsing.clause_detector import detect_tofu

        assert detect_tofu("Some text with \ufffd replacement") is True
        assert detect_tofu("Normal text without tofu") is False
