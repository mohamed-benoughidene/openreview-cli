"""Shared mock classes for gateway testing."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class _MockMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _MockChoice:
    def __init__(self, content: str) -> None:
        self.message = _MockMessage(content)


class _MockCostTracker:
    def log_call(self, *args: Any, **kwargs: Any) -> None:
        pass


class _MockPiiEngineAvailable:
    """Duck-type mock for PiiEngine that reports available."""

    def is_available(self) -> bool:
        return True


class _MockPiiEngineUnavailable:
    """Duck-type mock for PiiEngine that reports unavailable."""

    def is_available(self) -> bool:
        return False


class _MockGateway:
    """Minimal Gateway mock that records calls and returns canned responses."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._config = config or {"gateway": {"models": {}}}
        self.chat_calls: list[tuple[str, list[dict[str, str]], dict[str, Any]]] = []
        self.embed_calls: list[tuple[str, list[str], dict[str, Any]]] = []
        self._cost_tracker = _MockCostTracker()
        self._data_path = Path("/tmp/test.db")

    def chat(
        self,
        slot: str,
        messages: list[dict[str, str]],
        *,
        session_id: str | None = None,
        **kwargs: Any,
    ) -> str:
        self.chat_calls.append((slot, messages, {"session_id": session_id, **kwargs}))
        return "mock response"

    def embed(
        self,
        slot: str,
        texts: list[str],
        *,
        session_id: str | None = None,
    ) -> list[list[float]]:
        self.embed_calls.append((slot, texts, {"session_id": session_id}))
        return [[0.1, 0.2, 0.3]]

    def _get_litellm_kwargs(self, slot: str) -> dict[str, Any]:
        """Return kwargs that can be inspected for model/provider info."""
        model = ""
        models = self._config.get("gateway", {}).get("models", {})
        slot_cfg = models.get(slot, {})
        if isinstance(slot_cfg, dict):
            model = slot_cfg.get("primary", "")
        return {"model": model}
