from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from openreview_cli.gateway.wizard import SetupWizard, validate_api_key


@pytest.fixture
def temp_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    config_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    return config_dir


def test_api_key_validation_success() -> None:
    with patch("httpx.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        assert validate_api_key("openai", "sk-valid-key") is True

        # Verify endpoint called
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        assert "headers" in kwargs
        assert "Authorization" in kwargs["headers"]
        assert "sk-valid-key" in kwargs["headers"]["Authorization"]


def test_api_key_validation_failure() -> None:
    with patch("httpx.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_get.return_value = mock_resp

        assert validate_api_key("openai", "sk-invalid-key") is False


def test_api_key_validation_timeout() -> None:
    with patch("httpx.get") as mock_get:
        mock_get.side_effect = httpx.TimeoutException("Timeout")

        assert validate_api_key("openai", "sk-timeout-key") is False


def test_slot_grouping_logic() -> None:
    # Setup wizard and verify that when slot grouping is triggered,
    # it configures extraction and graph with the same provider/model.
    wizard = SetupWizard()

    # We simulate grouping selection
    wizard.apply_grouping(provider="openai", model="gpt-4o", slot="reasoning")

    assert wizard.slots_config["reasoning"]["primary"] == "openai/gpt-4o"
    assert wizard.slots_config["extraction"]["primary"] == "openai/gpt-4o"
    assert wizard.slots_config["graph"]["primary"] == "openai/gpt-4o"


def test_wizard_arrow_key_navigation_flow(temp_config_dir: Path) -> None:
    wizard = SetupWizard(config_dir=temp_config_dir)
    from openreview_cli.gateway.providers import ModelInfo

    fake_models = [ModelInfo(name="llama3", size=4_700_000_000, parameter_size="8B")]
    select_values = iter(
        [
            "ollama",  # provider step 0 (reasoning)
            "llama3",  # ollama model select step 0
            "openai",  # provider step 2 (embedding — extraction/graph skipped by grouping)
            "text-embedding-3-small",  # model select step 2
            "cohere",  # provider step 3 (reranking)
            "rerank-v3",  # model select step 3
        ]
    )

    def fake_select(message: str, choices: list[str], default: str | None = None) -> str | None:
        try:
            return next(select_values)
        except StopIteration:
            return None

    with (
        patch("openreview_cli.gateway.wizard._select", side_effect=fake_select),
        patch("openreview_cli.gateway.wizard._confirm", return_value=True),
        patch("openreview_cli.gateway.wizard._password", return_value="sk-test"),
        patch("openreview_cli.gateway.wizard.validate_api_key", return_value=True),
        patch("openreview_cli.gateway.wizard._is_interactive", return_value=True),
        patch("openreview_cli.gateway.wizard.ollama_discover_models", return_value=fake_models),
        patch(
            "openreview_cli.gateway.wizard.get_models_for_slot",
            return_value=["text-embedding-3-small", "text-embedding-3-large"],
        ),
        patch.object(wizard, "save") as mock_save,
    ):
        wizard.run()
        assert wizard.slots_config["reasoning"]["primary"] == "ollama/llama3"
        assert wizard.slots_config["embedding"]["primary"] == "openai/text-embedding-3-small"
        assert wizard.slots_config["reranking"]["primary"] == "cohere/rerank-v3"
        mock_save.assert_called_once()


def test_wizard_cancel_on_first_step_skips_save(temp_config_dir: Path) -> None:
    wizard = SetupWizard(config_dir=temp_config_dir)

    with (
        patch("openreview_cli.gateway.wizard._select", return_value=None),
        patch("openreview_cli.gateway.wizard._confirm", return_value=False),
        patch("openreview_cli.gateway.wizard.ollama_discover_models", return_value=[]),
        patch.object(wizard, "save") as mock_save,
    ):
        wizard.run()
        mock_save.assert_not_called()
