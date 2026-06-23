import pytest
from typer.testing import CliRunner

from openreview_cli._version import __version__
from openreview_cli.app import app

runner = CliRunner()


def test_app_imports() -> None:
    assert app is not None


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_help_flag() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "openreview" in result.stdout.lower()


@pytest.mark.memory
def test_imports_are_under_budget(memory_tracker: None) -> None:
    assert app is not None
    assert __version__
