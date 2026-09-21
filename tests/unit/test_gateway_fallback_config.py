"""Gap #1 — the ``openreview gateway fallback`` CLI surface.

Per-slot backup models are optional and user-controlled: the command is the
only way the CLI writes ``gateway.models.<slot>.fallback`` and primary-only
slots are rejected up-front.

Config/log/data directories are redirected so the command never touches the
real ``~/.config/openreview``. The ``gateway.router`` path targets are
deliberately *not* patched: this module never constructs a ``Gateway`` (that
would import litellm, ~4.5 s), so those two targets are unnecessary here.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from openreview_cli.app import app
from openreview_cli.config.loader import load_config

runner = CliRunner()


def _patch_dirs(
    monkeypatch: pytest.MonkeyPatch,
    config_dir: Path,
    log_dir: Path,
    data_dir: Path,
) -> None:
    for dotted in (
        "openreview_cli.config.paths.get_config_dir",
        "openreview_cli.app.get_config_dir",
    ):
        monkeypatch.setattr(dotted, lambda: config_dir)
    for dotted in (
        "openreview_cli.config.paths.get_log_dir",
        "openreview_cli.app.get_log_dir",
    ):
        monkeypatch.setattr(dotted, lambda: log_dir)
    for dotted in (
        "openreview_cli.config.paths.get_data_dir",
        "openreview_cli.app.get_data_dir",
    ):
        monkeypatch.setattr(dotted, lambda: data_dir)


@pytest.fixture
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config_dir = tmp_path / "config"
    log_dir = tmp_path / "logs"
    data_dir = tmp_path / "data"
    for d in (config_dir, log_dir, data_dir):
        d.mkdir()
    config_path = config_dir / "config.yml"
    # Pre-create so set_config_value's unguarded open() finds a file even when
    # a path reaches the subcommand without _init's load_config running first.
    config_path.write_text("gateway:\n  models: {}\n")
    _patch_dirs(monkeypatch, config_dir, log_dir, data_dir)
    return config_path


def test_fallback_command_sets_and_persists(isolated_config: Path) -> None:
    result = runner.invoke(app, ["gateway", "fallback", "reasoning", "anthropic/claude-3-5-haiku"])

    assert result.exit_code == 0, result.output
    persisted = load_config(isolated_config)
    assert persisted["gateway"]["models"]["reasoning"]["fallback"] == ("anthropic/claude-3-5-haiku")


def test_fallback_command_clear_restores_none(isolated_config: Path) -> None:
    runner.invoke(app, ["gateway", "fallback", "reasoning", "anthropic/claude-3-5-haiku"])

    result = runner.invoke(app, ["gateway", "fallback", "reasoning", "--clear"])

    assert result.exit_code == 0, result.output
    persisted = load_config(isolated_config)
    assert persisted["gateway"]["models"]["reasoning"]["fallback"] is None


def test_fallback_command_rejects_primary_only_slot(isolated_config: Path) -> None:
    before = isolated_config.read_text()

    result = runner.invoke(app, ["gateway", "fallback", "embedding", "cohere/embed-x"])

    assert result.exit_code == 1
    assert "primary-only" in result.stderr
    assert isolated_config.read_text() == before


def test_fallback_command_rejects_unknown_slot(isolated_config: Path) -> None:
    result = runner.invoke(app, ["gateway", "fallback", "nonexistent", "anthropic/x"])

    assert result.exit_code == 1
    assert "Invalid slot" in result.stderr


def test_fallback_command_requires_model_or_clear(isolated_config: Path) -> None:
    result = runner.invoke(app, ["gateway", "fallback", "reasoning"])

    assert result.exit_code == 1


def test_default_install_starts_without_fallback(isolated_config: Path) -> None:
    for slot in ("reasoning", "extraction", "graph", "grounding"):
        result = runner.invoke(app, ["gateway", "fallback", slot, "--clear"])
        assert result.exit_code == 0, result.output

    persisted = load_config(isolated_config)
    models = persisted["gateway"]["models"]
    assert models["reasoning"]["fallback"] is None
    assert models["reasoning"]["primary"]
