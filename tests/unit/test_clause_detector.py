from openreview_cli.graph.builder import ClauseHierarchyBuilder
from openreview_cli.graph.models import EdgeType
from openreview_cli.parsing.clause_detector import (
    annotate_clauses,
    build_hierarchy,
    detect_clause_starts,
    detect_non_english,
    detect_numbering_pattern,
    detect_tofu,
    link_parent_ids,
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

    def test_bare_dotted_number_is_a_clause_start_with_a_child_item(self) -> None:
        """Real contracts number clauses ``1.1 Title`` (no trailing dot).

        Regression: the dot-alternative used to require a trailing dot
        (``1.1.``), so ``1.1 Confidentiality`` was never a start and got folded
        into the preceding clause -- the clause hierarchy, and therefore the
        graph's ``parent_child`` edges, came out thinner than reality.
        """
        text = (
            "1.1 Confidentiality\n"
            "The Receiving Party shall keep the information secret.\n"
            "1.2 Term\n"
            "(a) This Agreement begins on the Effective Date.\n"
        )
        starts = detect_clause_starts(text)
        start_lines = [text[offset:].splitlines()[0] for offset, _ in starts]
        assert start_lines == [
            "1.1 Confidentiality",
            "1.2 Term",
            "(a) This Agreement begins on the Effective Date.",
        ]

        # The start regex and the level rules must agree: ``1.1`` is level 1,
        # its nested ``(a)`` item is level 2, exactly as the parser links them.
        clauses = build_hierarchy([], starts, [], 1, 0, text)
        matches = [detect_numbering_pattern(c.text.splitlines()[0]) for c in clauses]
        levels = [m["level"] if m else None for m in matches]
        assert levels == [1, 1, 2]
        link_parent_ids(clauses, [], levels=levels)
        assert clauses[0].parent_id is None
        assert clauses[1].parent_id is None
        assert clauses[2].parent_id == clauses[1].id

    def test_existing_numbering_forms_still_start_clauses(self) -> None:
        text = (
            "ARTICLE I: Definitions\n"
            "Section 1.1 Confidentiality obligations apply.\n"
            "Clause 4 Payment\n"
            "1. Payment\n"
            "2. Payment\n"
            "1.1 Late payment\n"
            "1.1.1. Trailing dot sub-clause\n"
            "2.3.4 Sub-sub-clause\n"
            "1.1.107 Definition\n"
            "(a) Exclusions apply.\n"
            "(1) Numbered item\n"
            "(i) First sub-item\n"
        )
        start_lines = [text[offset:].splitlines()[0] for offset, _ in detect_clause_starts(text)]
        assert start_lines == [
            "ARTICLE I: Definitions",
            "Section 1.1 Confidentiality obligations apply.",
            "Clause 4 Payment",
            "1. Payment",
            "2. Payment",
            "1.1 Late payment",
            "1.1.1. Trailing dot sub-clause",
            "2.3.4 Sub-sub-clause",
            "1.1.107 Definition",
            "(a) Exclusions apply.",
            "(1) Numbered item",
            "(i) First sub-item",
        ]

    def test_dotted_number_inside_a_sentence_is_not_a_clause_start(self) -> None:
        """A number that merely appears mid-line must never split a clause."""
        text = (
            "The obligations described in 1.1 Confidentiality apply to both parties.\n"
            "See also 2.3.4 Term of the schedule, and 1.5.1 as amended.\n"
        )
        assert detect_clause_starts(text) == []

    def test_numeric_literals_at_line_start_are_not_clause_numbers(self) -> None:
        """Years, long decimals and document numbers must not start clauses.

        These are the lines the three-digit cap on each dotted component exists
        for; every one of them is a real CUAD line, not a contrived example.
        Without the cap they would split the clause they sit in and, because
        ``detect_numbering_pattern`` agreed with the old, uncapped rule, they
        would claim a numbering level too.
        """
        text = (
            "1.3.2019 - 31.12.2019: All grades at the price below.\n"
            "1162967.3\n"
            "2510.03 D- Guest Kitchens - Install tile.\n"
            "01.02.2024 Settlement Date payment.\n"
        )
        assert detect_clause_starts(text) == []
        for line in text.splitlines():
            assert detect_numbering_pattern(line) is None, line

    def test_bare_decimal_at_line_start_is_pinned_as_agreeing_with_the_level_rule(self) -> None:
        """A short decimal is syntactically identical to a two-level clause number.

        ``3.14`` is indistinguishable from ``1.1`` without looking at the
        surrounding document, so the two rules deliberately agree: the line is a
        clause start *and* carries numbering level 1. The cost is at most one
        extra boundary; disagreeing is worse, because a levelled clause that is
        not a start (the bug this file fixes) or a start with no level (the
        parser would fold it in anyway) both distort the hierarchy.
        """
        text = "3.14 is the ratio used in the calculation.\n"
        assert [text[offset:].splitlines()[0] for offset, _ in detect_clause_starts(text)] == [
            "3.14 is the ratio used in the calculation."
        ]
        level = detect_numbering_pattern("3.14 is the ratio used in the calculation.")
        assert level is not None and level["level"] == 1

    def test_plain_integer_with_trailing_dot_is_unchanged_by_this_fix(self) -> None:
        """``2024.`` was already a start through the plain ``N.`` form.

        A year followed by a full stop cannot be told apart from a top-level
        ``1.`` clause number by this detector, and that behaviour predates the
        bare-dotted-number fix -- pinning it here keeps the change honest about
        what it did and did not alter.
        """
        text = "2024. All rights reserved.\n"
        start_lines = [text[offset:].splitlines()[0] for offset, _ in detect_clause_starts(text)]
        assert start_lines == ["2024. All rights reserved."]

    def test_start_rule_and_level_rule_agree_line_by_line(self) -> None:
        """The segmentation rule and the level rule must never disagree.

        A line that ``detect_numbering_pattern`` levels but ``detect_clause_starts``
        does not split on is exactly the bug this file fixes: the number claims a
        rung of the hierarchy while the text stays folded into the clause above.
        The converse -- a start that carries no level -- would make the parser
        fold the line in anyway. The two rules share ``_DOTTED_NUMBER_END``, so
        every separator the level rule tolerates (``:``, ``)``, ``-``, ``/``,
        ``,`` ...) is a start here too, not just whitespace. Lines are checked with
        a trailing newline, as they carry in a real document.
        """
        levelled = {
            "ARTICLE I: Definitions": 0,
            "Section 1.1 Confidentiality obligations apply.": 1,
            "Clause 4 Payment": 0,
            "1. Payment": 0,
            "1.1 Confidentiality": 1,
            "1.1.1. Trailing dot sub-clause": 1,
            "2.3.4 Sub-sub-clause": 1,
            "1.1.107 Definition": 1,
            "9.02.5.1.4 Deeply nested term": 1,
            # Separators other than whitespace: the level rule always tolerated
            # these, so before the trailer was shared these lines were levelled
            # but not split on -- the exact bug class this file fixes.
            "1.1: Payment": 1,
            "1.1) Payment": 1,
            "1.2.3-beta tag": 1,
            "1.1/Exhibits": 1,
            "1.1, Definitions": 1,
            "(a) Exclusions apply.": 2,
            "(i) First sub-item": 2,
            "(1) Numbered item": 2,
        }
        not_levelled = [
            "1.3.2019 - 31.12.2019: All grades at the price below.",
            "1162967.3",
            "2510.03 D- Guest Kitchens - Install tile.",
            "01.02.2024 Settlement Date payment.",
            "1.1X Glued to a word, so not a number at all.",
            "The obligations described in 1.1 Confidentiality apply.",
            "See also 2.3.4 Term of the schedule.",
            "This is just a sentence.",
        ]

        for line, expected_level in levelled.items():
            match = detect_numbering_pattern(line)
            assert match is not None, line
            assert match["level"] == expected_level, line
            assert detect_clause_starts(line + "\n"), line

        for line in not_levelled:
            assert detect_numbering_pattern(line) is None, line
            assert detect_clause_starts(line + "\n") == [], line

    def test_dotted_number_at_end_of_text_still_starts_a_clause(self) -> None:
        """The last line needs no trailing newline to be a start."""
        text = "The parties agree as follows.\n1.1 Term"
        start_lines = [text[offset:].splitlines()[0] for offset, _ in detect_clause_starts(text)]
        assert start_lines == ["1.1 Term"]
        level = detect_numbering_pattern("1.1 Term")
        assert level is not None and level["level"] == 1

    def test_ip_like_number_at_line_start_is_a_known_residual(self) -> None:
        """``192.168.1.1`` is shaped exactly like the real clause number ``4.1.2.1``.

        Four all-short components cannot be told apart from a deeply nested
        clause number, and rejecting four-component numbers would drop real
        headings every deep contract has, so this stays a clause start (as the
        level rule already treated it before this fix). Pinned so the residual is
        a documented decision rather than a surprise.
        """
        text = "192.168.1.1 Upstream host\n"
        assert detect_clause_starts(text)
        level = detect_numbering_pattern("192.168.1.1 Upstream host")
        assert level is not None and level["level"] == 1

    def test_trailer_widening_leaves_the_documented_residuals_unchanged(self) -> None:
        """Sharing the trailer widens the separator only; the residuals stay as they were.

        ``1.50`` (a currency amount) and ``10.0.0.1`` (an address) were already
        clause starts with level 1 before the trailer was shared -- a space follows
        both -- so accepting any non-word separator leaves them unchanged. The
        rejects stay rejects: the three-digit cap keeps ``1162967.3`` and
        ``2510.03`` from matching either rule, and the line-start anchor keeps a
        mid-sentence ``in 1.1`` from splitting its clause.
        """
        for line in ("1.50 USD per unit", "10.0.0.1 gateway"):
            assert detect_clause_starts(line + "\n"), line
            level = detect_numbering_pattern(line)
            assert level is not None and level["level"] == 1, line

        for line in ("1162967.3", "2510.03 D- Guest Kitchens - Install tile."):
            assert detect_clause_starts(line + "\n") == [], line
            assert detect_numbering_pattern(line) is None, line

        mid_sentence = "The obligations described in 1.1 Confidentiality apply to both parties.\n"
        assert detect_clause_starts(mid_sentence) == []
        assert detect_numbering_pattern(mid_sentence.strip()) is None


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


class TestLinkParentIds:
    """T2.1: the parser -> graph bridge, exercised the way the parser calls it.

    ``link_parent_ids`` is the only function that turns numbering levels into
    ``Clause.parent_id`` links, and the graph's ``parent_child`` edges depend
    entirely on it -- yet every graph unit test builds ``Clause`` objects with
    ``parent_id`` already set, so they prove nothing about this path. This test
    mirrors ``PdfParser.parse`` end to end: ``detect_clause_starts`` ->
    ``build_hierarchy`` -> per-clause numbering level -> ``link_parent_ids`` ->
    ``ClauseHierarchyBuilder().build``.
    """

    def test_numbered_text_links_parents_and_survives_into_the_graph(self) -> None:
        page_text = (
            "ARTICLE I: Definitions\n"
            "Section 1.1 Confidentiality obligations apply.\n"
            "(a) Exclusions to the definition apply.\n"
        )

        # Exactly the PDF parser's steps (parsing/pdf_parser.py:171-178):
        # segment, build clauses, read each clause's numbering level (the
        # parser's ``_extract_numbering_level`` wraps ``detect_numbering_pattern``),
        # then link parents across the page.
        clause_starts = detect_clause_starts(page_text)
        clauses = build_hierarchy([], clause_starts, [], 0, 0, page_text)
        matches = [detect_numbering_pattern(c.text.splitlines()[0]) for c in clauses]
        levels = [m["level"] if m else None for m in matches]
        link_parent_ids(clauses, [], levels=levels)

        by_first_line = {c.text.splitlines()[0]: c for c in clauses}
        article = by_first_line["ARTICLE I: Definitions"]
        section = by_first_line["Section 1.1 Confidentiality obligations apply."]
        item = by_first_line["(a) Exclusions to the definition apply."]

        # The links the graph depends on: ARTICLE I -> Section 1.1 -> (a).
        assert article.parent_id is None
        assert section.parent_id == article.id
        assert item.parent_id == section.id

        # ...and they survive into the graph as parent_child edges.
        graph = ClauseHierarchyBuilder().build(clauses)
        parent_child = {
            (edge.source_id, edge.target_id)
            for edge in graph.edges
            if edge.edge_type == EdgeType.parent_child
        }
        assert (article.id, section.id) in parent_child
        assert (section.id, item.id) in parent_child
