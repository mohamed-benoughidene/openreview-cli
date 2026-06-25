class TestExtractPageText:
    def test_extracts_text_with_sort_true(self) -> None:
        import pymupdf

        from openreview_cli.parsing.pdf_parser import extract_page_text

        with pymupdf.open() as doc:  # type: ignore[no-untyped-call]
            page = doc.new_page()
            page.insert_text((50, 50), "Hello World")
            text = extract_page_text(page)
            assert "Hello World" in text


class TestDetectHeadingsFromToc:
    def test_maps_toc_to_hierarchy(self) -> None:
        from openreview_cli.parsing.pdf_parser import detect_headings_from_toc

        toc = [
            [1, "Article I: Definitions", 1],
            [2, "Section 1.1: Confidential Information", 2],
            [2, "Section 1.2: Exclusions", 3],
            [1, "Article II: Obligations", 4],
        ]
        result = detect_headings_from_toc(toc)
        assert len(result) == 4
        assert result[0] == (1, "Article I: Definitions", 0)
        assert result[3] == (1, "Article II: Obligations", 3)

    def test_empty_toc_returns_empty_list(self) -> None:
        from openreview_cli.parsing.pdf_parser import detect_headings_from_toc

        assert detect_headings_from_toc([]) == []


class TestExtractFontProperties:
    def test_detects_bold_from_flags(self) -> None:
        from openreview_cli.parsing.pdf_parser import extract_font_properties

        span_bold = {"flags": 16, "size": 12, "font": "Helvetica-Bold"}
        props = extract_font_properties(span_bold)
        assert props["bold"] is True

    def test_detects_font_size(self) -> None:
        from openreview_cli.parsing.pdf_parser import extract_font_properties

        span = {"flags": 0, "size": 14.5, "font": "Helvetica"}
        props = extract_font_properties(span)
        assert props["size"] == 14.5

    def test_handles_zero_flags(self) -> None:
        from openreview_cli.parsing.pdf_parser import extract_font_properties

        span = {"flags": 0, "size": 10, "font": "Courier"}
        props = extract_font_properties(span)
        assert props["bold"] is False


class TestDetectNumberingPattern:
    def test_detects_article_roman(self) -> None:
        from openreview_cli.parsing.clause_detector import detect_numbering_pattern

        assert detect_numbering_pattern("Article I: Definitions") is not None

    def test_detects_section_decimal(self) -> None:
        from openreview_cli.parsing.clause_detector import detect_numbering_pattern

        assert detect_numbering_pattern("Section 3.1: Confidentiality") is not None

    def test_detects_parenthetical_letter(self) -> None:
        from openreview_cli.parsing.clause_detector import detect_numbering_pattern

        assert detect_numbering_pattern("(a) Exclusions") is not None

    def test_detects_parenthetical_roman(self) -> None:
        from openreview_cli.parsing.clause_detector import detect_numbering_pattern

        assert detect_numbering_pattern("(i) First sub-item") is not None

    def test_returns_none_for_plain_text(self) -> None:
        from openreview_cli.parsing.clause_detector import detect_numbering_pattern

        assert detect_numbering_pattern("This is just a sentence.") is None
