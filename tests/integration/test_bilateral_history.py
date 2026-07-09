"""Integration test for D-11: --history flag on compare command."""

from typer.testing import CliRunner

from openreview_cli.app import app

runner = CliRunner()


def test_history_flag_empty_table() -> None:
    """--history shows empty-state message without crashing."""
    result = runner.invoke(app, ["precheck", "compare", "--history"])
    assert result.exit_code == 0


def test_history_flag_skips_file_validation() -> None:
    """--history returns early, so doc paths are NOT required."""
    result = runner.invoke(app, ["precheck", "compare", "--history"])
    assert result.exit_code == 0
