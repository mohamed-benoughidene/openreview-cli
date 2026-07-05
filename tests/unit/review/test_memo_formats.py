"""Unit tests for memo format renderers (Markdown, JSON, DOCX)."""

from __future__ import annotations

import json

from openreview_cli.review.memo.formats import (
    render_docx,
    render_json,
    render_markdown,
)
from openreview_cli.review.memo.models import (
    MemoCitation,
    MemoClause,
    MemoReport,
    MemoSummary,
)


def _make_memo_report() -> MemoReport:
    summary = MemoSummary(
        recommendation="revise",
        clauses_checked=4,
        matches=2,
        differences=2,
        confidence_avg=0.76,
    )
    clauses = [
        MemoClause(
            id="c1",
            title="Confidentiality Term",
            playbook_requirement="Preferred: 3 years",
            contract_text="The confidentiality term shall be 3 years from the Effective Date.",
            assessment="match",
            color="green",
            confidence=0.92,
            citation=MemoCitation(clause_id="§3.1", paragraph_index=0),
        ),
        MemoClause(
            id="c2",
            title="Permitted Disclosures",
            playbook_requirement="Acceptable: with NDA",
            contract_text="Disclosures to employees with need-to-know.",
            assessment="match",
            color="amber",
            confidence=0.68,
            severity="minor",
        ),
        MemoClause(
            id="c3",
            title="Governing Law",
            playbook_requirement="Preferred: Delaware",
            contract_text="This agreement shall be governed by the laws of California.",
            assessment="difference",
            color="red",
            confidence=0.15,
            citation=MemoCitation(clause_id="§12.1", paragraph_index=1),
            severity="major",
        ),
        MemoClause(
            id="c4",
            title="Indemnification",
            playbook_requirement="Walkaway: No indemnification",
            contract_text="Indemnification obligations survive termination.",
            assessment="difference",
            color="amber",
            confidence=0.55,
        ),
    ]
    return MemoReport(
        memo_version="1.0",
        mode="precheck",
        document_name="nda-sample.pdf",
        playbook_name="precheck-nda-v1",
        playbook_version="1.2.0",
        review_date="2026-07-05T14:30:22+00:00",
        overall=summary,
        clauses=clauses,
        disclaimer="AI-generated review. Not legal advice. Consult a qualified attorney.",
    )


class TestRenderMarkdown:
    def test_output_is_string(self) -> None:
        memo = _make_memo_report()
        output = render_markdown(memo)
        assert isinstance(output, str)
        assert len(output) > 100

    def test_contains_header(self) -> None:
        memo = _make_memo_report()
        output = render_markdown(memo)
        assert "# Memo Export: precheck" in output
        assert "nda-sample.pdf" in output
        assert "precheck-nda-v1" in output
        assert "v1.2.0" in output or "1.2.0" in output

    def test_contains_summary_table(self) -> None:
        memo = _make_memo_report()
        output = render_markdown(memo)
        assert "4" in output  # clauses_checked
        assert "2" in output  # matches

    def test_contains_per_clause_badges(self) -> None:
        memo = _make_memo_report()
        output = render_markdown(memo)
        assert "✅" in output
        assert "⚠️" in output
        assert "❌" in output

    def test_contains_confidence_bars(self) -> None:
        memo = _make_memo_report()
        output = render_markdown(memo)
        assert "█" in output and "░" in output

    def test_contains_recommendation(self) -> None:
        memo = _make_memo_report()
        output = render_markdown(memo)
        assert "revise" in output.lower()

    def test_contains_disclaimer(self) -> None:
        memo = _make_memo_report()
        output = render_markdown(memo)
        assert "Disclaimer" in output

    def test_contains_playbook_version(self) -> None:
        memo = _make_memo_report()
        output = render_markdown(memo)
        assert "1.2.0" in output

    def test_no_differences_message(self) -> None:
        summary = MemoSummary(
            recommendation="approve",
            clauses_checked=2,
            matches=2,
            differences=0,
            confidence_avg=0.95,
        )
        memo = MemoReport(
            memo_version="1.0",
            mode="precheck",
            document_name="doc.pdf",
            playbook_name="pb",
            playbook_version="1.0",
            review_date="2026-01-01",
            overall=summary,
            clauses=[],
            disclaimer="D",
        )
        output = render_markdown(memo)
        assert "No differences found" in output


