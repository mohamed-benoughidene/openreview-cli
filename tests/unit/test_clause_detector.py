from openreview_cli.parsing.clause_detector import (
    annotate_clauses,
    build_hierarchy,
    detect_clause_starts,
    detect_non_english,
    detect_numbering_pattern,
    detect_tofu,
    nupunkt_detect_boundaries,
)
from openreview_cli.parsing.models import Clause


def _clause(text: str, id: str = "clause-1") -> Clause:
    return Clause(
        id=id,
        title=None,
        text=text,
        level=0,
        parent_id=None,
        source_page=None,
        source_paragraph=None,
        source_span=None,
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


class TestAnnotateClauses:
    def test_annotate_clauses_flags_non_english_clause(self) -> None:
        clauses = [_clause("مرحبا", id="clause-1"), _clause("Hello", id="clause-2")]
        warnings = annotate_clauses(clauses)
        assert clauses[0].is_non_english is True
        assert clauses[1].is_non_english is False
        assert warnings == ["The contract appears to be in Arabic. Results may be less accurate"]

    def test_annotate_clauses_returns_cjk_and_cyrillic_names(self) -> None:
        clauses = [
            _clause("你好世界", id="clause-1"),
            _clause("Привет мир", id="clause-2"),
        ]
        warnings = annotate_clauses(clauses)
        assert set(warnings) == {
            "The contract appears to be in Chinese/Japanese/Korean. Results may be less accurate",
            "The contract appears to be in Russian/Ukrainian/Bulgarian. Results may be less accurate",
        }

    def test_annotate_clauses_dedupes_languages(self) -> None:
        clauses = [_clause("مرحبا", id="clause-1"), _clause("أهلا وسهلا", id="clause-2")]
        warnings = annotate_clauses(clauses)
        assert warnings == ["The contract appears to be in Arabic. Results may be less accurate"]

    def test_annotate_clauses_flags_tofu(self) -> None:
        clauses = [_clause("Some text with \ufffd replacement")]
        warnings = annotate_clauses(clauses)
        assert "Some text could not be read correctly. Results may contain errors" in warnings

    def test_annotate_clauses_clean_document_has_no_warnings(self) -> None:
        clauses = [_clause("Hello world", id="clause-1"), _clause("Another clause", id="clause-2")]
        warnings = annotate_clauses(clauses)
        assert warnings == []
        assert all(c.is_non_english is False for c in clauses)
