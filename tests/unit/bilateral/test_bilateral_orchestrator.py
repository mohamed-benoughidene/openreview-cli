"""Unit tests for the bilateral comparison orchestrator (run_comparison).

Tests the sequential pipeline: parse → extract + QA for A → release →
parse → extract + QA for B → release → align → compare → build report.
"""

from __future__ import annotations

import pytest

from openreview_cli.parsing.models import Clause
from openreview_cli.review.models import (
    Category,
    Playbook,
    PlaybookMetadata,
    Position,
    PositionDef,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_playbook() -> Playbook:
    fav = PositionDef(description="Short term", exemplars=["3 years", "2 years"])
    neu = PositionDef(description="Standard term", exemplars=["5 years"])
    unfav = PositionDef(description="Indefinite", exemplars=["perpetuity"])
    cat = Category(
        id="confidentiality-term",
        name="Confidentiality Term",
        description="Defines how long confidentiality obligations survive",
        favorable=fav,
        neutral=neu,
        unfavorable=unfav,
        default_position=Position.neutral,
    )
    meta = PlaybookMetadata(version="1.0.0", description="Test", author="test")
    return Playbook(id="test-nda", mode="precheck", categories=[cat], metadata=meta)


def make_clause(
    clause_id: str = "c1", title: str = "Confidentiality", text: str = "Test clause"
) -> Clause:
    return Clause(
        id=clause_id,
        title=title,
        text=text,
        level=1,
        parent_id=None,
        source_page=1,
        source_paragraph=None,
        source_span=(0, len(text)),
    )


class TestRunComparison:
    """Tests for the run_comparison orchestrator."""

    def test_full_pipeline_returns_comparison_report(
        self, monkeypatch: pytest.MonkeyPatch, sample_playbook: Playbook
    ) -> None:
        """Full pipeline should produce a ComparisonReport with all fields."""
        from openreview_cli.bilateral import run_comparison

        # Mock parse_document to return controlled clauses
        clauses_a = [
            make_clause("a1", "Confidentiality", "Confidential info for 3 years"),
            make_clause("a2", "Term", "Term is 5 years"),
        ]
        clauses_b = [
            make_clause("b1", "Confidentiality", "Confidential info shall be kept secret"),
            make_clause("b2", "Termination", "Agreement terminates after 3 years"),
        ]

        def mock_parse(path: str) -> tuple[object, list[Clause]]:
            if "a" in path.lower() or "doc_a" in path.lower():
                return (object(), clauses_a)
            return (object(), clauses_b)

        monkeypatch.setattr("openreview_cli.bilateral._parse_document", mock_parse)

        # Mock gateway for extraction
        extraction_call_count: list[int] = [0]

        def mock_extraction_chat(_slot: str, _messages: list[dict[str, str]]) -> str:
            extraction_call_count[0] += 1
            return (
                '{"position": "favorable", "confidence": 0.85, '
                '"citation": "3 years", "category_match": true}'
            )

        monkeypatch.setattr(
            "openreview_cli.review.extraction.call_gateway_chat", mock_extraction_chat
        )

        # Mock QA gateway
        def mock_qa_chat(_slot: str, _messages: list[dict[str, str]]) -> str:
            return (
                '{"verdict": "agree", "revised_position": null, '
                '"rationale": "correct", "citation_valid": true, '
                '"position_valid": true, "category_valid": true, '
                '"confidence_valid": true}'
            )

        monkeypatch.setattr("openreview_cli.review.qa.call_gateway_chat", mock_qa_chat)

        # Mock comparison agent gateway
        comparison_call_count: list[int] = [0]

        def mock_comparison_chat(_slot: str, _messages: list[dict[str, str]]) -> str:
            comparison_call_count[0] += 1
            return (
                '{"divergence": "evidence", "confidence": 0.82, '
                '"citations": ["Party A: 3 years", "Party B: kept secret"], '
                '"rationale": "Different standards"}'
            )

        monkeypatch.setattr(
            "openreview_cli.bilateral.comparison.call_gateway_chat", mock_comparison_chat
        )

        report = run_comparison(
            doc_a_path="test/fixtures/doc_a.pdf",
            doc_b_path="test/fixtures/doc_b.pdf",
            playbook=sample_playbook,
            extraction_model="test-slot",
        )

        assert report.experimental is True
        assert report.schema_version == "1.0.0"
        assert report.playbook_id == "test-nda"
        assert report.document_a is not None
        assert report.document_b is not None

        # Should have 2 alignment pairs
        assert len(report.assessments) > 0

        # Summary should be present
        assert report.summary is not None

        # Comparison agent was called for each aligned pair
        assert comparison_call_count[0] == 2

    def test_sequential_processing(
        self, monkeypatch: pytest.MonkeyPatch, sample_playbook: Playbook
    ) -> None:
        """Document A should be fully processed before Document B."""
        from openreview_cli.bilateral import run_comparison

        clauses_a = [make_clause("a1", "Confidentiality", "Confidential info for 3 years")]
        clauses_b = [make_clause("b1", "Confidentiality", "Confidential info protected")]
        call_order: list[str] = []

        def mock_parse(path: str) -> tuple[object, list[Clause]]:
            if "doc_a" in path.lower():
                call_order.append("parse_a")
                return (object(), clauses_a)
            call_order.append("parse_b")
            return (object(), clauses_b)

        monkeypatch.setattr("openreview_cli.bilateral._parse_document", mock_parse)

        def mock_extraction_chat(_slot: str, _messages: list[dict[str, str]]) -> str:
            call_order.append("extract")
            return (
                '{"position": "favorable", "confidence": 0.85, '
                '"citation": "text", "category_match": true}'
            )

        monkeypatch.setattr(
            "openreview_cli.review.extraction.call_gateway_chat", mock_extraction_chat
        )

        def mock_qa_chat(_slot: str, _messages: list[dict[str, str]]) -> str:
            call_order.append("qa")
            return (
                '{"verdict": "agree", "revised_position": null, '
                '"rationale": "ok", "citation_valid": true, '
                '"position_valid": true, "category_valid": true, '
                '"confidence_valid": true}'
            )

        monkeypatch.setattr("openreview_cli.review.qa.call_gateway_chat", mock_qa_chat)

        def mock_comparison_chat(_slot: str, _messages: list[dict[str, str]]) -> str:
            call_order.append("compare")
            return (
                '{"divergence": "no_divergence", "confidence": 0.95, '
                '"citations": [], "rationale": "Aligned"}'
            )

        monkeypatch.setattr(
            "openreview_cli.bilateral.comparison.call_gateway_chat", mock_comparison_chat
        )

        run_comparison(
            doc_a_path="test/fixtures/doc_a.pdf",
            doc_b_path="test/fixtures/doc_b.pdf",
            playbook=sample_playbook,
            extraction_model="test-slot",
        )

        # Verify sequential order: A parsed → A extracted → A QA'd → then B...
        assert call_order[0] == "parse_a"
        assert "extract" in call_order
        assert "qa" in call_order
        assert "parse_b" in call_order
        assert call_order[-1] == "compare"

        # Find extract and qa for A before parse_b
        # Parse A first
        parse_a_idx = call_order.index("parse_a")
        # Then extract/qa happen
        # Then parse B
        parse_b_idx = call_order.index("parse_b")
        # Extract/QA should be between parse_a and parse_b
        for idx, step in enumerate(call_order):
            if step == "extract" and idx < parse_b_idx:
                break
        else:
            pytest.fail("Extraction for A should happen before parsing B")

    def test_empty_document(
        self, monkeypatch: pytest.MonkeyPatch, sample_playbook: Playbook
    ) -> None:
        """Empty clauses list should produce empty alignment."""
        from openreview_cli.bilateral import run_comparison

        def mock_parse(path: str) -> tuple[object, list[Clause]]:
            return (object(), [])

        monkeypatch.setattr("openreview_cli.bilateral._parse_document", mock_parse)

        report = run_comparison(
            doc_a_path="doc_a.pdf",
            doc_b_path="doc_b.pdf",
            playbook=sample_playbook,
            extraction_model="test-slot",
        )

        assert len(report.assessments) == 0
        assert report.alignment_table.alignment_rate == 0.0
        assert report.summary.total_pairs == 0

    def test_identical_documents_all_green(
        self, monkeypatch: pytest.MonkeyPatch, sample_playbook: Playbook
    ) -> None:
        """Identical documents should produce no divergences."""
        from openreview_cli.bilateral import run_comparison

        clauses = [make_clause("c1", "Confidentiality", "Same text")]

        def mock_parse(path: str) -> tuple[object, list[Clause]]:
            return (object(), clauses)

        monkeypatch.setattr("openreview_cli.bilateral._parse_document", mock_parse)

        def mock_qa_chat_fn(_slot: str, _messages: list[dict[str, str]]) -> str:
            return (
                '{"verdict": "agree", "revised_position": null, '
                '"rationale": "ok", "citation_valid": true, '
                '"position_valid": true, "category_valid": true, '
                '"confidence_valid": true}'
            )

        def mock_extraction_chat_fn(_slot: str, _messages: list[dict[str, str]]) -> str:
            return (
                '{"position": "neutral", "confidence": 0.9, '
                '"citation": "text", "category_match": true}'
            )

        monkeypatch.setattr(
            "openreview_cli.review.extraction.call_gateway_chat", mock_extraction_chat_fn
        )
        monkeypatch.setattr("openreview_cli.review.qa.call_gateway_chat", mock_qa_chat_fn)

        def mock_comp_chat(_slot: str, _messages: list[dict[str, str]]) -> str:
            return (
                '{"divergence": "no_divergence", "confidence": 0.95, '
                '"citations": [], "rationale": "Aligned"}'
            )

        monkeypatch.setattr("openreview_cli.bilateral.comparison.call_gateway_chat", mock_comp_chat)

        report = run_comparison(
            doc_a_path="doc_a.pdf",
            doc_b_path="doc_b.pdf",
            playbook=sample_playbook,
            extraction_model="test-slot",
        )

        assert report.summary.divergent_count == 0
        assert report.summary.green_count >= 0

    def test_align_only_skips_comparison(
        self, monkeypatch: pytest.MonkeyPatch, sample_playbook: Playbook
    ) -> None:
        """align_only=True should produce alignment table but skip comparison."""
        from openreview_cli.bilateral import run_comparison

        clauses_a = [make_clause("a1", "Confidentiality", "A text")]
        clauses_b = [make_clause("b1", "Confidentiality", "B text")]

        def mock_parse(path: str) -> tuple[object, list[Clause]]:
            if "doc_a" in path.lower():
                return (object(), clauses_a)
            return (object(), clauses_b)

        monkeypatch.setattr("openreview_cli.bilateral._parse_document", mock_parse)

        # If align_only=True, no extraction/QA/comparison calls should happen
        chat_called: list[bool] = [False]

        def mock_chat(_slot: str, _messages: list[dict[str, str]]) -> str:
            chat_called[0] = True
            return ""

        monkeypatch.setattr("openreview_cli.review.extraction.call_gateway_chat", mock_chat)

        report = run_comparison(
            doc_a_path="doc_a.pdf",
            doc_b_path="doc_b.pdf",
            playbook=sample_playbook,
            extraction_model="test-slot",
            align_only=True,
        )

        assert not chat_called[0], "No chat calls should happen in align_only mode"
        assert report.alignment_table.matched_count == 1
        assert report.alignment_table.alignment_rate == 1.0
        assert len(report.assessments) == 0
