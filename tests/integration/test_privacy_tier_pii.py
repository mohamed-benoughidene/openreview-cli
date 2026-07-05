"""Integration tests for PII failure scenarios across tiers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from openreview_cli.gateway.errors import PIIUnavailableError
from openreview_cli.gateway.tier_config import TierConfig
from openreview_cli.gateway.tier_router import TierRouter


class _MockPiiEngineAvailable:
    """Duck-type mock for PiiEngine that reports available."""

    def is_available(self) -> bool:
        return True


class _MockPiiEngineUnavailable:
    """Duck-type mock for PiiEngine that reports unavailable."""

    def is_available(self) -> bool:
        return False


class _MockCostTracker:
    def log_call(self, *args: Any, **kwargs: Any) -> None:
        pass


class _MockGateway:
    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._config = config or {"gateway": {"models": {}}}
        self._cost_tracker = _MockCostTracker()
        self._data_path = Path("/tmp/test.db")
        self.chat_calls: list[Any] = []
        self.embed_calls: list[Any] = []

    def chat(self, *args: Any, **kwargs: Any) -> str:
        self.chat_calls.append((args, kwargs))
        return "response"

    def embed(self, *args: Any, **kwargs: Any) -> list[list[float]]:
        self.embed_calls.append((args, kwargs))
        return [[0.1, 0.2, 0.3]]

    def _get_litellm_kwargs(self, slot: str) -> dict[str, Any]:
        model = ""
        models = self._config.get("gateway", {}).get("models", {})
        slot_cfg = models.get(slot, {})
        if isinstance(slot_cfg, dict):
            model = slot_cfg.get("primary", "")
        return {"model": model}


class TestPIIFailureIntegration:
    """US4 integration: PII failure blocks cloud, Maximum unaffected."""

    def test_balanced_blocked_when_pii_fails(self) -> None:
        """Balanced tier blocks cloud LLM when PII unavailable."""
        gw = _MockGateway(
            {
                "gateway": {
                    "models": {
                        "reasoning": {"primary": "openai/gpt-4o"},
                    }
                }
            }
        )
        config = TierConfig(tier="balanced", tier_source="config")
        router = TierRouter(gw, config, pii_engine=_MockPiiEngineUnavailable())  # type: ignore[arg-type]

        with pytest.raises(PIIUnavailableError) as excinfo:
            router.chat("reasoning", [{"role": "user", "content": "sensitive data"}])

        msg = str(excinfo.value)
        assert "PII" in msg
        assert len(gw.chat_calls) == 0  # fail-closed

    def test_performance_blocked_when_pii_fails(self) -> None:
        """Performance tier blocks all cloud calls when PII unavailable."""
        gw = _MockGateway(
            {
                "gateway": {
                    "models": {
                        "reasoning": {"primary": "openai/gpt-4o"},
                        "embedding": {"primary": "openai/text-embedding-3-small"},
                    }
                }
            }
        )
        config = TierConfig(tier="performance", tier_source="config")
        router = TierRouter(gw, config, pii_engine=_MockPiiEngineUnavailable())  # type: ignore[arg-type]

        with pytest.raises(PIIUnavailableError):
            router.chat("reasoning", [{"role": "user", "content": "secret"}])
        with pytest.raises(PIIUnavailableError):
            router.embed("embedding", ["secret"])
        assert len(gw.chat_calls) == 0
        assert len(gw.embed_calls) == 0

    def test_maximum_unaffected_when_pii_fails(self) -> None:
        """Maximum tier works without PII engine."""
        gw = _MockGateway(
            {
                "gateway": {
                    "models": {
                        "reasoning": {"primary": "ollama/qwen3:8b"},
                        "embedding": {"primary": "ollama/nomic-embed-text"},
                    }
                }
            }
        )
        config = TierConfig(tier="maximum", tier_source="config")
        router = TierRouter(gw, config, pii_engine=_MockPiiEngineUnavailable())  # type: ignore[arg-type]

        router.chat("reasoning", [{"role": "user", "content": "data"}])
        router.embed("embedding", ["data"])
        assert len(gw.chat_calls) == 1
        assert len(gw.embed_calls) == 1

    def test_error_contains_actionable_suggestions(self) -> None:
        """Error includes ≥2 actionable suggestions and no document text."""
        gw = _MockGateway(
            {
                "gateway": {
                    "models": {
                        "reasoning": {"primary": "openai/gpt-4o"},
                    }
                }
            }
        )
        config = TierConfig(tier="balanced", tier_source="config")
        router = TierRouter(gw, config, pii_engine=_MockPiiEngineUnavailable())  # type: ignore[arg-type]

        with pytest.raises(PIIUnavailableError) as excinfo:
            router.chat("reasoning", [{"role": "user", "content": "my secret text"}])

        msg = str(excinfo.value)
        assert "PII" in msg
        # At least 2 actionable suggestions
        suggestions = [
            line for line in msg.split("\n") if line.strip().startswith(("A.", "B.", "C."))
        ]
        assert len(suggestions) >= 2
        # No document text
        assert "my secret text" not in msg
