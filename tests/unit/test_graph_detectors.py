from __future__ import annotations

from openreview_cli.graph.detectors import (
    CrossReferenceDetector,
    DefinitionDetector,
)
from openreview_cli.parsing.models import Clause


class TestCrossReferenceDetector:
    def test_default_pattern_matches_section_dot_number(self) -> None:
        detector = CrossReferenceDetector()
        refs = detector.detect("as set forth in Section 3.2")
        assert "3.2" in refs

    def test_default_pattern_matches_plain_section(self) -> None:
        detector = CrossReferenceDetector()
        refs = detector.detect("pursuant to Section 5")
        assert len(refs) >= 1

    def test_default_pattern_match_ref_forms(self) -> None:
        detector = CrossReferenceDetector()
        refs = detector.detect(
            "as described in Section 7.1, as set forth in Section 8.2, as provided in Section 9"
        )
        assert "7.1" in refs
        assert "8.2" in refs

    def test_no_match_returns_empty(self) -> None:
        detector = CrossReferenceDetector()
        refs = detector.detect("No references here.")
        assert refs == []

    def test_default_pattern_matches_article(self) -> None:
        """Verify Article references match via default Section pattern."""
        detector = CrossReferenceDetector()
        # Default patterns match Section references, not Article prefix
        refs = detector.detect("As per Article 12")
        assert refs == []


class TestDefinitionDetector:
    def test_detects_quoted_means(self) -> None:
        detector = DefinitionDetector()
        clause = Clause(
            id="c1",
            title=None,
            text='"Confidential Information" means any non-public data.',
            level=0,
            parent_id=None,
            source_page=None,
            source_paragraph=None,
            source_span=None,
        )
        defs = detector.extract_definitions([clause])
        assert "Confidential Information" in defs
        assert defs["Confidential Information"] == "c1"

    def test_detects_single_quoted_shall_mean(self) -> None:
        detector = DefinitionDetector()
        clause = Clause(
            id="c2",
            title=None,
            text="'Term' shall mean the defined term.",
            level=0,
            parent_id=None,
            source_page=None,
            source_paragraph=None,
            source_span=None,
        )
        defs = detector.extract_definitions([clause])
        assert "Term" in defs

    def test_detects_refers_to(self) -> None:
        detector = DefinitionDetector()
        clause = Clause(
            id="c3",
            title=None,
            text='"Widget" refers to the product.',
            level=0,
            parent_id=None,
            source_page=None,
            source_paragraph=None,
            source_span=None,
        )
        defs = detector.extract_definitions([clause])
        assert "Widget" in defs

    def test_capitalised_term_heuristic(self) -> None:
        detector = DefinitionDetector()
        clause = Clause(
            id="c4",
            title=None,
            text="Confidential Information means non-public data.",
            level=0,
            parent_id=None,
            source_page=None,
            source_paragraph=None,
            source_span=None,
        )
        defs = detector.extract_definitions([clause])
        assert "Confidential Information" in defs

    def test_count_references(self) -> None:
        detector = DefinitionDetector()
        definitions = {"Confidential Information": "c1", "Term": "c2"}
        refs = detector.count_references(
            'The "Confidential Information" and "Term" are defined.',
            definitions,
        )
        assert len(refs) == 2
        terms = {r[0] for r in refs}
        assert terms == {"Confidential Information", "Term"}

    def test_extract_definitions_returns_dict(self) -> None:
        detector = DefinitionDetector()
        clauses = [
            Clause(
                id="c1",
                title=None,
                text='"TermA" means something.',
                level=0,
                parent_id=None,
                source_page=None,
                source_paragraph=None,
                source_span=None,
            ),
            Clause(
                id="c2",
                title=None,
                text='"TermB" shall mean something else.',
                level=0,
                parent_id=None,
                source_page=None,
                source_paragraph=None,
                source_span=None,
            ),
        ]
        defs = detector.extract_definitions(clauses)
        assert defs == {"TermA": "c1", "TermB": "c2"}
