"""Parsing models — construction validation rules."""

from pathlib import Path

import pytest

from openreview_cli.parsing.models import Clause, Document, ParseError


class TestClause:
    def test_valid(self) -> None:
        c = Clause(
            id="c1",
            title="Title",
            text="Hello world",
            level=0,
            parent_id=None,
            source_page=None,
            source_paragraph=None,
            source_span=None,
        )
        assert c.id == "c1"
        assert c.text == "Hello world"
        assert c.title == "Title"

    def test_empty_id_raises(self) -> None:
        with pytest.raises(ValueError, match="id must be non-empty"):
            Clause(
                id="",
                title=None,
                text="text",
                level=0,
                parent_id=None,
                source_page=None,
                source_paragraph=None,
                source_span=None,
            )

    def test_negative_level_raises(self) -> None:
        with pytest.raises(ValueError, match="level must be >= 0"):
            Clause(
                id="c1",
                title=None,
                text="text",
                level=-1,
                parent_id=None,
                source_page=None,
                source_paragraph=None,
                source_span=None,
            )

    def test_blank_text_raises(self) -> None:
        with pytest.raises(ValueError, match="text must be non-empty"):
            Clause(
                id="c1",
                title=None,
                text="   ",
                level=0,
                parent_id=None,
                source_page=None,
                source_paragraph=None,
                source_span=None,
            )

    def test_both_source_page_and_paragraph_raises(self) -> None:
        with pytest.raises(ValueError, match="mutually exclusive"):
            Clause(
                id="c1",
                title=None,
                text="text",
                level=0,
                parent_id=None,
                source_page=1,
                source_paragraph=2,
                source_span=None,
            )


class TestDocument:
    def test_valid(self) -> None:
        d = Document(
            source_path=Path("/tmp/doc.pdf"),
            format="pdf",
            page_count=5,
            clause_count=3,
            parse_duration_seconds=1.5,
            warnings=[],
        )
        assert d.format == "pdf"
        assert d.page_count == 5

    def test_valid_docx(self) -> None:
        d = Document(
            source_path=Path("/tmp/doc.docx"),
            format="docx",
            page_count=1,
            clause_count=0,
            parse_duration_seconds=0.0,
            warnings=[],
        )
        assert d.format == "docx"

    def test_invalid_format_raises(self) -> None:
        with pytest.raises(ValueError, match="format must be 'pdf' or 'docx'"):
            Document(
                source_path=Path("/tmp/doc.txt"),
                format="txt",
                page_count=1,
                clause_count=0,
                parse_duration_seconds=0.0,
                warnings=[],
            )

    def test_page_count_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="page_count must be >= 1"):
            Document(
                source_path=Path("/tmp/doc.pdf"),
                format="pdf",
                page_count=0,
                clause_count=0,
                parse_duration_seconds=0.0,
                warnings=[],
            )

    def test_negative_clause_count_raises(self) -> None:
        with pytest.raises(ValueError, match="clause_count must be >= 0"):
            Document(
                source_path=Path("/tmp/doc.pdf"),
                format="pdf",
                page_count=1,
                clause_count=-1,
                parse_duration_seconds=0.0,
                warnings=[],
            )

    def test_negative_duration_raises(self) -> None:
        with pytest.raises(ValueError, match="parse_duration_seconds must be >= 0"):
            Document(
                source_path=Path("/tmp/doc.pdf"),
                format="pdf",
                page_count=1,
                clause_count=0,
                parse_duration_seconds=-0.1,
                warnings=[],
            )


class TestParseError:
    def test_valid(self) -> None:
        e = ParseError(
            exit_code=8, category="file_not_found", message="File not found", action="Check path"
        )
        assert str(e) == "File not found"
        assert repr(e) == "ParseError(file_not_found: File not found)"

    def test_wrong_exit_code_raises(self) -> None:
        with pytest.raises(ValueError, match="exit_code must be 8"):
            ParseError(exit_code=1, category="file_not_found", message="msg", action="act")

    def test_invalid_category_raises(self) -> None:
        with pytest.raises(ValueError, match="invalid category"):
            ParseError(exit_code=8, category="bogus", message="msg", action="act")

    def test_empty_message_raises(self) -> None:
        with pytest.raises(ValueError, match="message must be non-empty"):
            ParseError(exit_code=8, category="empty", message="", action="act")

    def test_empty_action_raises(self) -> None:
        with pytest.raises(ValueError, match="action must be non-empty"):
            ParseError(exit_code=8, category="empty", message="msg", action="")
