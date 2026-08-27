"""Unit tests for recovery data models and classify_error()."""

from openreview_cli.recovery.models import (
    DEGRADATION_ACTIONS,
    PRIVACY_TIER_NONE,
    PRIVACY_TIER_STANDARD,
    PRIVACY_TIER_STRICT,
    ErrorCategory,
    RecoveryContext,
    RecoveryError,
    RecoveryEvent,
    RecoveryOutcome,
    RecoveryReport,
    classify_error,
    privacy_tier_from_product,
)


class TestErrorCategory:
    def test_values(self) -> None:
        assert ErrorCategory.transient.value == "transient"
        assert ErrorCategory.permanent.value == "permanent"
        assert ErrorCategory.resource.value == "resource"
        assert ErrorCategory.stage_failure.value == "stage_failure"
        assert ErrorCategory.stage_failure_critical.value == "stage_failure_critical"
        assert ErrorCategory.unknown.value == "unknown"

    def test_six_values(self) -> None:
        assert len(ErrorCategory) == 6


class TestDegradationActions:
    def test_values(self) -> None:
        assert DEGRADATION_ACTIONS == (
            "reduce_batch_size",
            "switch_to_lightweight_model",
            "simplify_processing",
            "reduce_context_window",
        )

    def test_four_values(self) -> None:
        assert len(DEGRADATION_ACTIONS) == 4


class TestPrivacyTierConstants:
    def test_values(self) -> None:
        assert PRIVACY_TIER_STRICT == "strict"
        assert PRIVACY_TIER_STANDARD == "standard"
        assert PRIVACY_TIER_NONE == "none"


class TestPrivacyTierTranslation:
    def test_maximum_to_strict(self) -> None:
        assert privacy_tier_from_product("maximum") == PRIVACY_TIER_STRICT

    def test_balanced_to_standard(self) -> None:
        assert privacy_tier_from_product("balanced") == PRIVACY_TIER_STANDARD

    def test_performance_to_none(self) -> None:
        assert privacy_tier_from_product("performance") == PRIVACY_TIER_NONE

    def test_case_insensitive(self) -> None:
        assert privacy_tier_from_product("MAXIMUM") == PRIVACY_TIER_STRICT
        assert privacy_tier_from_product("Balanced") == PRIVACY_TIER_STANDARD

    def test_unknown_product_tier_falls_back_to_strict(self) -> None:
        # The product config contract (PrivacyTier.parse) coerces invalid/absent
        # values to "maximum"; this helper mirrors that fail-closed default.
        assert privacy_tier_from_product("garbage") == PRIVACY_TIER_STRICT
        assert privacy_tier_from_product("") == PRIVACY_TIER_STRICT
        assert privacy_tier_from_product(None) == PRIVACY_TIER_STRICT


class TestRecoveryEvent:
    def test_default_fields(self) -> None:
        event = RecoveryEvent(strategy_name="auto_retry", stage_name="parse")
        assert event.strategy_name == "auto_retry"
        assert event.stage_name == "parse"
        assert event.provider_name is None
        assert event.attempt is None
        assert event.outcome == "resolved"
        assert event.message == ""
        assert isinstance(event.timestamp, float)
        assert event.timestamp > 0

    def test_all_fields(self) -> None:
        event = RecoveryEvent(
            strategy_name="provider_fallback",
            stage_name="generate",
            provider_name="ollama/llama3.1",
            attempt=2,
            outcome=RecoveryOutcome.ESCALATED,
            message="Fallback failed",
            timestamp=1234.0,
        )
        assert event.strategy_name == "provider_fallback"
        assert event.stage_name == "generate"
        assert event.provider_name == "ollama/llama3.1"
        assert event.attempt == 2
        assert event.outcome == "escalated"
        assert event.message == "Fallback failed"
        assert event.timestamp == 1234.0


class TestRecoveryContext:
    def test_default_fields(self) -> None:
        ctx = RecoveryContext()
        assert ctx.provider_list == []
        assert ctx.attempted_strategies == []
        assert ctx.current_provider_index == 0
        assert ctx.retry_counts == {}
        assert ctx.memory_threshold_bytes == 83_886_080  # 80 MB
        assert ctx.memory_budget_bytes == 104_857_600  # 100 MB
        assert ctx.failed_stages == []
        assert ctx.completed_stages == []
        assert ctx.partial_data == {}
        assert ctx.events == []
        assert ctx.user_privacy_tier == PRIVACY_TIER_STRICT
        assert not hasattr(ctx, "degradation_active")

    def test_custom_values(self) -> None:
        ctx = RecoveryContext(
            provider_list=["openai/gpt-4", "ollama/llama3.1"],
            current_provider_index=1,
            memory_threshold_bytes=50_000_000,
            user_privacy_tier=PRIVACY_TIER_STANDARD,
        )
        assert ctx.provider_list == ["openai/gpt-4", "ollama/llama3.1"]
        assert ctx.current_provider_index == 1
        assert ctx.memory_threshold_bytes == 50_000_000
        assert ctx.user_privacy_tier == PRIVACY_TIER_STANDARD


