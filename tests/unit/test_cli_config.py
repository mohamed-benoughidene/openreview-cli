import logging
import time
from pathlib import Path

import pytest
from typer.testing import CliRunner

from openreview_cli.app import app
from openreview_cli.config.loader import load_config

runner = CliRunner()


def _setup_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    from openreview_cli.config.paths import get_config_dir

    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "config.yml"


def test_config_show_displays_values(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config_file = _setup_config(monkeypatch, tmp_path)
    config_file.write_text("version: 1\nprivacy:\n  tier: maximum\n")

    result = runner.invoke(app, ["config", "show"])

    assert result.exit_code == 0
    assert "maximum" in result.stdout
    assert "privacy" in result.stdout.lower()


def test_config_get_returns_single_value(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config_file = _setup_config(monkeypatch, tmp_path)
    config_file.write_text("version: 1\nprivacy:\n  tier: balanced\n")

    result = runner.invoke(app, ["config", "get", "privacy.tier"])

    assert result.exit_code == 0
    assert result.stdout.strip() == "balanced"


def test_config_get_unknown_key_shows_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_file = _setup_config(monkeypatch, tmp_path)
    config_file.write_text("version: 1\n")

    result = runner.invoke(app, ["config", "get", "nonexistent.key"])

    assert result.exit_code == 5


def test_config_set_updates_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config_file = _setup_config(monkeypatch, tmp_path)
    config_file.write_text("version: 1\nprivacy:\n  tier: balanced\n")

    result = runner.invoke(app, ["config", "set", "privacy.tier", "maximum"])

    assert result.exit_code == 0
    assert "updated" in result.stdout.lower()
    reloaded = load_config(config_file)
    assert reloaded["privacy"]["tier"] == "maximum"


def test_config_set_creates_backup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config_file = _setup_config(monkeypatch, tmp_path)
    config_file.write_text("version: 1\nprivacy:\n  tier: balanced\n")

    runner.invoke(app, ["config", "set", "privacy.tier", "maximum"])

    assert config_file.with_suffix(".yml.bak").exists()


def test_config_set_rejects_invalid_value(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config_file = _setup_config(monkeypatch, tmp_path)
    config_file.write_text("version: 1\nprivacy:\n  tier: balanced\n")

    result = runner.invoke(app, ["config", "set", "privacy.tier", "invalid"])

    assert result.exit_code == 5


def test_config_set_rejects_invalid_int(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config_file = _setup_config(monkeypatch, tmp_path)
    config_file.write_text("version: 1\ngateway:\n  cost_limits:\n    per_review_cents: 100\n")

    result = runner.invoke(app, ["config", "set", "gateway.cost_limits.per_review_cents", "0"])

    assert result.exit_code == 5


def test_config_operation_latency(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config_file = _setup_config(monkeypatch, tmp_path)
    config_file.write_text("version: 1\nprivacy:\n  tier: balanced\n")

    # Warm-up: the first invoke pays one-time cold-start (auth.json creation,
    # 12 DB migrations on a fresh tmp db) which is environment setup, not
    # config-get latency. Time the second, warm invoke.
    runner.invoke(app, ["config", "get", "privacy.tier"])

    start = time.perf_counter()
    result = runner.invoke(app, ["config", "get", "privacy.tier"])
    elapsed = time.perf_counter() - start

    assert result.exit_code == 0
    assert elapsed < 1.0, f"config get took {elapsed:.3f}s (limit: 1.0s)"


def test_repeated_invokes_do_not_accumulate_file_handlers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Each CLI invoke must replace, not stack, _init's root handlers.

    Stacked FileHandlers keep deleted tmp-dir log files open; logging then
    prints '--- Logging error ---' into CliRunner output, polluting every
    output-asserting CLI test (see docs/test-FAILURES.md failure 1).
    """
    config_file = _setup_config(monkeypatch, tmp_path)
    config_file.write_text("version: 1\nprivacy:\n  tier: balanced\n")

    root = logging.getLogger()
    before = sum(isinstance(h, logging.FileHandler) for h in root.handlers)
    runner.invoke(app, ["config", "get", "privacy.tier"])
    runner.invoke(app, ["config", "get", "privacy.tier"])
    after = sum(isinstance(h, logging.FileHandler) for h in root.handlers)

    assert after - before <= 1
