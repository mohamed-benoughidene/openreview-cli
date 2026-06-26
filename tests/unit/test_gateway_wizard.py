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
