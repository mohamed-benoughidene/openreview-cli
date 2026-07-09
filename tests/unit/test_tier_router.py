"""Unit tests for TierRouter, ProviderLocationClassifier, and tier enforcement."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from openreview_cli.gateway.errors import (
    NoMatchingProviderError,
    PIIUnavailableError,
)
from openreview_cli.gateway.tier_config import TierConfig
from openreview_cli.gateway.tier_router import TierRouter
from tests.helpers.mock_gateway import (
    _MockGateway,
    _MockPiiEngineAvailable,
    _MockPiiEngineUnavailable,
)

# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_router(
    tier: str = "maximum",
    pii_available: bool = True,
    gateway: _MockGateway | None = None,
) -> tuple[TierRouter, _MockGateway]:
    gw = gateway or _MockGateway()
    config = TierConfig(tier=tier, tier_source="config")
    pii_engine = _MockPiiEngineAvailable() if pii_available else _MockPiiEngineUnavailable()
    router = TierRouter(gw, config, pii_engine=pii_engine)  # type: ignore[arg-type]
    return router, gw


def _config_with_provider(
    slot: str,
    model: str,
    api_base: str = "",
) -> dict[str, Any]:
    """Build a config dict with one model slot."""
    cfg: dict[str, Any] = {"gateway": {"models": {}}}
    slot_cfg: dict[str, Any] = {"primary": model}
    if api_base:
        slot_cfg["api_base"] = api_base
    cfg["gateway"]["models"][slot] = slot_cfg
    return cfg


# ── ProviderLocationClassifier Tests (T005) ─────────────────────────────────


class TestProviderLocationClassifier:
    """T005: URL-based provider classification."""

    def test_classify_localhost(self) -> None:
        result = TierRouter.classify_provider({"api_base": "http://localhost:11434"})
        assert result == "local"

    def test_classify_loopback_ip(self) -> None:
        result = TierRouter.classify_provider({"api_base": "http://127.0.0.1:11434"})
        assert result == "local"

    def test_classify_ipv6_loopback(self) -> None:
        result = TierRouter.classify_provider({"api_base": "http://[::1]:11434"})
        assert result == "local"

    def test_classify_unix_socket(self) -> None:
        result = TierRouter.classify_provider({"api_base": "/var/run/ollama.sock"})
        assert result == "local"

    def test_classify_external_url(self) -> None:
        result = TierRouter.classify_provider({"api_base": "https://api.openai.com"})
        assert result == "cloud"

    def test_classify_explicit_local_flag(self) -> None:
        result = TierRouter.classify_provider({"local": True})
        assert result == "local"

    def test_classify_explicit_cloud_flag(self) -> None:
        result = TierRouter.classify_provider(
            {"local": False, "api_base": "http://localhost:11434"}
        )
        assert result == "cloud"

    def test_classify_no_url_defaults_cloud(self) -> None:
        result = TierRouter.classify_provider({})
        assert result == "cloud"


# ── Maximum Tier Tests (US1: T014, T015) ────────────────────────────────────


class TestMaximumTier:
    """US1 — Maximum tier: all inference local, cloud blocked."""

    def test_rejects_cloud_provider(self) -> None:
        """T014: Maximum tier rejects cloud provider call."""
        router, gw = _make_router(tier="maximum")
        gw._config = _config_with_provider("reasoning", "openai/gpt-4")
        with pytest.raises(NoMatchingProviderError) as excinfo:
            router.chat("reasoning", [{"role": "user", "content": "Hi"}])
        assert "MAXIMUM" in str(excinfo.value)
        assert "local" in str(excinfo.value)

    def test_allows_local_provider(self) -> None:
        """T015: Maximum tier allows local provider call."""
        router, gw = _make_router(tier="maximum")
        gw._config = _config_with_provider("reasoning", "ollama/llama3.1")
        result = router.chat("reasoning", [{"role": "user", "content": "Hi"}])
        assert result == "mock response"
        assert len(gw.chat_calls) == 1

    def test_blocks_cloud_embedding(self) -> None:
        """Maximum tier blocks cloud embedding provider."""
        router, gw = _make_router(tier="maximum")
        gw._config = _config_with_provider("embedding", "openai/text-embedding-3-small")
        with pytest.raises(NoMatchingProviderError):
            router.embed("embedding", ["test text"])

    def test_allows_local_embedding(self) -> None:
        """Maximum tier allows local embedding provider."""
        router, gw = _make_router(tier="maximum")
        gw._config = _config_with_provider("embedding", "ollama/nomic-embed-text")
        result = router.embed("embedding", ["test text"])
        assert result == [[0.1, 0.2, 0.3]]
        assert len(gw.embed_calls) == 1


# ── Balanced Tier Tests (US2: T020, T021) ───────────────────────────────────


class TestBalancedTier:
    """US2 — Balanced tier: local embeddings, cloud LLM with PII stripped."""

    def test_routes_embeddings_to_local(self) -> None:
        """T020: Balanced routes embeddings to local provider."""
        router, gw = _make_router(tier="balanced")
        gw._config = _config_with_provider("embedding", "ollama/nomic-embed-text")
        result = router.embed("embedding", ["test"])
        assert result == [[0.1, 0.2, 0.3]]
        assert len(gw.embed_calls) == 1

    def test_routes_llm_to_cloud_with_pii_stripped(self) -> None:
        """T021: Balanced routes LLM to cloud (PII verified via mock)."""
        router, gw = _make_router(tier="balanced", pii_available=True)
        gw._config = _config_with_provider("reasoning", "openai/gpt-4")
        result = router.chat(
            "reasoning", [{"role": "user", "content": "test"}, {"role": "user", "content": "more"}]
        )
        assert result == "mock response"
        assert len(gw.chat_calls) == 1

    def test_blocks_cloud_embedding(self) -> None:
        """Balanced blocks cloud embedding provider."""
        router, gw = _make_router(tier="balanced")
        gw._config = _config_with_provider("embedding", "openai/text-embedding-3-small")
        with pytest.raises(NoMatchingProviderError):
            router.embed("embedding", ["test"])

    def test_allows_local_embedding(self) -> None:
        """Balanced allows local embedding."""
        router, gw = _make_router(tier="balanced")
        gw._config = _config_with_provider("embedding", "ollama/nomic-embed-text")
        result = router.embed("embedding", ["test"])
        assert result == [[0.1, 0.2, 0.3]]


# ── Performance Tier Tests (US3: T024, T025) ────────────────────────────────


class TestPerformanceTier:
    """US3 — Performance tier: all calls cloud, PII stripped."""

    def test_routes_chat_to_cloud(self) -> None:
        """T024: Performance routes chat to cloud."""
        router, gw = _make_router(tier="performance", pii_available=True)
        gw._config = _config_with_provider("reasoning", "openai/gpt-4")
        result = router.chat("reasoning", [{"role": "user", "content": "Hi"}])
        assert result == "mock response"
        assert len(gw.chat_calls) == 1

    def test_routes_embedding_to_cloud(self) -> None:
        """T024: Performance routes embedding to cloud."""
        router, gw = _make_router(tier="performance", pii_available=True)
        gw._config = _config_with_provider("embedding", "openai/text-embedding-3-small")
        result = router.embed("embedding", ["test"])
        assert result == [[0.1, 0.2, 0.3]]
        assert len(gw.embed_calls) == 1

    def test_strips_pii_before_chat(self) -> None:
        """T025: Performance strips PII before chat (verified via pii_available gate)."""
        router, gw = _make_router(tier="performance", pii_available=True)
        gw._config = _config_with_provider("reasoning", "openai/gpt-4")
        result = router.chat("reasoning", [{"role": "user", "content": "John Smith"}])
        assert result == "mock response"

    def test_strips_pii_before_embedding(self) -> None:
        """T025: Performance strips PII before embedding."""
        router, gw = _make_router(tier="performance", pii_available=True)
        gw._config = _config_with_provider("embedding", "openai/text-embedding-3-small")
        result = router.embed("embedding", ["John Smith data"])
        assert result == [[0.1, 0.2, 0.3]]


# ── PII Unavailable Tests (US4: T028, T029, T030) ───────────────────────────


class TestPIIUnavailable:
    """US4 — PII engine failure blocks cloud calls."""

    def test_pii_unavailable_blocks_balanced_chat(self) -> None:
        """T028: PIIUnavailableError raised when PII engine fails on Balanced."""
        router, gw = _make_router(tier="balanced", pii_available=False)
        gw._config = _config_with_provider("reasoning", "openai/gpt-4")
        with pytest.raises(PIIUnavailableError) as excinfo:
            router.chat("reasoning", [{"role": "user", "content": "Hi"}])
        assert "PII" in str(excinfo.value)
        assert len(gw.chat_calls) == 0  # no cloud call dispatched

    def test_maximum_unaffected_by_pii_failure(self) -> None:
        """T029: Maximum tier works even when PII unavailable."""
        router, gw = _make_router(tier="maximum", pii_available=False)
        gw._config = _config_with_provider("reasoning", "ollama/llama3.1")
        result = router.chat("reasoning", [{"role": "user", "content": "Hi"}])
        assert result == "mock response"
        assert len(gw.chat_calls) == 1

    def test_error_contains_actionable_suggestions(self) -> None:
        """T030: PII failure error includes actionable suggestions."""
        router, gw = _make_router(tier="balanced", pii_available=False)
        gw._config = _config_with_provider("reasoning", "openai/gpt-4")
        with pytest.raises(PIIUnavailableError) as excinfo:
            router.chat("reasoning", [{"role": "user", "content": "test"}])
        msg = str(excinfo.value)
        assert "PII" in msg
        # At least 2 actionable suggestions
        assert "Switch" in msg or "switch" in msg
        assert "Maximum" in msg
        # No document text in error
        assert "test" not in msg

    def test_performance_unaffected_by_pii_failure_before_cloud(self) -> None:
        """Performance tier also blocked when PII unavailable."""
        router, gw = _make_router(tier="performance", pii_available=False)
        gw._config = _config_with_provider("reasoning", "openai/gpt-4")
        with pytest.raises(PIIUnavailableError):
            router.chat("reasoning", [{"role": "user", "content": "Hi"}])
        assert len(gw.chat_calls) == 0

    def test_error_contains_no_document_text(self) -> None:
        """T030: error message does not contain document text."""
        router, gw = _make_router(tier="balanced", pii_available=False)
        gw._config = _config_with_provider("reasoning", "openai/gpt-4")
        with pytest.raises(PIIUnavailableError) as excinfo:
            router.chat("reasoning", [{"role": "user", "content": "my secret text"}])
        msg = str(excinfo.value)
        assert "my secret text" not in msg


# ── T040: Memory Profile (POL) ──────────────────────────────────────────────


class TestTierRouterMemory:
    """T040: Assert TierRouter overhead <5 MB peak."""

    @pytest.mark.memory
    def test_maximum_tier_peak_memory_budget(self) -> None:
        """T040: TierRouter with Maximum tier must stay under 5 MB peak overhead."""
        import tracemalloc

        tracemalloc.start()
        try:
            _snap_before = tracemalloc.take_snapshot()

            router, gw = _make_router(tier="maximum")
            gw._config = _config_with_provider("reasoning", "ollama/llama3.1")
            router.chat("reasoning", [{"role": "user", "content": "Hi"}])

            _snap_after = tracemalloc.take_snapshot()
            stats = _snap_after.compare_to(_snap_before, "lineno")
            peak_delta = sum(s.size_diff for s in stats)
        finally:
            tracemalloc.stop()

        peak_mb = peak_delta / (1024 * 1024)
        assert peak_mb < 5, (
            f"TierRouter.Maximum.chat() memory delta {peak_mb:.2f} MB exceeds 5 MB budget"
        )


# ── TierRouter + TierTracker (D-36 / D-50) ──────────────────────────────────


class TestTierRouterWithTracker:
    """TierRouter with TierTracker — per-operation tier change detection."""

    def test_no_tracker_returns_none(self) -> None:
        """check_tier_change returns None when no tracker configured."""
        router, _ = _make_router(tier="maximum")
        assert router.check_tier_change() is None

    def test_first_run_no_change(self, tmp_path: Path) -> None:
        """No previous .last_tier — no change message."""
        from openreview_cli.gateway.tier_tracker import TierTracker

        tracker = TierTracker(state_path=tmp_path / ".last_tier")
        gw = _MockGateway()
        config = TierConfig(tier="maximum", tier_source="config")
        pii_engine = _MockPiiEngineAvailable()
        router = TierRouter(gw, config, pii_engine=pii_engine, tracker=tracker)  # type: ignore[arg-type]
        assert router.check_tier_change() is None

    def test_tier_change_detected(self, tmp_path: Path) -> None:
        """Change from previous tier returns diff message."""
        import json

        from openreview_cli.gateway.tier_tracker import TierTracker

        state = tmp_path / ".last_tier"
        state.write_text(json.dumps({"tier": "maximum"}))

        tracker = TierTracker(state_path=state)
        gw = _MockGateway()
        config = TierConfig(tier="balanced", tier_source="config")
        pii_engine = _MockPiiEngineAvailable()
        router = TierRouter(gw, config, pii_engine=pii_engine, tracker=tracker)  # type: ignore[arg-type]
        msg = router.check_tier_change()
        assert msg == "Tier changed from maximum to balanced"

    def test_same_tier_no_message(self, tmp_path: Path) -> None:
        """Same tier as previous — no change message."""
        import json

        from openreview_cli.gateway.tier_tracker import TierTracker

        state = tmp_path / ".last_tier"
        state.write_text(json.dumps({"tier": "balanced"}))

        tracker = TierTracker(state_path=state)
        gw = _MockGateway()
        config = TierConfig(tier="balanced", tier_source="config")
        pii_engine = _MockPiiEngineAvailable()
        router = TierRouter(gw, config, pii_engine=pii_engine, tracker=tracker)  # type: ignore[arg-type]
        assert router.check_tier_change() is None

    def test_recorded_tier_updated(self, tmp_path: Path) -> None:
        """After check_tier_change, stored tier is updated."""
        import json

        from openreview_cli.gateway.tier_tracker import TierTracker

        state = tmp_path / ".last_tier"
        state.write_text(json.dumps({"tier": "maximum"}))

        tracker = TierTracker(state_path=state)
        gw = _MockGateway()
        config = TierConfig(tier="performance", tier_source="config")
        pii_engine = _MockPiiEngineAvailable()
        router = TierRouter(gw, config, pii_engine=pii_engine, tracker=tracker)  # type: ignore[arg-type]
        router.check_tier_change()

        data = json.loads(state.read_text())
        assert data["tier"] == "performance"
