"""Tests for benchmark CLI --hallucination-method flag.

See D-7 in DEFERRED.md: wires HallucinationDetector selection
through the benchmark run CLI command.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from openreview_cli.benchmark.cli import benchmark_app
from openreview_cli.benchmark.models import DatasetResult

FIXTURES = Path(__file__).resolve().parent.parent.parent / "fixtures"


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def mock_runner_deps(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Mock BenchmarkRunner and filesystem to isolate flag tests."""
    mock_runner = MagicMock()
    result = DatasetResult(dataset_name="mock", dataset_version="v1", n_examples=0)
    mock_runner.run_dataset.return_value = result

    monkeypatch.setattr(
        "openreview_cli.benchmark.cli.BenchmarkRunner",
        lambda config, fixtures_root, cache_dir, **kwargs: mock_runner,
    )
    monkeypatch.setattr(
        "openreview_cli.benchmark.cli._FIXTURES_DIR",
        FIXTURES,
    )
    monkeypatch.setattr(
        "openreview_cli.benchmark.cli.get_data_dir",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        "openreview_cli.benchmark.cli._detect_git_branch",
        lambda: "test",
    )
    monkeypatch.setattr(
        "openreview_cli.benchmark.cli._detect_git_commit",
        lambda: "abc1234",
    )
    monkeypatch.setattr(
        "openreview_cli.benchmark.cli._run_pii_evaluation",
        lambda runner, verbose: None,
    )


class TestValidHallucinationMethods:
    """VALID_HALLUCINATION_METHODS constant."""

    def test_constant_exists(self) -> None:
        from openreview_cli.benchmark.cli import VALID_HALLUCINATION_METHODS

        assert isinstance(VALID_HALLUCINATION_METHODS, frozenset)

    def test_contains_lexical(self) -> None:
        from openreview_cli.benchmark.cli import VALID_HALLUCINATION_METHODS

        assert "lexical" in VALID_HALLUCINATION_METHODS

    def test_contains_cg_dpo(self) -> None:
        from openreview_cli.benchmark.cli import VALID_HALLUCINATION_METHODS

        assert "cg-dpo" in VALID_HALLUCINATION_METHODS

    def test_is_frozenset(self) -> None:
        from openreview_cli.benchmark.cli import VALID_HALLUCINATION_METHODS

        assert isinstance(VALID_HALLUCINATION_METHODS, frozenset)


class TestHallucinationMethodCli:
    """--hallucination-method CLI flag."""

    def test_help_shows_flag(self, cli_runner: CliRunner) -> None:
        """--hallucination-method should appear in --help output."""
        result = cli_runner.invoke(benchmark_app, ["run", "--help"])
        assert result.exit_code == 0
        assert "--hallucination-method" in result.stdout

    def test_invalid_value_rejected(self, cli_runner: CliRunner) -> None:
        """Invalid value 'foo' should exit with code 78."""
        result = cli_runner.invoke(benchmark_app, ["run", "--hallucination-method=foo"])
        assert result.exit_code == 78

    def test_invalid_value_message_mentions_valid_values(self, cli_runner: CliRunner) -> None:
        """Error message should list valid options."""
        result = cli_runner.invoke(benchmark_app, ["run", "--hallucination-method=invalid"])
        assert result.exit_code == 78

    def test_valid_lexical_accepted(self, cli_runner: CliRunner, mock_runner_deps: None) -> None:
        """'lexical' should pass validation and complete."""
        result = cli_runner.invoke(benchmark_app, ["run", "--hallucination-method=lexical"])
        assert result.exit_code == 0

    def test_valid_cg_dpo_accepted(self, cli_runner: CliRunner, mock_runner_deps: None) -> None:
        """'cg-dpo' should pass validation and complete."""
        result = cli_runner.invoke(benchmark_app, ["run", "--hallucination-method=cg-dpo"])
        assert result.exit_code == 0
