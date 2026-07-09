"""Unit tests for ComparisonStage adapter.

Tests validate the stage reads aligned pairs + assessments from context,
delegates to ``compare_pair``, and writes ``paired_assessments``.
"""

from __future__ import annotations

import asyncio
from unittest.mock import Mock, patch

import pytest

from openreview_cli.pipeline.adapters.comparison import ComparisonStage
from openreview_cli.pipeline.base import PipelineContext, Stage


@pytest.fixture
def mock_clause() -> Mock:
    c = Mock(spec=["id", "text", "title", "level", "source_span", "source_paragraph"])
    c.id = "1"
    c.text = "Party A shall indemnify"
    c.title = "Indemnification"
    c.level = 1
    c.source_span = (0, 100)
    c.source_paragraph = 0
    return c


@pytest.fixture
def mock_assessment() -> Mock:
    a = Mock(spec=["clause_id", "text", "playbook_category", "position", "confidence", "rationale"])
    a.clause_id = "1"
    a.text = "Party A shall indemnify"
    a.playbook_category = "indemnification"
    a.position = "preferred"
    a.confidence = 0.9
    a.rationale = "Standard indemnification clause"
    return a


@pytest.fixture
def mock_alignment(mock_clause: Mock) -> Mock:
    a = Mock(spec=["pair_id", "clause_a", "clause_b", "method", "score"])
    a.pair_id = "A1-B1"
    a.clause_a = mock_clause
    a.clause_b = mock_clause
    a.method = "exact"
    a.score = 1.0
    return a


class TestComparisonStageContract:
    """Validate ComparisonStage conforms to Stage contract."""

    def test_name_and_critical(self) -> None:
        stage = ComparisonStage(model="extraction")
        assert stage.name == "comparison"
        assert stage.critical is False
        assert isinstance(stage, Stage)

    def test_default_comparison_model(self) -> None:
        stage = ComparisonStage(model="extraction")
        assert stage._model == "extraction"
        assert stage._comparison_model is None

        stage2 = ComparisonStage(model="extraction", comparison_model="comparison")
        assert stage2._comparison_model == "comparison"

    def test_should_skip_default(self) -> None:
        stage = ComparisonStage(model="extraction")
        assert stage.should_skip({}) is False

    def test_cleanup_noop(self) -> None:
        stage = ComparisonStage(model="extraction")
        # Should not raise
        stage.cleanup({})


