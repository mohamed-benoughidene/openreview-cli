from pathlib import Path

import pytest

from openreview_cli.parsing.models import Clause, Document, ParseError, ParseErrorCategory


class TestClause:
    def test_valid_clause(self) -> None:
        clause = Clause(
            id="clause-0",
            title="Article I",
            text="This is the text.",
            level=0,
            parent_id=None,
            source_page=1,
            source_paragraph=None,
            source_span=(0, 20),
        )
        assert clause.id == "clause-0"
        assert clause.title == "Article I"
        assert clause.text == "This is the text."
        assert clause.level == 0

    def test_slots_prevents_extra_attributes(self) -> None:
        clause = Clause(
            id="clause-0",
            title=None,
            text="text",
            level=0,
            parent_id=None,
            source_page=None,
            source_paragraph=None,
            source_span=None,
        )
        with pytest.raises(AttributeError):
            clause.nonexistent = "should fail"  # type: ignore[attr-defined]

    def test_empty_id_raises(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            Clause(id="", title=None, text="text", level=0, parent_id=None, source_page=None, source_paragraph=None, source_span=None)

    def test_negative_level_raises(self) -> None:
        with pytest.raises(ValueError, match=">= 0"):
            Clause(id="c-0", title=None, text="text", level=-1, parent_id=None, source_page=None, source_paragraph=None, source_span=None)

    def test_empty_text_raises(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            Clause(id="c-0", title=None, text="   ", level=0, parent_id=None, source_page=None, source_paragraph=None, source_span=None)

    def test_mutually_exclusive_source_fields_raises(self) -> None:
        with pytest.raises(ValueError, match="mutually exclusive"):
            Clause(id="c-0", title=None, text="text", level=0, parent_id=None, source_page=1, source_paragraph=2, source_span=None)

    def test_docx_clause_no_page(self) -> None:
        clause = Clause(
            id="c-0",
            title=None,
            text="text",
            level=0,
            parent_id=None,
            source_page=None,
            source_paragraph=5,
            source_span=None,
        )
        assert clause.source_paragraph == 5
        assert clause.source_page is None


class TestDocument:
    def test_valid_document(self) -> None:
        doc = Document(
            source_path=Path("/test.pdf"),
            format="pdf",
            page_count=5,
            clause_count=20,
            parse_duration_seconds=1.5,
            warnings=[],
        )
        assert doc.format == "pdf"
        assert doc.page_count == 5

    def test_invalid_format_raises(self) -> None:
        with pytest.raises(ValueError, match="format"):
            Document(source_path=Path("/t.txt"), format="txt", page_count=1, clause_count=0, parse_duration_seconds=0.0, warnings=[])

    def test_page_count_below_one_raises(self) -> None:
        with pytest.raises(ValueError, match="page_count"):
            Document(source_path=Path("/t.pdf"), format="pdf", page_count=0, clause_count=1, parse_duration_seconds=0.1, warnings=[])

    def test_negative_clause_count_raises(self) -> None:
        with pytest.raises(ValueError, match="clause_count"):
            Document(source_path=Path("/t.pdf"), format="pdf", page_count=1, clause_count=-1, parse_duration_seconds=0.1, warnings=[])

    def test_negative_duration_raises(self) -> None:
        with pytest.raises(ValueError, match="parse_duration_seconds"):
            Document(source_path=Path("/t.pdf"), format="pdf", page_count=1, clause_count=0, parse_duration_seconds=-0.1, warnings=[])


class TestParseError:
    def test_valid_error(self) -> None:
        err = ParseError(exit_code=8, category="file_not_found", message="Not found.", action="Check path.")
        assert err.exit_code == 8
        assert err.category == "file_not_found"

    def test_exit_code_must_be_8(self) -> None:
        with pytest.raises(ValueError, match="exit_code"):
            ParseError(exit_code=1, category="corrupt", message="x", action="y")

    def test_invalid_category_raises(self) -> None:
        with pytest.raises(ValueError, match="category"):
            ParseError(exit_code=8, category="bogus", message="x", action="y")

    def test_empty_message_raises(self) -> None:
        with pytest.raises(ValueError, match="message"):
            ParseError(exit_code=8, category="corrupt", message="", action="y")

    def test_empty_action_raises(self) -> None:
        with pytest.raises(ValueError, match="action"):
            ParseError(exit_code=8, category="corrupt", message="x", action="")

    @pytest.mark.parametrize("cat", [c.value for c in ParseErrorCategory])
    def test_all_categories(self, cat: str) -> None:
        err = ParseError(exit_code=8, category=cat, message=f"Error {cat}.", action="Do something.")
        assert err.category == cat

    def test_str_is_message(self) -> None:
        err = ParseError(exit_code=8, category="corrupt", message="Corrupt file.", action="Fix it.")
        assert str(err) == "Corrupt file."

    def test_exception_subclass(self) -> None:
        assert issubclass(ParseError, Exception)