class TestRenderJson:
    def test_output_is_valid_json(self) -> None:
        memo = _make_memo_report()
        output = render_json(memo)
        data = json.loads(output)
        assert isinstance(data, dict)

    def test_contains_required_top_keys(self) -> None:
        memo = _make_memo_report()
        output = render_json(memo)
        data = json.loads(output)
        assert "memo_version" in data
        assert "mode" in data
        assert "document" in data
        assert "playbook" in data
        assert "review_date" in data
        assert "overall" in data
        assert "clauses" in data
        assert "disclaimer" in data

    def test_playbook_structure(self) -> None:
        memo = _make_memo_report()
        output = render_json(memo)
        data = json.loads(output)
        assert data["playbook"]["name"] == "precheck-nda-v1"
        assert data["playbook"]["version"] == "1.2.0"

    def test_document_structure(self) -> None:
        memo = _make_memo_report()
        output = render_json(memo)
        data = json.loads(output)
        assert data["document"]["name"] == "nda-sample.pdf"

    def test_overall_structure(self) -> None:
        memo = _make_memo_report()
        output = render_json(memo)
        data = json.loads(output)
        overall = data["overall"]
        assert "recommendation" in overall
        assert "clauses_checked" in overall
        assert "matches" in overall
        assert "differences" in overall
        assert "confidence_avg" in overall

    def test_clause_structure(self) -> None:
        memo = _make_memo_report()
        output = render_json(memo)
        data = json.loads(output)
        assert len(data["clauses"]) == 4
        clause = data["clauses"][0]
        assert "id" in clause
        assert "assessment" in clause
        assert "color" in clause
        assert "confidence" in clause
        assert "citation" in clause
        assert clause["id"] == "c1"
        assert clause["color"] == "green"

    def test_memo_version_value(self) -> None:
        memo = _make_memo_report()
        output = render_json(memo)
        data = json.loads(output)
        assert data["memo_version"] == "1.0"

    def test_tier_info_optional(self) -> None:
        memo = _make_memo_report()
        output = render_json(memo)
        data = json.loads(output)
        # tier_info may or may not be present depending on whether it was set
        assert "tier_info" in data


class TestRenderDocx:
    def test_returns_document_object(self) -> None:
        memo = _make_memo_report()
        doc = render_docx(memo)
        assert doc is not None
        assert hasattr(doc, "save")

    def test_has_tables(self) -> None:
        memo = _make_memo_report()
        doc = render_docx(memo)
        assert len(doc.tables) > 0

    def test_has_disclaimer(self) -> None:
        memo = _make_memo_report()
        doc = render_docx(memo)
        disclaimer_found = any("Disclaimer" in p.text for p in doc.paragraphs)
        assert disclaimer_found

    def test_has_summary_table(self) -> None:
        memo = _make_memo_report()
        doc = render_docx(memo)
        # Check tables exist with clause data
        texts = []
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    texts.append(cell.text)
        all_text = " ".join(texts)
        assert "Clauses Checked" in all_text or "4" in all_text

    def test_has_heading(self) -> None:
        memo = _make_memo_report()
        doc = render_docx(memo)
        # Check for heading about memo export
        headings = [p.text for p in doc.paragraphs if p.style.name.startswith("Heading")]
        assert len(headings) > 0

    def test_document_not_empty(self) -> None:
        memo = _make_memo_report()
        doc = render_docx(memo)
        assert len(doc.paragraphs) > 0
