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


def test_gateway_config_defaults(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yml"
    result = load_config(config_path)
    gateway = result["gateway"]

    # Check slots
    assert gateway["models"]["reasoning"]["primary"] == "ollama/qwen3:8b"
    assert gateway["models"]["reasoning"]["params"]["temperature"] == 0.1
    assert gateway["models"]["embedding"]["primary"] == "ollama/nomic-embed-text"
    assert gateway["models"]["embedding"]["params"]["dimensions"] == 512

    # Check fallback defaults
    assert gateway["fallback"]["retries"] == 2
    assert gateway["fallback"]["timeout"] == 60
    assert gateway["fallback"]["on_failure"] == "error"

    # Check cost limits defaults
    assert gateway["cost_limits"]["per_review_cents"] == 100
    assert gateway["cost_limits"]["daily_cents"] == 1000

    # Check registry defaults
    assert gateway["registry"]["refresh_days"] == 7
    assert gateway["registry"]["remote_url"] == "https://example.com/models.json"


def test_gateway_config_env_overrides(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENREVIEW_GATEWAY__MODELS__REASONING__PRIMARY", "openai/gpt-4o")
    monkeypatch.setenv("OPENREVIEW_GATEWAY__COST_LIMITS__PER_REVIEW_CENTS", "500")
    monkeypatch.setenv("OPENREVIEW_GATEWAY__FALLBACK__RETRIES", "5")
    monkeypatch.setenv(
        "OPENREVIEW_GATEWAY__REGISTRY__REMOTE_URL", "https://custom.com/registry.json"
    )

    config_path = tmp_path / "config.yml"
    config_path.write_text("version: 1\n")
    result = load_config(config_path)

    gateway = result["gateway"]

    assert gateway["models"]["reasoning"]["primary"] == "openai/gpt-4o"
    assert gateway["cost_limits"]["per_review_cents"] == 500
    assert gateway["fallback"]["retries"] == 5
    assert gateway["registry"]["remote_url"] == "https://custom.com/registry.json"


def test_gateway_config_validation_errors(tmp_path: Path) -> None:
    from pydantic import ValidationError

    config_path = tmp_path / "config.yml"

    # Invalid model format in config file
    config_path.write_text("gateway:\n  models:\n    reasoning:\n      primary: openai/\n")
    with pytest.raises(ValidationError):
        load_config(config_path)

    # Invalid temperature range
    config_path.write_text(
        "gateway:\n  models:\n    reasoning:\n      primary: openai/gpt-4o\n      params:\n        temperature: 2.5\n"
    )
    with pytest.raises(ValidationError):
        load_config(config_path)

    # Invalid cost limits (negative)
    config_path.write_text("gateway:\n  cost_limits:\n    per_review_cents: -1\n")
    with pytest.raises(ValidationError):
        load_config(config_path)

    # Invalid URL format
    config_path.write_text("gateway:\n  registry:\n    remote_url: not_a_url\n")
    with pytest.raises(ValidationError):
        load_config(config_path)
