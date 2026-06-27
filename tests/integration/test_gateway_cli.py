from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
import respx
from typer.testing import CliRunner

from openreview_cli.app import app
from openreview_cli.config.loader import load_config

runner = CliRunner()


@pytest.fixture
def temp_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    config_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    return config_dir


def test_gateway_setup_non_interactive_success(temp_config_dir: Path) -> None:
    # Pass all 5 slots via flags
    result = runner.invoke(
        app,
        [
            "gateway",
            "setup",
            "--non-interactive",
            "--reasoning",
            "openai/gpt-4o",
            "--extraction",
            "ollama/llama3",
            "--embedding",
            "openai/text-embedding-3-small",
            "--reranking",
            "cohere/rerank-v3",
            "--graph",
            "ollama/qwen3",
        ],
    )

    assert result.exit_code == 0
    assert "configured" in result.stdout.lower()

    # Verify config.yml was updated
    config_path = temp_config_dir / "openreview" / "config.yml"
    assert config_path.exists()
    config = load_config(config_path)

    assert config["gateway"]["models"]["reasoning"]["primary"] == "openai/gpt-4o"
    assert config["gateway"]["models"]["extraction"]["primary"] == "ollama/llama3"
    assert config["gateway"]["models"]["embedding"]["primary"] == "openai/text-embedding-3-small"
    assert config["gateway"]["models"]["reranking"]["primary"] == "cohere/rerank-v3"
    assert config["gateway"]["models"]["graph"]["primary"] == "ollama/qwen3"


def test_gateway_setup_non_interactive_missing_slots(temp_config_dir: Path) -> None:
    # We pass only some slots in a fresh setup (where config.yml doesn't exist yet)
    result = runner.invoke(
        app,
        [
            "gateway",
            "setup",
            "--non-interactive",
            "--reasoning",
            "openai/gpt-4o",
            "--extraction",
            "ollama/llama3",
        ],
    )

    # Should exit with code 7 because embedding, reranking, and graph are missing and unconfigured
    assert result.exit_code == 7
    output = result.stdout + (getattr(result, "stderr", None) or "")
    assert (
        "missing" in output.lower() or "unconfigured" in output.lower() or "error" in output.lower()
    )


def test_gateway_setup_interactive_run_wizard(temp_config_dir: Path) -> None:
    # Mock SetupWizard.run to avoid actual prompt looping
    with patch("openreview_cli.gateway.wizard.SetupWizard.run") as mock_run:
        result = runner.invoke(app, ["gateway", "setup"])
        assert result.exit_code == 0
        mock_run.assert_called_once()


def test_gateway_status_no_config(temp_config_dir: Path) -> None:
    config_path = temp_config_dir / "openreview" / "config.yml"
    if config_path.exists():
        config_path.unlink()

    # Inject config state check
    with patch("openreview_cli.app._CONFIG_EXISTS_AT_START", False):
        result = runner.invoke(app, ["gateway", "status"])
        assert result.exit_code == 5
        output = result.stdout + (getattr(result, "stderr", None) or "")
        assert "no config" in output.lower() or "not configured" in output.lower()


def test_gateway_status_success(temp_config_dir: Path) -> None:
    # Configure first
    runner.invoke(
        app,
        [
            "gateway",
            "setup",
            "--non-interactive",
            "--reasoning",
            "openai/gpt-4o",
            "--extraction",
            "ollama/llama3",
            "--embedding",
            "openai/text-embedding-3-small",
            "--reranking",
            "cohere/rerank-v3",
            "--graph",
            "ollama/qwen3",
        ],
    )

    with patch("openreview_cli.app._CONFIG_EXISTS_AT_START", True):
        result = runner.invoke(app, ["gateway", "status"])
        assert result.exit_code == 0
        assert "gateway status" in result.stdout.lower()
        assert "reasoning" in result.stdout
        assert "openai/gpt-4o" in result.stdout


def test_gateway_providers(temp_config_dir: Path) -> None:
    result = runner.invoke(app, ["gateway", "providers"])
    assert result.exit_code == 0
    assert "supported providers" in result.stdout.lower()
    assert "openai" in result.stdout
    assert "ollama" in result.stdout


