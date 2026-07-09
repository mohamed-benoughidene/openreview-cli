"""Unit tests for BenchmarkRunner — pipeline kwarg delegation."""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock, patch

from openreview_cli.benchmark.models import BenchmarkConfig
from openreview_cli.benchmark.runner import BenchmarkRunner


def _make_config(
    datasets: list[str] | None = None,
    slots: list[str] | None = None,
    modes: list[str] | None = None,
) -> BenchmarkConfig:
    return BenchmarkConfig(
        datasets=datasets or ["cuad"],
        slots=slots or ["default"],
        modes=modes or ["precheck"],
        prompts={},
        ci_mode=False,
        multi_party=False,
    )


class TestBenchmarkRunnerPipelineKwarg:
    """BenchmarkRunner accepts optional pipeline kwarg."""

    def test_default_pipeline_is_none(self) -> None:
        """Default constructor has no pipeline."""
        config = _make_config()
        runner = BenchmarkRunner(config=config)
        assert runner._pipeline is None

    def test_accepts_pipeline_kwarg(self) -> None:
        """Pipeline kwarg is stored."""
        config = _make_config()
        mock_pipeline = Mock(spec=["run"])
        mock_pipeline.run.return_value = None
        runner = BenchmarkRunner(config=config, pipeline=mock_pipeline)
        assert runner._pipeline is mock_pipeline

    def test_existing_methods_unaffected(self) -> None:
        """Adding pipeline kwarg doesn't break existing method signatures."""
        config = _make_config()
        runner = BenchmarkRunner(config=config)
        # Should still have all expected methods
        assert hasattr(runner, "run_dataset")
        assert hasattr(runner, "run_all")
        assert hasattr(runner, "run_pii")

    def test_run_dataset_defaults_to_direct_path(self) -> None:
        """Without pipeline, run_dataset uses pipeline_fn directly."""
        config = _make_config(datasets=["cuad"])
        runner = BenchmarkRunner(config=config)

        def mock_pipeline_fn(text: str, category: str) -> dict[str, Any]:
            return {"start": 0, "end": 10, "match": True}

        with patch.object(runner, "_load_dataset", return_value=[]):
            result = runner.run_dataset("cuad", mock_pipeline_fn)

        assert result.dataset_name == "cuad"

    def test_run_dataset_allows_pipeline_param(self) -> None:
        """run_dataset signature accepts pipeline_fn (unchanged)."""
        config = _make_config()
        runner = BenchmarkRunner(config=config)

        def fn(text: str, category: str) -> dict[str, Any]:
            return {"match": True}

        with patch.object(runner, "_load_dataset", return_value=[]):
            # Should not raise even with pipeline=None
            result = runner.run_dataset("cuad", fn)
            assert result is not None
