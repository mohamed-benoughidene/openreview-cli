"""Live CLI integration tests using a real OpenRouter API key.

Set the OPENROUTER_API_KEY environment variable to run these tests:
  export OPENROUTER_API_KEY="sk-or-v1-..."
  uv run pytest tests/integration/test_gateway_live_cli.py -v

These tests are excluded from CI (marked @pytest.mark.live).
"""

import json
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from openreview_cli.app import app
from openreview_cli.config.loader import load_config

pytestmark = pytest.mark.live

runner = CliRunner()


def _model(name: str) -> str:
    return f"openrouter/{name}"


@pytest.fixture
def live_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    config_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))

    openreview_config = config_dir / "openreview"
    openreview_config.mkdir(exist_ok=True)

    cfg_path = openreview_config / "config.yml"
    cfg_path.write_text(
        """
version: 1
gateway:
  models:
    reasoning:
      primary: openrouter/openai/gpt-4o-mini
      params:
        temperature: 0.1
        max_tokens: 500
    extraction:
      primary: openrouter/openai/gpt-4o-mini
      params:
        temperature: 0.0
    embedding:
      primary: openrouter/openai/text-embedding-3-small
    graph:
      primary: openrouter/openai/gpt-4o-mini
      params:
        temperature: 0.0
    reranking:
      primary: openrouter/openai/gpt-4o-mini
  cost_limits:
    per_review_cents: 500
    daily_cents: 5000
  fallback:
    retries: 1
    retry_delay: 0.5
    timeout: 30
    on_failure: error
  registry:
    refresh_days: 7
    remote_url: https://example.com/models.json
"""
    )

    key = os.environ.get("OPENROUTER_API_KEY", "")
    auth_path = openreview_config / "auth.json"
    auth_path.write_text(json.dumps({"openrouter": key, "openai": key}))
    auth_path.chmod(0o600)

    return config_dir


def _skipif_no_key() -> bool:
    return not os.environ.get("OPENROUTER_API_KEY")


@pytest.mark.skipif(_skipif_no_key(), reason="OPENROUTER_API_KEY not set")
def test_live_cli_setup_noninteractive(live_config_dir: Path) -> None:
    config_path = live_config_dir / "openreview" / "config.yml"
    if config_path.exists():
        config_path.unlink()

    m = _model
    result = runner.invoke(
        app,
        [
            "gateway",
            "setup",
            "--non-interactive",
            "--reasoning",
            m("openai/gpt-4o-mini"),
            "--extraction",
            m("openai/gpt-4o-mini"),
            "--embedding",
            m("openai/text-embedding-3-small"),
            "--reranking",
            m("openai/gpt-4o-mini"),
            "--graph",
            m("openai/gpt-4o-mini"),
        ],
    )
    assert result.exit_code == 0
    assert "configured" in result.stdout.lower()

    config = load_config(config_path)
    assert config["gateway"]["models"]["reasoning"]["primary"] == m("openai/gpt-4o-mini")


@pytest.mark.skipif(_skipif_no_key(), reason="OPENROUTER_API_KEY not set")
def test_live_cli_status(live_config_dir: Path) -> None:
    result = runner.invoke(app, ["gateway", "status"])
    assert result.exit_code == 0
    assert "openrouter" in result.stdout.lower()


@pytest.mark.skipif(_skipif_no_key(), reason="OPENROUTER_API_KEY not set")
def test_live_cli_test_slot(live_config_dir: Path) -> None:
    result = runner.invoke(app, ["gateway", "test", "reasoning"])
    assert result.exit_code == 0
    assert "passed" in result.stdout.lower()
    assert "latency" in result.stdout.lower()


@pytest.mark.skipif(_skipif_no_key(), reason="OPENROUTER_API_KEY not set")
def test_live_cli_providers(live_config_dir: Path) -> None:
    result = runner.invoke(app, ["gateway", "providers"])
    assert result.exit_code == 0
    assert "openrouter" in result.stdout.lower()


@pytest.mark.skipif(_skipif_no_key(), reason="OPENROUTER_API_KEY not set")
def test_live_cli_models(live_config_dir: Path) -> None:
    result = runner.invoke(app, ["gateway", "models", "openai"])
    assert result.exit_code == 0
    assert "gpt-4o" in result.stdout


@pytest.mark.skipif(_skipif_no_key(), reason="OPENROUTER_API_KEY not set")
def test_live_cli_costs(live_config_dir: Path) -> None:
    result = runner.invoke(app, ["gateway", "costs"])
    assert result.exit_code == 0
