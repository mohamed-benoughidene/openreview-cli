import pytest

from openreview_cli.parsing.clause_detector import (
    build_hierarchy,
    detect_clause_starts,
    detect_non_english,
    detect_numbering_pattern,
    detect_tofu,
    nupunkt_detect_boundaries,
)


class TestNupunktBoundaries:
    def test_detects_sentence_boundaries(self) -> None:
        spans = nupunkt_detect_boundaries("This is a sentence. This is another.")
        assert len(spans) >= 2

    def test_handles_abbreviations(self) -> None:
        spans = nupunkt_detect_boundaries("The Corp. Inc. v. Smith case. It was settled.")
        assert len(spans) >= 2


class TestNumberingPattern:
    def test_article_roman(self) -> None:
        assert detect_numbering_pattern("Article I: Definitions") is not None

    def test_section_decimal(self) -> None:
        assert detect_numbering_pattern("Section 3.1: Confidentiality") is not None

    def test_parenthetical_letter(self) -> None:
        assert detect_numbering_pattern("(a) Exclusions") is not None

    def test_parenthetical_roman(self) -> None:
        assert detect_numbering_pattern("(i) First sub-item") is not None

    def test_plain_text_returns_none(self) -> None:
        assert detect_numbering_pattern("This is just a sentence.") is None


class TestDetectClauseStarts:
    def test_finds_article_starts(self) -> None:
        text = "Article I: Definitions\nSome text.\nArticle II: Obligations"
        starts = detect_clause_starts(text)
        assert len(starts) >= 2

    def test_empty_text_returns_empty(self) -> None:
        assert detect_clause_starts("") == []


class TestBuildHierarchy:
    def test_flat_document_fallback(self) -> None:
        boundaries = [(0, 20), (20, 40)]
        clauses = build_hierarchy(boundaries, [], [], 0, 0, "First sentence. Second one.")
        assert len(clauses) >= 1

    def test_empty_text_returns_empty(self) -> None:
        assert build_hierarchy([], [], [], 0, 0, "") == []


class TestDetectNonEnglish:
    def test_arabic_detected(self) -> None:
        assert detect_non_english("مرحبا بالعالم") is not None

    def test_cjk_detected(self) -> None:
        assert detect_non_english("你好世界") is not None

    def test_cyrillic_detected(self) -> None:
        assert detect_non_english("Привет мир") is not None

    def test_english_returns_none(self) -> None:
        assert detect_non_english("Hello World") is None


class TestDetectTofu:
    def test_tofu_detected(self) -> None:
        assert detect_tofu("Some \ufffd text") is True

    def test_no_tofu(self) -> None:
        assert detect_tofu("Normal text") is False

    def test_empty_string(self) -> None:
        assert detect_tofu("") is False
