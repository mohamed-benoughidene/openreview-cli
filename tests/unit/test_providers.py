from unittest.mock import MagicMock, patch

import httpx
import pytest

from openreview_cli.gateway.providers import (
    ModelInfo,
    OllamaNotRunningError,
    OllamaTimeoutError,
    ollama_discover_models,
)


def test_discover_models_success() -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "models": [
            {
                "name": "llama3.1:8b",
                "size": 4676845389,
                "details": {"parameter_size": "8B", "quantization_level": "Q4_K_M"},
            },
            {
                "name": "nomic-embed-text:latest",
                "size": 274182741,
                "details": {"parameter_size": "137M", "quantization_level": "Q8_0"},
            },
        ]
    }

    with patch("httpx.get", return_value=mock_response) as mock_get:
        models = ollama_discover_models()

    mock_get.assert_called_once()
    assert len(models) == 2

    m1 = models[0]
    assert isinstance(m1, ModelInfo)
    assert m1.name == "llama3.1:8b"
    assert m1.size == 4676845389
    assert m1.parameter_size == "8B"
    assert m1.quantization_level == "Q4_K_M"

    m2 = models[1]
    assert m2.name == "nomic-embed-text:latest"
    assert m2.parameter_size == "137M"


def test_discover_models_empty_list() -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = {"models": []}

    with patch("httpx.get", return_value=mock_response):
        models = ollama_discover_models()

    assert models == []


def test_discover_models_connect_error_raises_not_running() -> None:
    with (
        patch("httpx.get", side_effect=httpx.ConnectError("Connection refused")),
        pytest.raises(OllamaNotRunningError, match="Ollama is not running"),
    ):
        ollama_discover_models()


def test_discover_models_timeout_raises_timeout_error() -> None:
    with (
        patch("httpx.get", side_effect=httpx.TimeoutException("Timed out")),
        pytest.raises(OllamaTimeoutError, match="Ollama connection timed out"),
    ):
        ollama_discover_models()


def test_discover_models_http_error_raises_not_running() -> None:
    with (
        patch(
            "httpx.get",
            side_effect=httpx.HTTPStatusError("500", request=MagicMock(), response=MagicMock()),
        ),
        pytest.raises(OllamaNotRunningError),
    ):
        ollama_discover_models()


def test_discover_models_custom_base_url() -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = {"models": [{"name": "test-model"}]}

    with patch("httpx.get", return_value=mock_response) as mock_get:
        ollama_discover_models(base_url="http://192.168.1.100:11434")

    args, _ = mock_get.call_args
    assert args[0] == "http://192.168.1.100:11434/api/tags"


def test_discover_models_missing_details_field() -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = {"models": [{"name": "minimal-model", "size": 12345}]}

    with patch("httpx.get", return_value=mock_response):
        models = ollama_discover_models()

    assert len(models) == 1
    assert models[0].name == "minimal-model"
    assert models[0].parameter_size is None
    assert models[0].quantization_level is None


def test_model_info_dataclass_defaults() -> None:
    m = ModelInfo(name="test")
    assert m.size is None
    assert m.parameter_size is None
    assert m.quantization_level is None
