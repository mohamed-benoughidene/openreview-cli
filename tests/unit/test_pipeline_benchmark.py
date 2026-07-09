"""Unit tests for BenchmarkStage adapter.

Tests validate the stage reads per-item data from context (text, category),
processes it, and writes ``prediction`` back.
"""

from __future__ import annotations

import asyncio

import pytest

from openreview_cli.pipeline.adapters.benchmark import BenchmarkStage
from openreview_cli.pipeline.base import PipelineContext, Stage


class TestBenchmarkStageContract:
    """Validate BenchmarkStage conforms to Stage contract."""

    def test_name_and_critical(self) -> None:
        stage = BenchmarkStage()
        assert stage.name == "benchmark"
        assert stage.critical is False
        assert isinstance(stage, Stage)

    def test_should_skip_default(self) -> None:
        stage = BenchmarkStage()
        assert stage.should_skip({}) is False

    def test_cleanup_noop(self) -> None:
        stage = BenchmarkStage()
        stage.cleanup({})


class TestBenchmarkStageRun:
    """Validate run() reads text+category and returns prediction."""

    def test_empty_ctx_raises_key_error(self) -> None:
        stage = BenchmarkStage()
        with pytest.raises(KeyError, match="text"):
            asyncio.run(stage.run({}))

    def test_returns_prediction_dict(self) -> None:
        """Default run returns a basic prediction dict."""
        stage = BenchmarkStage()
        ctx: PipelineContext = {"text": "some contract text", "category": "indemnification"}
        result = asyncio.run(stage.run(ctx))
        assert result is not None
        assert "prediction" in result
        assert isinstance(result["prediction"], dict)
        # Default prediction includes standard keys
        assert "match" in result["prediction"]

    def test_preserves_text_in_context(self) -> None:
        """Stage does not mutate input context."""
        stage = BenchmarkStage()
        ctx: PipelineContext = {"text": "hello", "category": "test"}
        asyncio.run(stage.run(ctx))
        assert ctx["text"] == "hello"
        assert ctx["category"] == "test"

    def test_category_fallback(self) -> None:
        """When category missing, defaults to 'unknown'."""
        stage = BenchmarkStage()
        ctx: PipelineContext = {"text": "some text"}
        result = asyncio.run(stage.run(ctx))
        assert result is not None
        assert "prediction" in result

    def test_integration_with_pipeline(self) -> None:
        """BenchmarkStage works as a Pipeline stage end-to-end."""
        from openreview_cli.pipeline.runner import Pipeline

        stage = BenchmarkStage()
        pipeline = Pipeline([stage])
        ctx: PipelineContext = {"text": "contract text", "category": "indemnification"}
        report = asyncio.run(pipeline.run(ctx))

        assert len(report.stage_results) == 1
        assert report.stage_results[0].stage_name == "benchmark"
        assert report.stage_results[0].error is None
        assert "prediction" in ctx
