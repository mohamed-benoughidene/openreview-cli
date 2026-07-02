from pathlib import Path

import pytest
from typer.testing import CliRunner

from openreview_cli.app import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _xdg_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))


@pytest.mark.memory
def test_prompt_operations_under_memory_budget(memory_tracker: None) -> None:
    runner.invoke(app, ["prompt", "create", "--name", "mem-test", "--content", "x" * 1000])
    runner.invoke(app, ["prompt", "create", "--name", "mem-test-2", "--content", "y" * 1000])
    r = runner.invoke(app, ["prompt", "list"])
    assert r.exit_code == 0
    assert "mem-test" in r.stdout
