from dataclasses import dataclass

import httpx


@dataclass(slots=True)
class ModelInfo:
    """Information about a model available from a provider."""

    name: str
    size: int | None = None
    parameter_size: str | None = None
    quantization_level: str | None = None


class OllamaNotRunningError(Exception):
    """Raised when Ollama is not running."""

    pass


class OllamaTimeoutError(Exception):
    """Raised when Ollama connection times out."""

    pass


def ollama_discover_models(base_url: str = "http://localhost:11434") -> list[ModelInfo]:
    """
    Query GET /api/tags to discover local Ollama models.
    """
    try:
        timeout = httpx.Timeout(5.0, connect=2.0)
        response = httpx.get(f"{base_url}/api/tags", timeout=timeout)
        response.raise_for_status()
        data = response.json()

        models = []
        for item in data.get("models", []):
            name = item.get("name", "")
            size = item.get("size")
            details = item.get("details", {}) or {}
            param_size = details.get("parameter_size")
            quant = details.get("quantization_level")
            models.append(
                ModelInfo(name=name, size=size, parameter_size=param_size, quantization_level=quant)
            )
        return models
    except httpx.ConnectError as e:
        raise OllamaNotRunningError("Ollama is not running") from e
    except httpx.TimeoutException as e:
        raise OllamaTimeoutError("Ollama connection timed out") from e
    except Exception as e:
        # Fallback for other request/HTTP errors
        raise OllamaNotRunningError(f"Could not connect to Ollama: {e}") from e
