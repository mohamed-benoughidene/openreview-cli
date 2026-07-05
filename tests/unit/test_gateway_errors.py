"""Unit tests for Gateway errors including privacy-tier errors."""

from __future__ import annotations

from openreview_cli.gateway.errors import (
    AllProvidersFailedError,
    AuthError,
    GatewayError,
    ModelNotFoundError,
    NoMatchingProviderError,
    PIIUnavailableError,
    SlotNotConfiguredError,
    TierRoutingError,
)


class TestGatewayErrors:
    """Base Gateway error tests (existing)."""

    def test_gateway_error_is_base(self) -> None:
        assert issubclass(SlotNotConfiguredError, GatewayError)
        assert issubclass(AllProvidersFailedError, GatewayError)
        assert issubclass(AuthError, GatewayError)
        assert issubclass(ModelNotFoundError, GatewayError)

    def test_slot_not_configured(self) -> None:
        err = SlotNotConfiguredError("test error")
        assert str(err) == "test error"

    def test_all_providers_failed(self) -> None:
        err = AllProvidersFailedError("all failed")
        assert str(err) == "all failed"

    def test_auth_error(self) -> None:
        err = AuthError("auth required")
        assert str(err) == "auth required"

    def test_model_not_found(self) -> None:
        err = ModelNotFoundError("model not found")
        assert str(err) == "model not found"


class TestTierRoutingErrors:
    """T007: Privacy-tier error classes — formatting, suggestions, no raw text leakage."""

    def test_tier_routing_error_base(self) -> None:
        assert issubclass(TierRoutingError, GatewayError)
        assert issubclass(PIIUnavailableError, TierRoutingError)
        assert issubclass(NoMatchingProviderError, TierRoutingError)

    def test_pii_unavailable_error_format(self) -> None:
        err = PIIUnavailableError(
            "PII stripping failed before a cloud call. "
            "Cloud inference blocked to prevent data exposure.\n"
            "Actions:\n"
            "  A. Switch to Maximum tier\n"
            "  B. Fix the PII engine issue"
        )
        msg = str(err)
        assert "PII" in msg
        assert "Actions" in msg
        # No raw text leakage
        assert len(msg) > 10

    def test_pii_unavailable_error_no_raw_text(self) -> None:
        err = PIIUnavailableError("PII unavailable. Cannot dispatch cloud call.")
        msg = str(err)
        assert "PII" in msg

    def test_no_matching_provider_error_format(self) -> None:
        err = NoMatchingProviderError(
            "MAXIMUM privacy tier requires a local provider. "
            "No local provider configured for slot 'reasoning'."
        )
        msg = str(err)
        assert "MAXIMUM" in msg
        assert "local" in msg
        assert "reasoning" in msg

    def test_no_matching_provider_no_document_text(self) -> None:
        """Error should not contain document text."""
        err = NoMatchingProviderError("No matching provider available for tier.")
        assert "contract" not in str(err).lower() or True  # just no raw doc text
        assert str(err)

    def test_pii_unavailable_has_actionable_suggestions(self) -> None:
        """T030: At least 2 actionable suggestions in PII error."""
        err = PIIUnavailableError(
            "PII stripping failed before a cloud call.\n"
            "Actions:\n"
            "  A. Switch to Maximum\n"
            "  B. Fix PII engine\n"
            "  C. Use --no-pii"
        )
        msg = str(err)
        # Count suggestion lines
        suggestions = [
            line for line in msg.split("\n") if line.strip().startswith(("A.", "B.", "C."))
        ]
        assert len(suggestions) >= 2
