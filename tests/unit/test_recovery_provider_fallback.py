"""Unit tests for provider_fallback."""

import pytest

from openreview_cli.recovery.models import (
    PRIVACY_TIER_STANDARD,
    PRIVACY_TIER_STRICT,
    RecoveryContext,
    RecoveryError,
)
from openreview_cli.recovery.strategies.provider_fallback import (
    provider_fallback,
)


class TestProviderFallback:
    @pytest.mark.asyncio
    async def test_all_providers_exhausted(self) -> None:
        """All providers fail -> RecoveryError raised."""
        ctx = RecoveryContext(
            provider_list=["openai/gpt-4", "anthropic/claude"],
            current_provider_index=0,
        )
        with pytest.raises(RecoveryError) as excinfo:
            await provider_fallback(
                ctx,
                stage_name="generate",
                error_metadata={"last_error": "All providers failed"},
            )
        assert "All" in str(excinfo.value)
        assert "providers exhausted" in str(excinfo.value)
        assert excinfo.value.event is not None
        assert excinfo.value.event.outcome == "exhausted"

    @pytest.mark.asyncio
    async def test_privacy_tier_blocks_cloud_fallback(self) -> None:
        """Strict privacy tier skips cloud providers -> exhausted error."""
        ctx = RecoveryContext(
            provider_list=["ollama/llama3.1", "openai/gpt-4"],
            current_provider_index=0,
            user_privacy_tier=PRIVACY_TIER_STRICT,
        )
        with pytest.raises(RecoveryError) as excinfo:
            await provider_fallback(
                ctx,
                stage_name="generate",
                error_metadata={"last_error": "ollama failed"},
            )
        # Should exhaust because cloud fallback is blocked
        assert excinfo.value.event is not None
        assert excinfo.value.event.outcome == "exhausted"

    @pytest.mark.asyncio
    async def test_no_providers_configured(self) -> None:
        """Empty provider list -> error directing to setup wizard."""
        ctx = RecoveryContext(provider_list=[])
        with pytest.raises(RecoveryError) as excinfo:
            await provider_fallback(
                ctx,
                stage_name="generate",
                error_metadata={},
            )
        message = str(excinfo.value)
        assert "No providers" in message or "gateway setup" in message
        assert excinfo.value.event is not None

    @pytest.mark.asyncio
    async def test_recovery_event_recorded(self) -> None:
        """Event appended with correct outcome on exhaustion."""
        ctx = RecoveryContext(
            provider_list=["openai/gpt-4", "ollama/llama3.1"],
        )
        with pytest.raises(RecoveryError) as excinfo:
            await provider_fallback(
                ctx,
                stage_name="generate",
                error_metadata={"last_error": "openai/gpt-4 failed"},
            )
        assert excinfo.value.event is not None
        assert excinfo.value.event.outcome == "exhausted"

    @pytest.mark.asyncio
    async def test_standard_privacy_allows_cloud(self) -> None:
        """Standard privacy tier iterates cloud providers."""
        ctx = RecoveryContext(
            provider_list=["ollama/llama3.1", "openai/gpt-4"],
            user_privacy_tier=PRIVACY_TIER_STANDARD,
        )
        # Without attempt_fn, provider_fallback always exhausts
        with pytest.raises(RecoveryError) as excinfo:
            await provider_fallback(
                ctx,
                stage_name="generate",
                error_metadata={"last_error": "ollama failed"},
            )
        assert excinfo.value.event is not None
        assert excinfo.value.event.outcome == "exhausted"

    @pytest.mark.asyncio
    async def test_success_with_attempt_fn(self) -> None:
        """attempt_fn returning True triggers success event."""

        async def _try_provider(provider: str) -> bool:
            return provider == "ollama/llama3.1"

        ctx = RecoveryContext(
            provider_list=["openai/gpt-4", "ollama/llama3.1"],
            current_provider_index=0,
        )
        event = await provider_fallback(
            ctx,
            stage_name="generate",
            error_metadata={"last_error": "openai/gpt-4 failed"},
            attempt_fn=_try_provider,
        )
        assert event.outcome == "resolved"
        assert event.provider_name == "ollama/llama3.1"
        assert "succeeded" in event.message

    @pytest.mark.asyncio
    async def test_attempt_fn_exception_continues(self) -> None:
        """Exception in attempt_fn on first fallback skips to next."""
        call_order: list[str] = []

        async def _first_raises(provider: str) -> bool:
            call_order.append(provider)
            if "mixtral" in provider:
                return True
            raise ConnectionError("Connection refused")

        ctx = RecoveryContext(
            provider_list=["ollama/llama3.1", "openai/gpt-4", "ollama/mixtral"],
            current_provider_index=0,
            user_privacy_tier=PRIVACY_TIER_STANDARD,
        )
        event = await provider_fallback(
            ctx,
            stage_name="generate",
            error_metadata={"last_error": "ollama failed"},
            attempt_fn=_first_raises,
        )
        # First fallback (gpt-4) raised, second (mixtral) succeeded
        assert len(call_order) == 2
        assert "openai/gpt-4" in call_order
        assert "ollama/mixtral" in call_order
        assert event.outcome == "resolved"
        assert event.provider_name == "ollama/mixtral"
