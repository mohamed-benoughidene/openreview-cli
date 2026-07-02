from pathlib import Path

import pytest
from typer.testing import CliRunner

from openreview_cli.app import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _xdg_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))


class TestPromptLifecycle:
    def test_full_lifecycle(self) -> None:
        runner.invoke(
            app, ["prompt", "create", "--name", "lifecycle-test", "--content", "v1 content"]
        )

        r = runner.invoke(
            app, ["prompt", "create", "--name", "lifecycle-test", "--content", "v1 again"]
        )
        assert r.exit_code == 1

        runner.invoke(app, ["prompt", "update", "lifecycle-test", "--content", "v2 content"])

        r = runner.invoke(app, ["prompt", "list"])
        assert r.exit_code == 0
        assert "lifecycle-test" in r.stdout
        assert "2" in r.stdout

        r = runner.invoke(app, ["prompt", "show", "lifecycle-test", "--version", "1"])
        assert r.exit_code == 0
        assert "v1 content" in r.stdout

        r = runner.invoke(app, ["prompt", "show", "lifecycle-test"])
        assert r.exit_code == 0
        assert "v2 content" in r.stdout

        r = runner.invoke(app, ["prompt", "diff", "lifecycle-test", "--from", "1", "--to", "2"])
        assert r.exit_code == 0
        assert "v1 content" in r.stdout or "-v1 content" in r.stdout
        assert "v2 content" in r.stdout or "+v2 content" in r.stdout

        r = runner.invoke(app, ["prompt", "delete", "lifecycle-test", "--force"])
        assert r.exit_code == 0

        r = runner.invoke(app, ["prompt", "show", "lifecycle-test"])
        assert r.exit_code == 1

    def test_prompt_persistence_across_invocations(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
        runner.invoke(app, ["prompt", "create", "--name", "persist-test", "--content", "Hello"])

        r = runner.invoke(app, ["prompt", "list"])
        assert r.exit_code == 0
        assert "persist-test" in r.stdout

    def test_multiple_prompts(self) -> None:
        runner.invoke(app, ["prompt", "create", "--name", "alpha", "--content", "Alpha content"])
        runner.invoke(app, ["prompt", "create", "--name", "beta", "--content", "Beta content"])

        r = runner.invoke(app, ["prompt", "list"])
        assert "alpha" in r.stdout
        assert "beta" in r.stdout

    def test_delete_without_force_prompts_confirmation(self) -> None:
        runner.invoke(app, ["prompt", "create", "--name", "confirm-test", "--content", "Hello"])
        r = runner.invoke(app, ["prompt", "delete", "confirm-test"], input="y\n")
        assert r.exit_code == 0

        r = runner.invoke(app, ["prompt", "show", "confirm-test"])
        assert r.exit_code == 1
