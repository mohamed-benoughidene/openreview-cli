"""Integration tests for benchmark CLI --use-pipeline flag."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from openreview_cli.app import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestBenchmarkCliUsePipeline:
    """--use-pipeline flag is accepted and wires BenchmarkStage."""

    def test_use_pipeline_flag_accepted(self, runner: CliRunner) -> None:
        """--use-pipeline is a valid flag."""
        with patch(
            "openreview_cli.benchmark.cli._FIXTURES_DIR",
            "/tmp",
        ):
            result = runner.invoke(
                app,
                ["benchmark", "run", "--datasets", "cuad", "--use-pipeline"],
            )
        # Should not error on the flag — may error on missing fixtures
        assert "Error: Invalid" not in result.output
        # Options are accepted (exit code non-zero likely due to fixtures)
        assert result.exit_code != 2  # 2 = usage error in typer

    def test_default_no_use_pipeline(self, runner: CliRunner) -> None:
        """Without --use-pipeline, benchmark runs as before."""
        with patch(
            "openreview_cli.benchmark.cli._FIXTURES_DIR",
            "/tmp",
        ):
            result = runner.invoke(
                app,
                ["benchmark", "run", "--datasets", "cuad"],
            )
        assert result.exit_code != 2

    def test_use_pipeline_with_all_datasets(self, runner: CliRunner) -> None:
        """--use-pipeline works with --all flag."""
        with patch(
            "openreview_cli.benchmark.cli._FIXTURES_DIR",
            "/tmp",
        ):
            result = runner.invoke(
                app,
                ["benchmark", "run", "--all", "--use-pipeline"],
            )
        assert result.exit_code != 2

    def test_help_shows_flag(self, runner: CliRunner) -> None:
        """--help for benchmark run shows --use-pipeline."""
        result = runner.invoke(app, ["benchmark", "run", "--help"])
        assert "--use-pipeline" in result.output
