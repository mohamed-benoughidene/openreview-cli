import os
from pathlib import Path

import pytest

from openreview_cli.config.loader import load_config
from openreview_cli.config.paths import get_config_dir


@pytest.fixture(autouse=True)
def _scrub_openreview_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in [k for k in os.environ if k.startswith("OPENREVIEW_")]:
        monkeypatch.delenv(key, raising=False)


def test_default_config_has_no_fallback_models(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yml"
    result = load_config(config_path)
    models = result["gateway"]["models"]
    for slot in ("reasoning", "extraction", "grounding"):
        assert models[slot]["fallback"] is None


def test_removed_slot_keys_are_ignored_not_an_error(tmp_path: Path) -> None:
    """A config written before the slot consolidation must still load.

    ``embedding``/``reranking``/``graph`` are no longer schema fields, so an
    old config carrying them is dropped from the validated view rather than
    raising a validation error.
    """
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        "gateway:\n"
        "  models:\n"
        "    reranking:\n"
        "      primary: cohere/rerank-x\n"
        "      fallback: cohere/backup\n"
    )
    result = load_config(config_path)
    assert "reranking" not in result["gateway"]["models"]


def test_shipped_defaults_are_the_same_model_for_all_three_slots(tmp_path: Path) -> None:
    """Spec 035 T1.5: granite4:3b is the shipped default for every slot."""
    config_path = tmp_path / "config.yml"
    models = load_config(config_path)["gateway"]["models"]
    assert set(models) == {"extraction", "reasoning", "grounding"}
    for slot in ("extraction", "reasoning", "grounding"):
        assert models[slot]["primary"] == "ollama/granite4:3b"


def test_legacy_performance_tier_loads_as_balanced(tmp_path: Path) -> None:
    """Spec 035 T1.4 compatibility: an old ``performance`` value must not crash.

    The pydantic schema validates before ``PrivacyTier.parse`` runs, so the old
    value has to stay accepted and be normalized to ``balanced``.
    """
    config_path = tmp_path / "config.yml"
    config_path.write_text("privacy:\n  tier: performance\n")
    assert load_config(config_path)["privacy"]["tier"] == "balanced"


def test_legacy_performance_tier_yields_balanced_rules(tmp_path: Path) -> None:
    from openreview_cli.gateway.tier_config import TierConfig

    config_path = tmp_path / "config.yml"
    config_path.write_text("privacy:\n  tier: performance\n")
    legacy = TierConfig.from_config(load_config(config_path))
    balanced = TierConfig.from_config(load_config(tmp_path / "other.yml"))
    assert legacy.tier == "balanced"
    assert legacy.tier_source == "config"
    assert legacy.llm_local_only == balanced.llm_local_only is False
    assert legacy.pii_required_before_cloud == balanced.pii_required_before_cloud is True


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


def test_env_override_applies_on_config_creation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("OPENREVIEW_PRIVACY_TIER", "maximum")
    config_path = tmp_path / "config.yml"
    result = load_config(config_path)
    assert result["privacy"]["tier"] == "maximum"
    assert "maximum" not in config_path.read_text()


def test_config_path_uses_platformdirs() -> None:
    config_dir = get_config_dir()
    assert isinstance(config_dir, Path)
    assert "openreview" in str(config_dir).lower()


def test_set_config_value_persists_an_unknown_key(tmp_path: Path) -> None:
    """Issue #125: a key outside the schema must survive `config set` and be
    readable back from the raw file, instead of being silently dropped."""
    from openreview_cli.config.loader import get_stored_config_value, set_config_value

    config_path = tmp_path / "config.yml"
    load_config(config_path)

    set_config_value(config_path, "rt005.unknown.key", "x")

    assert get_stored_config_value(config_path, "rt005.unknown.key") == "x"


def test_get_stored_config_value_ignores_env_only_unknown_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """File-only contract: an unknown key supplied only via env is NOT readable
    through the raw-file reader, so ``config get`` cannot echo arbitrary
    ``OPENREVIEW_*`` environment variables (e.g. secrets)."""
    from openreview_cli.config.loader import get_stored_config_value

    config_path = tmp_path / "config.yml"
    load_config(config_path)
    monkeypatch.setenv("OPENREVIEW_FOO__BAR", "x")

    with pytest.raises(KeyError):
        get_stored_config_value(config_path, "foo.bar")


def test_get_stored_config_value_ignores_env_over_stored(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """File-only contract: env does not shadow a value persisted in the file."""
    from openreview_cli.config.loader import get_stored_config_value, set_config_value

    config_path = tmp_path / "config.yml"
    load_config(config_path)
    set_config_value(config_path, "foo.bar", "from-file")
    monkeypatch.setenv("OPENREVIEW_FOO__BAR", "from-env")

    assert get_stored_config_value(config_path, "foo.bar") == "from-file"


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
