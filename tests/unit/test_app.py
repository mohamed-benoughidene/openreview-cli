import time
from pathlib import Path

import pytest
from typer.testing import CliRunner

from openreview_cli import __version__
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


def test_warm_startup_latency(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    runner.invoke(app, ["--version"])
    start = time.perf_counter()
    runner.invoke(app, ["--version"])
    elapsed = time.perf_counter() - start
    assert elapsed < 0.3, f"warm startup took {elapsed:.3f}s, expected <0.3s"