class TestComparisonStageRun:
    """Validate run() reads ctx keys and delegates to compare_pair."""

    def test_empty_ctx_raises_key_error(self) -> None:
        stage = ComparisonStage(model="extraction")
        with pytest.raises(KeyError, match="aligned_pairs"):
            asyncio.run(stage.run({}))

    def test_empty_pairs_returns_empty_list(self) -> None:
        stage = ComparisonStage(model="extraction")
        ctx: PipelineContext = {"aligned_pairs": []}
        result = asyncio.run(stage.run(ctx))
        assert result is not None
        assert "paired_assessments" in result
        assert result["paired_assessments"] == []

    def test_delegates_to_compare_pair(
        self,
        mock_alignment: Mock,
        mock_assessment: Mock,
    ) -> None:
        """Stage calls compare_pair for each aligned pair."""
        stage = ComparisonStage(model="extraction")

        aligned_pairs = [
            {
                "alignment": mock_alignment,
                "party_a_assessment": mock_assessment,
                "party_b_assessment": mock_assessment,
                "playbook_category": None,
            }
        ]

        mock_paired = Mock(spec=["pair_id", "divergence"])
        mock_paired.pair_id = "A1-B1"
        mock_paired.divergence = "aligned"

        with patch(
            "openreview_cli.bilateral.comparison.compare_pair",
            return_value=mock_paired,
        ) as mock_fn:
            ctx: PipelineContext = {
                "aligned_pairs": aligned_pairs,
                "model": "extraction",
            }
            result = asyncio.run(stage.run(ctx))

        assert result is not None
        assert "paired_assessments" in result
        assert len(result["paired_assessments"]) == 1
        assert result["paired_assessments"][0] is mock_paired
        mock_fn.assert_called_once_with(
            alignment=mock_alignment,
            party_a_assessment=mock_assessment,
            party_b_assessment=mock_assessment,
            playbook_category=None,
            model="extraction",
            comparison_model=None,
        )

    def test_uses_comparison_model_from_init(
        self,
        mock_alignment: Mock,
        mock_assessment: Mock,
    ) -> None:
        """comparison_model from __init__ is passed through."""
        stage = ComparisonStage(model="extraction", comparison_model="comparison")

        aligned_pairs = [
            {
                "alignment": mock_alignment,
                "party_a_assessment": mock_assessment,
                "party_b_assessment": mock_assessment,
                "playbook_category": None,
            }
        ]

        mock_paired = Mock(spec=["pair_id", "divergence"])
        mock_paired.pair_id = "A1-B1"

        with patch(
            "openreview_cli.bilateral.comparison.compare_pair",
            return_value=mock_paired,
        ) as mock_fn:
            ctx: PipelineContext = {"aligned_pairs": aligned_pairs}
            asyncio.run(stage.run(ctx))

        mock_fn.assert_called_once()
        _call_kwargs = mock_fn.call_args.kwargs
        assert _call_kwargs["comparison_model"] == "comparison"

    def test_multiple_pairs(
        self,
        mock_alignment: Mock,
        mock_assessment: Mock,
    ) -> None:
        """Multiple aligned pairs all get processed."""
        stage = ComparisonStage(model="extraction")

        # Two pairs with different IDs
        align1 = Mock(spec=["pair_id", "clause_a", "clause_b", "method", "score"])
        align1.pair_id = "A1-B1"
        align1.clause_a = mock_clause = mock_alignment.clause_a
        align1.clause_b = mock_clause
        align1.method = "exact"
        align1.score = 1.0

        align2 = Mock(spec=["pair_id", "clause_a", "clause_b", "method", "score"])
        align2.pair_id = "A2-B2"
        align2.clause_a = mock_clause
        align2.clause_b = mock_clause
        align2.method = "fuzzy"
        align2.score = 0.85

        aligned_pairs = [
            {
                "alignment": align1,
                "party_a_assessment": mock_assessment,
                "party_b_assessment": mock_assessment,
                "playbook_category": None,
            },
            {
                "alignment": align2,
                "party_a_assessment": mock_assessment,
                "party_b_assessment": mock_assessment,
                "playbook_category": None,
            },
        ]

        mock_paired = Mock(spec=["pair_id", "divergence"])
        mock_paired.pair_id = "A1-B1"

        with patch(
            "openreview_cli.bilateral.comparison.compare_pair",
            return_value=mock_paired,
        ) as mock_fn:
            ctx: PipelineContext = {"aligned_pairs": aligned_pairs}
            result = asyncio.run(stage.run(ctx))

        assert result is not None
        assert len(result["paired_assessments"]) == 2
        assert mock_fn.call_count == 2

    def test_handles_stage_error(
        self,
        mock_alignment: Mock,
        mock_assessment: Mock,
    ) -> None:
        """Stage wraps compare_pair exceptions without crashing."""
        stage = ComparisonStage(model="extraction")

        aligned_pairs = [
            {
                "alignment": mock_alignment,
                "party_a_assessment": mock_assessment,
                "party_b_assessment": mock_assessment,
                "playbook_category": None,
            }
        ]

        with patch(
            "openreview_cli.bilateral.comparison.compare_pair",
            side_effect=ValueError("boom"),
        ):
            ctx: PipelineContext = {"aligned_pairs": aligned_pairs}
            result = asyncio.run(stage.run(ctx))

        # Should return fallback paired assessment with error
        assert result is not None
        assert "paired_assessments" in result
        assert len(result["paired_assessments"]) == 1
        assert result["paired_assessments"][0].error is not None
        assert "boom" in result["paired_assessments"][0].error

    def test_integration_with_pipeline(
        self,
        mock_alignment: Mock,
        mock_assessment: Mock,
    ) -> None:
        """ComparisonStage works as a Pipeline stage end-to-end."""
        from openreview_cli.pipeline.runner import Pipeline

        stage = ComparisonStage(model="extraction")

        aligned_pairs = [
            {
                "alignment": mock_alignment,
                "party_a_assessment": mock_assessment,
                "party_b_assessment": mock_assessment,
                "playbook_category": None,
            }
        ]

        mock_paired = Mock(spec=["pair_id", "divergence"])
        mock_paired.pair_id = "A1-B1"
        mock_paired.divergence = "aligned"

        with patch(
            "openreview_cli.bilateral.comparison.compare_pair",
            return_value=mock_paired,
        ):
            pipeline = Pipeline([stage])
            ctx: PipelineContext = {"aligned_pairs": aligned_pairs}
            report = asyncio.run(pipeline.run(ctx))

        assert len(report.stage_results) == 1
        assert report.stage_results[0].stage_name == "comparison"
        assert report.stage_results[0].error is None
        assert "paired_assessments" in ctx
