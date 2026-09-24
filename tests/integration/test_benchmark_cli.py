"""Integration tests for benchmark CLI --use-pipeline flag."""

from __future__ import annotations

import re
from unittest.mock import patch

import pytest
from typer.core import TyperGroup, TyperOption
from typer.main import get_command
from typer.testing import CliRunner

from openreview_cli.app import app

# Typer forces terminal mode — and therefore ANSI styling — whenever
# ``GITHUB_ACTIONS`` (or ``FORCE_COLOR`` / ``PY_COLORS``) is set, and Rich then
# emits the highlighted option token as several separately-styled spans, e.g.
# ``\x1b[1;36m-\x1b[0m\x1b[1;36m-use\x1b[0m\x1b[1;36m-pipeline\x1b[0m``.
# The literal ``--use-pipeline`` therefore never appears in the raw captured
# output even though the user plainly sees it.  Strip styling before matching.
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _visible(output: str) -> str:
    """Return CLI output with ANSI styling removed — i.e. what the user reads."""
    return _ANSI_RE.sub("", output)


def _registered_options(*command_path: str) -> set[str]:
    """Option strings registered on a command, read from the Click command tree.

    Independent of how the Rich-rendered ``--help`` is laid out (terminal
    width, colour depth, terminal detection), unlike scraping the box output.
    """
    command = get_command(app)
    for name in command_path:
        assert isinstance(command, TyperGroup), f"'{name}' is not a command group"
        command = command.commands[name]
    return {opt for param in command.params if isinstance(param, TyperOption) for opt in param.opts}


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
        """--use-pipeline is registered on `benchmark run` and reaches --help."""
        assert "--use-pipeline" in _registered_options("benchmark", "run")

        # Pin the width so the rendered box cannot wrap the option name.
        result = runner.invoke(app, ["benchmark", "run", "--help"], env={"COLUMNS": "200"})
        assert result.exit_code == 0
        assert "--use-pipeline" in _visible(result.output)
