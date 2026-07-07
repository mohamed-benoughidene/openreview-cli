"""Unit tests for run_review() public API and pipeline adoption."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from openreview_cli.review import run_review


def _make_playbook(pid: str = "test") -> Any:
    """Return a minimal valid Playbook with one category."""
    from openreview_cli.review.models import (
        Category,
        Playbook,
        PlaybookMetadata,
        Position,
        PositionDef,
    )

    return Playbook(
        id=pid,
        mode="precheck",
        categories=[
            Category(
                id="test-cat",
                name="Test",
                description="test",
                preferred=PositionDef(description="a", exemplars=["a"]),
                acceptable=PositionDef(description="b", exemplars=["b"]),
                walkaway=PositionDef(description="c", exemplars=["c"]),
                default_position=Position.ACCEPTABLE,
            ),
        ],
        metadata=PlaybookMetadata(version="1.0.0", description="t", author="t"),
    )


class TestRunReviewPublicAPI:
    """Tests for the run_review() public API surface."""

    def test_accepts_kwargs(self) -> None:
        """run_review should accept all keyword arguments without error (signature check)."""
        import inspect

        sig = inspect.signature(run_review)
        params = {p.name for p in sig.parameters.values()}
        for expected in (
            "paths",
            "playbook_path",
            "extraction_model",
            "qa_model",
            "no_pii",
            "verbose",
        ):
            assert expected in params, f"Missing parameter: {expected}"

    def test_returns_list_of_reports(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """run_review returns a list of ReviewReport objects."""
        from datetime import UTC, datetime

        from openreview_cli.review.models import DocMeta, ReviewReport, ReviewSummary

        def mock_pipeline(
            doc_path: str,
            playbook: Any,
            playbook_version: str | None,
            extraction_model: str,
            qa_model: str,
            no_pii: bool,
            verbose: bool,
            confidence_threshold: float,
            mode: str = "precheck",
        ) -> tuple[ReviewReport, list[Any]] | None:
            return (
                ReviewReport(
                    document=DocMeta(
                        filename="test.docx",
                        page_count=1,
                        clause_count=0,
                        pii_stripped=False,
                    ),
                    assessments=[],
                    summary=ReviewSummary(),
                    playbook_id="test",
                    generated_at=datetime.now(UTC),
                ),
                [],
            )

        monkeypatch.setattr("openreview_cli.review._run_review_doc_pipeline", mock_pipeline)

        # Patch load_bundled
        monkeypatch.setattr("openreview_cli.review.load_bundled", _make_playbook)

        # Mock Path.exists so "test.docx" is treated as existing
        monkeypatch.setattr("pathlib.Path.exists", lambda self: True)

        reports = run_review(paths=["test.docx"])
        assert isinstance(reports, list)
        assert len(reports) == 1
        assert isinstance(reports[0], ReviewReport)


class TestPipelineAdoption:
    """Tests that verify the pipeline framework is adopted in the review flow."""

    def test_run_review_pipeline_doc_invokes_pipeline(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify _run_review_doc_pipeline creates a Pipeline with ParseStage and ReviewStage."""
        from openreview_cli.pipeline.runner import PipelineReport

        playbook = _make_playbook("invoke-test")

        # Mock Pipeline.run to verify stages
        captured_stages: list[str] = []

        class MockPipeline:
            def __init__(self, stages: list[Any], **kwargs: Any) -> None:
                self._stages = stages
                captured_stages.extend(s.name for s in stages)

            async def run(self, ctx: dict[str, Any]) -> PipelineReport:
                return PipelineReport()

        monkeypatch.setattr("openreview_cli.review.Pipeline", MockPipeline)

        from openreview_cli.review import _run_review_doc_pipeline

        _run_review_doc_pipeline(
            doc_path="test.docx",
            playbook=playbook,
            playbook_version=None,
            extraction_model="extraction",
            qa_model="extraction",
            no_pii=False,
            verbose=False,
            confidence_threshold=0.7,
        )

        # Pipeline should include parse, strip, and review stages
        assert "parse" in captured_stages, "ParseStage should be in pipeline"
        assert "strip" in captured_stages, "StripStage should be in pipeline (no_pii=False)"
        assert "review" in captured_stages, "ReviewStage should be in pipeline"

    def test_no_pii_skips_strip_stage(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify no_pii=True excludes StripStage from the pipeline."""
        from openreview_cli.pipeline.runner import PipelineReport

        playbook = _make_playbook("no-pii-test")

        captured_stages: list[str] = []

        class MockPipeline:
            def __init__(self, stages: list[Any], **kwargs: Any) -> None:
                self._stages = stages
                captured_stages.extend(s.name for s in stages)

            async def run(self, ctx: dict[str, Any]) -> PipelineReport:
                return PipelineReport()

        monkeypatch.setattr("openreview_cli.review.Pipeline", MockPipeline)

        from openreview_cli.review import _run_review_doc_pipeline

        _run_review_doc_pipeline(
            doc_path="test.docx",
            playbook=playbook,
            playbook_version=None,
            extraction_model="extraction",
            qa_model="extraction",
            no_pii=True,
            verbose=False,
            confidence_threshold=0.7,
        )

        assert "parse" in captured_stages, "ParseStage should always be in pipeline"
        assert "strip" not in captured_stages, (
            "StripStage should NOT be in pipeline when no_pii=True"
        )
        assert "review" in captured_stages, "ReviewStage should be in pipeline"

    def test_review_stage_run(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify ReviewStage.run() is called during pipeline execution."""
        from openreview_cli.pipeline.runner import PipelineReport
        from openreview_cli.review.pipeline import ReviewStage

        playbook = _make_playbook("run-test")
        stage = ReviewStage(playbook=playbook)

        # Mock Pipeline so asyncio.run can properly execute the async run()
        class MockPipeline:
            def __init__(self, stages: list[Any], **kwargs: Any) -> None:
                pass

            async def run(self, ctx: dict[str, Any]) -> PipelineReport:
                # Simulate the real pipeline: ParseStage would have populated
                # document and clauses before ReviewStage runs
                ctx["document"] = None
                ctx["clauses"] = []
                _ = await stage.run(ctx)
                return PipelineReport()

        monkeypatch.setattr("openreview_cli.review.Pipeline", MockPipeline)

        from openreview_cli.review import _run_review_doc_pipeline

        _run_review_doc_pipeline(
            doc_path="test.docx",
            playbook=playbook,
            playbook_version=None,
            extraction_model="extraction",
            qa_model="extraction",
            no_pii=True,
            verbose=False,
            confidence_threshold=0.7,
        )

        # ReviewStage.report should be set after pipeline execution
        assert stage.report is not None
        assert stage.report.playbook_id == "run-test"


class TestReviewStage:
    """Direct tests for ReviewStage."""

    def test_run_empty_clauses(self) -> None:
        """ReviewStage returns an empty report when no clauses are in context."""
        from openreview_cli.review.pipeline import ReviewStage

        playbook = _make_playbook("empty-test")
        stage = ReviewStage(playbook=playbook)
        result = asyncio.run(stage.run({"document": None, "clauses": []}))

        assert result is not None
        assert "review_report" in result
        report = result["review_report"]
        assert report.playbook_id == "empty-test"
        assert len(report.assessments) == 0

    def test_run_with_missing_document(self) -> None:
        """ReviewStage handles missing document gracefully."""
        from openreview_cli.review.pipeline import ReviewStage

        playbook = _make_playbook("no-doc")
        stage = ReviewStage(playbook=playbook)
        result = asyncio.run(stage.run({"clauses": []}))

        assert result is not None
        assert "review_report" in result
        report = result["review_report"]
        assert report.playbook_id == "no-doc"

    def test_run_uses_stripped_clauses_when_available(self) -> None:
        """ReviewStage prefers stripped_clauses over clauses."""
        from openreview_cli.review.pipeline import ReviewStage

        playbook = _make_playbook("strip-test")
        stage = ReviewStage(playbook=playbook)

        # Provide both clauses and stripped_clauses; stage should use stripped_clauses
        result = asyncio.run(
            stage.run(
                {
                    "document": None,
                    "clauses": [object()],  # would cause error if used
                    "stripped_clauses": [],  # empty so review succeeds
                }
            )
        )

        assert result is not None
        assert "review_report" in result
        report = result["review_report"]
        assert report.playbook_id == "strip-test"