def test_gateway_models_success(temp_config_dir: Path) -> None:
    # Put key in auth.json to mark openai as configured
    auth_path = temp_config_dir / "openreview" / "auth.json"
    auth_path.parent.mkdir(parents=True, exist_ok=True)
    import json

    auth_path.write_text(json.dumps({"openai": "test-key"}))

    result = runner.invoke(app, ["gateway", "models", "openai"])
    assert result.exit_code == 0
    assert "available models: openai" in result.stdout.lower()
    assert "gpt-4o" in result.stdout


def test_gateway_models_not_configured(temp_config_dir: Path) -> None:
    # Ensure auth.json has no key for openai
    auth_path = temp_config_dir / "openreview" / "auth.json"
    if auth_path.exists():
        auth_path.unlink()

    result = runner.invoke(app, ["gateway", "models", "openai"])
    assert result.exit_code == 5
    output = result.stdout + (getattr(result, "stderr", None) or "")
    assert "not configured" in output.lower()


def test_gateway_set_success(temp_config_dir: Path) -> None:
    # Configure first so file exists
    runner.invoke(
        app,
        [
            "gateway",
            "setup",
            "--non-interactive",
            "--reasoning",
            "openai/gpt-4o",
            "--extraction",
            "ollama/llama3",
            "--embedding",
            "openai/text-embedding-3-small",
            "--reranking",
            "cohere/rerank-v3",
            "--graph",
            "ollama/qwen3",
        ],
    )

    result = runner.invoke(
        app,
        [
            "gateway",
            "set",
            "reasoning",
            "openai/gpt-4o-mini",
            "--fallback",
            "anthropic/claude-3-5-sonnet-latest",
            "--temperature",
            "0.2",
            "--max-tokens",
            "1000",
        ],
    )
    assert result.exit_code == 0
    assert "updated reasoning slot" in result.stdout.lower()
    assert "openai/gpt-4o-mini" in result.stdout

    # Verify config
    config_path = temp_config_dir / "openreview" / "config.yml"
    config = load_config(config_path)
    assert config["gateway"]["models"]["reasoning"]["primary"] == "openai/gpt-4o-mini"
    assert (
        config["gateway"]["models"]["reasoning"]["fallback"] == "anthropic/claude-3-5-sonnet-latest"
    )
    assert config["gateway"]["models"]["reasoning"]["params"]["temperature"] == 0.2
    assert config["gateway"]["models"]["reasoning"]["params"]["max_tokens"] == 1000


def test_gateway_set_invalid_slot(temp_config_dir: Path) -> None:
    result = runner.invoke(app, ["gateway", "set", "invalid_slot", "openai/gpt-4o"])
    assert result.exit_code == 1


def test_gateway_test_slot_success(temp_config_dir: Path) -> None:
    # Set api key first so test subcommand finds it
    auth_path = temp_config_dir / "openreview" / "auth.json"
    auth_path.parent.mkdir(parents=True, exist_ok=True)
    import json

    auth_path.write_text(json.dumps({"openai": "test-key"}))

    # Configure reasoning
    runner.invoke(
        app,
        [
            "gateway",
            "setup",
            "--non-interactive",
            "--reasoning",
            "openai/gpt-4o",
            "--extraction",
            "ollama/llama3",
            "--embedding",
            "openai/text-embedding-3-small",
            "--reranking",
            "cohere/rerank-v3",
            "--graph",
            "ollama/qwen3",
        ],
    )

    with patch("openreview_cli.gateway.wizard.validate_api_key", return_value=True):
        result = runner.invoke(app, ["gateway", "test", "reasoning"])
        assert result.exit_code == 0
        assert "test passed" in result.stdout.lower()


def test_gateway_test_slot_unconfigured(temp_config_dir: Path) -> None:
    # Write a config where reasoning slot is empty
    config_path = temp_config_dir / "openreview" / "config.yml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("""
version: 1
gateway:
  models:
    reasoning:
      primary: ""
