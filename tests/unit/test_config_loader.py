from pathlib import Path

import pytest

from openreview_cli.config.loader import load_config
from openreview_cli.config.paths import get_config_dir


def test_config_yml_created_with_defaults(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yml"
    result = load_config(config_path)
    assert config_path.exists()
    for key in ("version", "privacy", "gateway", "storage"):
        assert key in result


def test_load_returns_defaults(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yml"
    result = load_config(config_path)
    assert result["version"] == 1
    assert result["privacy"]["tier"] == "balanced"
    assert result["gateway"]["cost_limits"]["per_review_cents"] == 100
    assert result["storage"]["logs_keep_days"] == 30


def test_load_merges_file_over_defaults(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yml"
    config_path.write_text("privacy:\n  tier: maximum\n")
    result = load_config(config_path)
    assert result["privacy"]["tier"] == "maximum"
    assert result["version"] == 1


def test_env_var_overrides_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENREVIEW_PRIVACY_TIER", "maximum")
    config_path = tmp_path / "config.yml"
    config_path.write_text("version: 1\nprivacy:\n  tier: balanced\n")
    result = load_config(config_path)
    assert result["privacy"]["tier"] == "maximum"


def test_env_var_falls_through_to_defaults(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENREVIEW_PRIVACY_TIER", "maximum")
    config_path = tmp_path / "config.yml"
    config_path.write_text("version: 1\n")
    result = load_config(config_path)
    assert result["version"] == 1


def test_config_path_uses_platformdirs() -> None:
    config_dir = get_config_dir()
    assert isinstance(config_dir, Path)
    assert "openreview" in str(config_dir).lower()
