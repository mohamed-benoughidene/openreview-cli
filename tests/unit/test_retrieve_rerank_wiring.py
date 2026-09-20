"""Unit tests for the retrieve --rerank wiring (config default and bookkeeping model id)."""

from __future__ import annotations

from pathlib import Path

import pytest

from openreview_cli.app import _rerank_enabled_from_config, _reranker_model_id
from openreview_cli.config.loader import load_config, set_config_value
from openreview_cli.config.paths import get_config_dir


class _StubGateway:
    def __init__(self, primary: str | None) -> None:
        self._primary = primary

    def slot_primary_model(self, slot: str) -> str | None:
        return self._primary


@pytest.fixture(autouse=True)
def _isolated_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg_config"))


def _write_config_value(key: str, value: str) -> None:
    config_path = get_config_dir() / "config.yml"
    load_config(config_path)
    set_config_value(config_path, key, value)


def test_rerank_disabled_by_default() -> None:
    assert _rerank_enabled_from_config() is False


def test_rerank_enabled_from_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    # Materialize config.yml first: `load_config` early-returns `DEFAULT_CONFIG` and skips env
    # overrides on the call that creates the file (`config/loader.py:307-311`). Env overrides only
    # apply on a subsequent load, which is what the CLI does (`app.py:252-253` loads in `_init`).
    load_config(get_config_dir() / "config.yml")
    monkeypatch.setenv("OPENREVIEW_RETRIEVAL__RERANK_ENABLED", "true")

    assert _rerank_enabled_from_config() is True


def test_rerank_enabled_from_config_file() -> None:
    _write_config_value("retrieval.rerank_enabled", "true")

    assert _rerank_enabled_from_config() is True


def test_reranker_model_id_prefers_gateway_slot() -> None:
    assert _reranker_model_id(_StubGateway("voyage/rerank-2.5")) == "voyage/rerank-2.5"


def test_reranker_model_id_falls_back_to_config() -> None:
    _write_config_value("retrieval.reranker_model", "voyage/rerank-2.5")

    assert _reranker_model_id(_StubGateway(None)) == "voyage/rerank-2.5"


def test_reranker_model_id_defaults_to_bundled_model() -> None:
    assert _reranker_model_id(None) == "qwen3-reranker-0.6b"
