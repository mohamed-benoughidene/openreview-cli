from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from openreview_cli.app import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _xdg_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))


def invoke(*args: str, **kwargs: Any) -> Any:
    return runner.invoke(app, ["prompt", *args], **kwargs)


class TestPromptCreate:
    def test_create_success(self) -> None:
        result = invoke("create", "--name", "test", "--content", "Hello")
        assert result.exit_code == 0

    def test_create_duplicate(self) -> None:
        invoke("create", "--name", "test", "--content", "Hello")
        result = invoke("create", "--name", "test", "--content", "World")
        assert result.exit_code == 1

    def test_create_content_too_long(self) -> None:
        result = invoke("create", "--name", "test", "--content", "x" * 20000)
        assert result.exit_code == 2

    def test_create_with_tags(self) -> None:
        result = invoke("create", "--name", "test", "--content", "Hello", "--tags", "tag1,tag2")
        assert result.exit_code == 0


class TestPromptUpdate:
    def test_update_success(self) -> None:
        invoke("create", "--name", "test", "--content", "v1")
        result = invoke("update", "test", "--content", "v2")
        assert result.exit_code == 0

    def test_update_nonexistent(self) -> None:
        result = invoke("update", "nonexistent", "--content", "v1")
        assert result.exit_code == 1


class TestPromptList:
    def test_list_empty(self) -> None:
        result = invoke("list")
        assert result.exit_code == 0

    def test_list_with_prompts(self) -> None:
        invoke("create", "--name", "test", "--content", "Hello")
        result = invoke("list")
        assert result.exit_code == 0
        assert "test" in result.stdout


class TestPromptShow:
    def test_show_success(self) -> None:
        invoke("create", "--name", "test", "--content", "Hello")
        result = invoke("show", "test")
        assert result.exit_code == 0
        assert "Hello" in result.stdout

    def test_show_nonexistent(self) -> None:
        result = invoke("show", "nonexistent")
        assert result.exit_code == 1


class TestPromptDelete:
    def test_delete_force_success(self) -> None:
        invoke("create", "--name", "test", "--content", "Hello")
        result = invoke("delete", "test", "--force")
        assert result.exit_code == 0

    def test_delete_nonexistent(self) -> None:
        result = invoke("delete", "nonexistent", "--force")
        assert result.exit_code == 1


class TestPromptDiff:
    def test_diff_success(self) -> None:
        invoke("create", "--name", "test", "--content", "Hello")
        invoke("update", "test", "--content", "World")
        result = invoke("diff", "test", "--from", "1", "--to", "2")
        assert result.exit_code == 0

    def test_diff_nonexistent_prompt(self) -> None:
        result = invoke("diff", "nonexistent", "--from", "1", "--to", "2")
        assert result.exit_code == 1

    def test_diff_nonexistent_version(self) -> None:
        invoke("create", "--name", "test", "--content", "Hello")
        result = invoke("diff", "test", "--from", "1", "--to", "99")
        assert result.exit_code == 2


class TestPromptHistory:
    def test_history_shows_versions(self) -> None:
        invoke("create", "--name", "test", "--content", "v1")
        invoke("update", "test", "--content", "v2")
        result = invoke("history", "test")
        assert result.exit_code == 0
        assert "1" in result.stdout
        assert "2" in result.stdout

    def test_history_nonexistent(self) -> None:
        result = invoke("history", "nonexistent")
        assert result.exit_code == 1


class TestPromptTest:
    def test_test_shows_error_without_benchmark(self) -> None:
        invoke("create", "--name", "test", "--content", "Hello")
        invoke("update", "test", "--content", "World")
        result = invoke("test", "--prompt", "test", "--versions", "1,2")
        assert result.exit_code == 3

    def test_test_invalid_prompt(self) -> None:
        result = invoke("test", "--prompt", "nonexistent", "--versions", "1")
        assert result.exit_code == 1

    def test_test_invalid_version(self) -> None:
        invoke("create", "--name", "test", "--content", "Hello")
        result = invoke("test", "--prompt", "test", "--versions", "99")
        assert result.exit_code == 2


class TestPromptExport:
    def test_export_single(self) -> None:
        invoke("create", "--name", "test", "--content", "Hello")
        result = invoke("export", "test")
        assert result.exit_code == 0

    def test_export_unknown(self) -> None:
        result = invoke("export", "nonexistent")
        assert result.exit_code == 1


class TestPromptImport:
    def test_import_from_file(self, tmp_path: Path) -> None:
        invoke("create", "--name", "import-src", "--content", "Src")
        result = invoke("export", "import-src", "--output", str(tmp_path / "out.yaml"))
        assert result.exit_code == 0
        invoke("delete", "import-src", "--force")
        result = invoke("import", str(tmp_path / "out.yaml"))
        assert result.exit_code == 0

    def test_import_nonexistent_file(self) -> None:
        result = invoke("import", "/nonexistent/file.yaml")
        assert result.exit_code == 1


class TestPromptOptimize:
    def test_optimize_shows_error_without_benchmark(self) -> None:
        invoke("create", "--name", "test", "--content", "Hello")
        result = invoke("optimize", "--prompt", "test", "--iterations", "3")
        assert result.exit_code == 2

    def test_optimize_invalid_prompt(self) -> None:
        result = invoke("optimize", "--prompt", "nonexistent")
        assert result.exit_code == 1

    def test_optimize_invalid_iterations(self) -> None:
        invoke("create", "--name", "test", "--content", "Hello")
        result = invoke("optimize", "--prompt", "test", "--iterations", "0")
        assert result.exit_code == 3
