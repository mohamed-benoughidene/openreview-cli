"""Unit tests for the gateway domain fallback surface (Gap #1)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from openreview_cli.config.loader import load_config
from openreview_cli.tui.domain import gateway as gw_domain


def _seed(config_path: Path, gateway_models: dict) -> None:
    config_path.write_text(yaml.safe_dump({"gateway": {"models": gateway_models}}))


def test_save_slot_fallback_writes_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "config.yml"
    config_path.write_text("gateway:\n  models: {}\n")
    monkeypatch.setitem(gw_domain._PATHS, "config", config_path)

    gw_domain.save_slot_fallback("reasoning", "anthropic/claude-3-5-haiku")

    persisted = load_config(config_path)
    assert persisted["gateway"]["models"]["reasoning"]["fallback"] == "anthropic/claude-3-5-haiku"


def test_save_slot_fallback_none_clears(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "config.yml"
    _seed(
        config_path,
        {
            "reasoning": {
                "primary": "anthropic/claude-opus",
                "fallback": "anthropic/claude-3-5-haiku",
            }
        },
    )
    monkeypatch.setitem(gw_domain._PATHS, "config", config_path)

    gw_domain.save_slot_fallback("reasoning", None)

    persisted = load_config(config_path)
    assert persisted["gateway"]["models"]["reasoning"]["fallback"] is None


def test_save_slot_fallback_rejects_primary_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "config.yml"
    config_path.write_text("gateway:\n  models: {}\n")
    monkeypatch.setitem(gw_domain._PATHS, "config", config_path)

    with pytest.raises(ValueError):
        gw_domain.save_slot_fallback("embedding", "cohere/embed-x")


def test_get_slot_configs_includes_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "config.yml"
    _seed(
        config_path,
        {
            "reasoning": {
                "primary": "anthropic/claude-opus",
                "fallback": "anthropic/claude-3-5-haiku",
            },
            "reranking": {"primary": "cohere/rerank-x", "fallback": "cohere/backup"},
        },
    )
    monkeypatch.setitem(gw_domain._PATHS, "config", config_path)

    slots = gw_domain.get_slot_configs()

    assert slots["reasoning"]["fallback"] == "anthropic/claude-3-5-haiku"
    assert slots["reranking"]["provider"] == "cohere"
    assert slots["reranking"].get("fallback") is None