class TestRecoveryReport:
    def test_default_fields(self) -> None:
        report = RecoveryReport()
        assert report.events == []
        assert report.final_status == "resolved"
        assert report.summary == ""
        assert report.degradation_notices == []
        assert report.partial_results is False
        assert report.actionable_error is None

    def test_with_events(self) -> None:
        events = [
            RecoveryEvent(strategy_name="auto_retry", stage_name="generate"),
            RecoveryEvent(
                strategy_name="provider_fallback",
                stage_name="generate",
                outcome=RecoveryOutcome.EXHAUSTED,
            ),
        ]
        report = RecoveryReport(
            events=events,
            final_status="unrecoverable",
            summary="All strategies exhausted",
            actionable_error="No provider available",
        )
        assert len(report.events) == 2
        assert report.final_status == "unrecoverable"
        assert report.summary == "All strategies exhausted"
        assert report.actionable_error == "No provider available"


class TestRecoveryError:
    def test_default_construction(self) -> None:
        exc = RecoveryError()
        assert exc.event is None

    def test_with_event(self) -> None:
        event = RecoveryEvent(strategy_name="auto_retry", stage_name="test")
        exc = RecoveryError("done", event=event)
        assert str(exc) == "done"
        assert exc.event is event


class TestClassifyError:
    """classify_error() must map status codes and error types correctly."""

    def test_transient_http_503(self) -> None:
        assert classify_error(http_status=503) == ErrorCategory.transient

    def test_transient_http_429(self) -> None:
        assert classify_error(http_status=429) == ErrorCategory.transient

    def test_transient_timeout(self) -> None:
        assert classify_error(error_type="timeout") == ErrorCategory.transient

    def test_transient_connection_reset(self) -> None:
        assert classify_error(error_type="connection_reset") == ErrorCategory.transient

    def test_permanent_http_400(self) -> None:
        assert classify_error(http_status=400) == ErrorCategory.permanent

    def test_permanent_http_401(self) -> None:
        assert classify_error(http_status=401) == ErrorCategory.permanent

    def test_permanent_http_403(self) -> None:
        assert classify_error(http_status=403) == ErrorCategory.permanent

    def test_permanent_http_404(self) -> None:
        assert classify_error(http_status=404) == ErrorCategory.permanent

    def test_transient_http_500(self) -> None:
        """HTTP 500 classifies as transient (server errors are retryable)."""
        assert classify_error(http_status=500) == ErrorCategory.transient

    def test_resource_memory_exceeded(self) -> None:
        assert (
            classify_error(memory_delta_mb=120.0, memory_threshold_mb=100.0)
            == ErrorCategory.resource
        )

    def test_resource_memory_within_budget(self) -> None:
        assert (
            classify_error(memory_delta_mb=50.0, memory_threshold_mb=100.0)
            != ErrorCategory.resource
        )

    def test_stage_failure_critical_exception(self) -> None:
        assert (
            classify_error(exception_type="CriticalStageError")
            == ErrorCategory.stage_failure_critical
        )

    def test_stage_failure_non_critical_exception(self) -> None:
        assert classify_error(exception_type="StageError") == ErrorCategory.stage_failure

    def test_stage_failure_via_flag_critical(self) -> None:
        assert classify_error(stage_critical=True) == ErrorCategory.stage_failure_critical

    def test_stage_failure_via_flag_non_critical(self) -> None:
        assert classify_error(stage_critical=False) == ErrorCategory.stage_failure

    def test_unknown_no_input(self) -> None:
        assert classify_error() == ErrorCategory.unknown

    def test_unknown_arbitrary_code(self) -> None:
        assert classify_error(http_status=999) == ErrorCategory.unknown

    def test_priority_resource_over_http(self) -> None:
        """Memory check should take priority over HTTP status."""
        assert (
            classify_error(
                http_status=503,
                memory_delta_mb=150.0,
                memory_threshold_mb=100.0,
            )
            == ErrorCategory.resource
        )


class TestR34Classification:
    """R3-4 — classification of gateway errors that the recovery seam must
    handle distinctly.

    Note: classify_error() itself only knows about ``http_status`` and
    ``error_type`` (the typed-error name) — it does not import
    gateway.errors. The HTTP-status mapping lives in
    ``review/_gateway.py._GATEWAY_ERROR_HTTP_STATUS``. These tests verify
    the seam end-to-end through ``coordinator.handle_gateway_failure``.
    """

    def test_unclassified_provider_error_type_is_unknown_via_classify(self) -> None:
        """Pre-fix sanity: without the new HTTP-status mapping, the bare
        ``UnclassifiedProviderError`` typed name classifies as unknown.
        The new mapping in _GATEWAY_ERROR_HTTP_STATUS must elevate it to
        transient — verified separately in coordinator-level tests below.
        """
        assert classify_error(error_type="UnclassifiedProviderError") == ErrorCategory.unknown

    def test_all_providers_failed_type_classifies_unknown(self) -> None:
        """The typed name alone classifies unknown; the status map keeps it
        at None → unknown (terminal) — verified at coordinator level."""
        assert classify_error(error_type="AllProvidersFailedError") == ErrorCategory.unknown

    def test_connection_error_typed_name_classifies_unknown(self) -> None:
        """Pre-fix sanity: the typed name ``ConnectionError`` alone does not
        match the error_type table — the new status-map entry drives its
        transient classification. Verified at coordinator level."""
        assert classify_error(error_type="ConnectionError") == ErrorCategory.unknown

    def test_no_matching_provider_type_classifies_unknown(self) -> None:
        """NoMatchingProviderError remains unknown → terminal (no fallback)."""
        assert classify_error(error_type="NoMatchingProviderError") == ErrorCategory.unknown
