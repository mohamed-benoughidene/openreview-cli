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


def test_set_grounding_slot_persists_and_resolves(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Regression: 'gateway set grounding X' must persist and Gateway must
    resolve the grounding slot. Before the fix, GatewayModels (the pydantic
    schema in _validate_and_merge) had no 'grounding' field, so set_config_value
    silently dropped it and Gateway.chat('grounding', ...) raised
    SlotNotConfiguredError."""
    from openreview_cli.config.loader import set_config_value
    from openreview_cli.gateway.errors import SlotNotConfiguredError
    from openreview_cli.gateway.router import Gateway

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    monkeypatch.setattr("openreview_cli.config.paths.get_config_dir", lambda: config_dir)

    config_path = config_dir / "config.yml"
    # Ensure the config file exists (the real app creates it on first load).
    load_config(config_path)

    # Same call path as `gateway set grounding openrouter/deepseek/deepseek-r1`
    set_config_value(
        config_path, "gateway.models.grounding.primary", "openrouter/deepseek/deepseek-r1"
    )

    # (1) persistence — load_config must round-trip the grounding slot
    persisted = load_config(config_path)
    assert persisted["gateway"]["models"]["grounding"]["primary"] == (
        "openrouter/deepseek/deepseek-r1"
    )

    # (2) resolution — Gateway must no longer raise SlotNotConfiguredError
    gw = Gateway()
    try:
        gw.chat("grounding", [{"role": "user", "content": "test"}])
    except SlotNotConfiguredError as e:
        raise AssertionError("grounding slot still not configured after set") from e
    except Exception:
        # Without a live API key the call fails later (auth/network) — that is
        # expected and proves the config layer resolved the slot correctly.
        pass