""")
    result = runner.invoke(app, ["gateway", "test", "reasoning"])
    assert result.exit_code == 1


@respx.mock
def test_gateway_refresh_success(temp_config_dir: Path) -> None:
    url = "https://example.com/models.json"
    respx.get(url).mock(return_value=httpx.Response(200, json=[]))

    cache_dir = temp_config_dir / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    with patch("openreview_cli.gateway.registry.get_cache_dir", return_value=cache_dir):
        result = runner.invoke(app, ["gateway", "refresh"])
        assert result.exit_code == 0
        assert "cache updated" in result.stdout.lower()


def test_gateway_costs(temp_config_dir: Path) -> None:
    # Clear costs
    runner.invoke(app, ["gateway", "costs", "--clear"])

    # Verify empty
    result = runner.invoke(app, ["gateway", "costs"])
    assert result.exit_code == 0
    assert "total cost: $0.00" in result.stdout.lower()


@respx.mock
def test_gateway_install_models_success(temp_config_dir: Path) -> None:
    respx.get("http://localhost:11434/api/tags").mock(
        return_value=httpx.Response(200, json={"models": []})
    )
    respx.post("http://localhost:11434/api/pull").mock(
        return_value=httpx.Response(200, json={"status": "success"})
    )
    result = runner.invoke(app, ["gateway", "install-models", "llama3"])
    assert result.exit_code == 0
    assert "installed successfully" in result.stdout.lower()


def test_gateway_import_success(temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_OPENAI_KEY", "env-secret-openai")
    monkeypatch.setenv("TEST_ANTHROPIC_KEY", "env-secret-anthropic")

    import_file = temp_config_dir / "my-config.yml"
    import_file.write_text("""
reasoning:
  provider: "openai"
  model: "gpt-4o"
extraction:
  provider: "openai"
  model: "gpt-4o-mini"
embedding:
  provider: "ollama"
  model: "nomic-embed-text"
reranking:
  provider: "cohere"
  model: "rerank-3.5"
graph:
  provider: "ollama"
  model: "qwen3:8b"
api_key_env:
  openai: "TEST_OPENAI_KEY"
  anthropic: "TEST_ANTHROPIC_KEY"
""")

    result = runner.invoke(app, ["gateway", "import", str(import_file), "--force"])
    assert result.exit_code == 0
    assert "config imported successfully" in result.stdout.lower()

    # Verify config
    import yaml

    config = yaml.safe_load((temp_config_dir / "openreview" / "config.yml").read_text())
    assert config["gateway"]["models"]["reasoning"]["primary"] == "openai/gpt-4o"

    # Verify auth
    import json

    auth = json.loads((temp_config_dir / "openreview" / "auth.json").read_text())
    assert auth["openai"] == "env-secret-openai"
    assert auth["anthropic"] == "env-secret-anthropic"


def test_gateway_import_dry_run(temp_config_dir: Path) -> None:
    import_file = temp_config_dir / "my-config.yml"
    import_file.write_text("""
reasoning:
  provider: "openai"
  model: "gpt-4o"
extraction:
  provider: "openai"
  model: "gpt-4o-mini"
embedding:
  provider: "ollama"
  model: "nomic-embed-text"
reranking:
  provider: "cohere"
  model: "rerank-3.5"
graph:
  provider: "ollama"
  model: "qwen3:8b"
""")

    result = runner.invoke(app, ["gateway", "import", str(import_file), "--dry-run"])
    assert result.exit_code == 0
    assert "dry-run: validation passed" in result.stdout.lower()

    # Verify config.yml exists but has not been updated with the imported values
    config_path = temp_config_dir / "openreview" / "config.yml"
    assert config_path.exists()
    import yaml

    config = yaml.safe_load(config_path.read_text())
    assert config["gateway"]["models"]["reasoning"]["primary"] != "openai/gpt-4o"


def test_gateway_import_validation_error(temp_config_dir: Path) -> None:
    import_file = temp_config_dir / "my-config.yml"
    import_file.write_text("""
reasoning:
  provider: "invalid-provider"
  model: "gpt-4o"
# Missing other slots
""")

    result = runner.invoke(app, ["gateway", "import", str(import_file)])
    assert result.exit_code == 5
    output = result.stdout + (getattr(result, "stderr", None) or "")
    assert "validation errors found" in output.lower()


def test_gateway_import_file_not_found(temp_config_dir: Path) -> None:
    result = runner.invoke(app, ["gateway", "import", "/nonexistent/file.yml"])
    assert result.exit_code == 1
    assert "not found" in (result.stdout + (getattr(result, "stderr", None) or "")).lower()
