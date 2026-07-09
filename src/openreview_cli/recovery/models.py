"""Core data models for the error recovery framework.

Defines ErrorCategory, degradation action constants, privacy tier,
RecoveryEvent, RecoveryContext, RecoveryReport, classify_error(),
and suggestion_for().
"""

from __future__ import annotations

import dataclasses
import enum
import time
from dataclasses import dataclass, field
from typing import Any


class RecoveryOutcome(enum.StrEnum):
    """Outcome of a recovery action (FR-06, F6).

    Used as the type for ``RecoveryEvent.outcome`` for consistency with
    ``RecoverySignal`` (both are ``StrEnum``).
    """

    RESOLVED = "resolved"
    ESCALATED = "escalated"
    EXHAUSTED = "exhausted"
    DEGRADED = "degraded"
    UNRECOVERABLE = "unrecoverable"


class ErrorCategory(enum.Enum):
    """Nature of a failure — determines which recovery strategy applies."""

    transient = "transient"
    permanent = "permanent"
    resource = "resource"
    stage_failure = "stage_failure"
    stage_failure_critical = "stage_failure_critical"
    unknown = "unknown"


# Degradation actions applied in least-disruptive order (FR-03).
DEGRADATION_ACTIONS: tuple[str, ...] = (
    "reduce_batch_size",
    "switch_to_lightweight_model",
    "simplify_processing",
    "reduce_context_window",
)

# Privacy tier constants for cloud fallback control (SC-04).
PRIVACY_TIER_STRICT = "strict"
PRIVACY_TIER_STANDARD = "standard"
PRIVACY_TIER_NONE = "none"


@dataclass
class RecoveryEvent:
    """Record of a single recovery action taken during pipeline execution.

    PII rule: only strategy names, error codes, and provider names appear in
    messages — never contract text or user data.
    """

    strategy_name: str
    stage_name: str
    provider_name: str | None = None
    attempt: int | None = None
    outcome: RecoveryOutcome = RecoveryOutcome.RESOLVED
    message: str = ""
    timestamp: float = field(default_factory=time.time)


@dataclass
class RecoveryContext:
    """Per-pipeline-invocation state bag.

    Carries cumulative recovery state between strategy evaluations.
    Discarded after pipeline finishes (spec §5: no persistence across invocations).
    """

    provider_list: list[str] = field(default_factory=list)
    attempted_strategies: list[str] = field(default_factory=list)
    current_provider_index: int = 0
    retry_counts: dict[str, int] = field(default_factory=dict)
    memory_threshold_bytes: int = 83_886_080
    memory_budget_bytes: int = 104_857_600
    failed_stages: list[str] = field(default_factory=list)
    completed_stages: list[str] = field(default_factory=list)
    partial_data: dict[str, Any] = field(default_factory=dict)
    events: list[RecoveryEvent] = field(default_factory=list)
    degradation_action_index: int = 0
    user_privacy_tier: str = PRIVACY_TIER_STRICT

    # ponytail: spec-required v1 — no consumer yet; populated by pipeline runner
    # post-stage completion so recovery layer can independently track preserved data.
    saved_results: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict.

        Round-trip lossless via ``from_dict()``.
        """
        return {
            "provider_list": self.provider_list,
            "attempted_strategies": self.attempted_strategies,
            "current_provider_index": self.current_provider_index,
            "retry_counts": self.retry_counts,
            "failed_stages": self.failed_stages,
            "completed_stages": self.completed_stages,
            "partial_data": self.partial_data,
            "events": [dataclasses.asdict(e) for e in self.events],
            "degradation_action_index": self.degradation_action_index,
            "user_privacy_tier": self.user_privacy_tier,
            "memory_threshold_bytes": self.memory_threshold_bytes,
            "memory_budget_bytes": self.memory_budget_bytes,
            "saved_results": self.saved_results,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> RecoveryContext:
        """Deserialize from a dict produced by ``to_dict()``.

        Missing keys fall back to dataclass defaults.
        """
        events: list[RecoveryEvent] = []
        for e in d.get("events", []):
            e_copy = dict(e)
            outcome_str = e_copy.pop("outcome", "resolved")
            events.append(
                RecoveryEvent(
                    outcome=RecoveryOutcome(outcome_str),
                    **e_copy,
                )
            )
        return cls(
            provider_list=d.get("provider_list", []),
            attempted_strategies=d.get("attempted_strategies", []),
            current_provider_index=d.get("current_provider_index", 0),
            retry_counts=d.get("retry_counts", {}),
            failed_stages=d.get("failed_stages", []),
            completed_stages=d.get("completed_stages", []),
            partial_data=d.get("partial_data", {}),
            events=events,
            degradation_action_index=d.get("degradation_action_index", 0),
            user_privacy_tier=d.get("user_privacy_tier", PRIVACY_TIER_STRICT),
            memory_threshold_bytes=d.get("memory_threshold_bytes", 83_886_080),
            memory_budget_bytes=d.get("memory_budget_bytes", 104_857_600),
            saved_results=d.get("saved_results", {}),
        )


@dataclass
class RecoveryReport:
    """Final output structure attached to the pipeline's result.

    Summarises all recovery actions and their outcomes.
    """

    events: list[RecoveryEvent] = field(default_factory=list)
    final_status: str = "resolved"
    summary: str = ""
    degradation_notices: list[str] = field(default_factory=list)
    partial_results: bool = False
    actionable_error: str | None = None


class RecoveryError(Exception):
    """Raised by a recovery strategy when all attempts are exhausted.

    Carries the last RecoveryEvent so the coordinator can chain it.
    """

    def __init__(self, message: str = "", event: RecoveryEvent | None = None) -> None:
        super().__init__(message)
        self.event = event


# Known cloud provider prefixes for privacy tier checking (shared helper).
_CLOUD_PREFIXES = {"openai", "anthropic", "google", "azure", "aws", "bedrock"}


def is_cloud_provider(provider_name: str) -> bool:
    """Check if a provider name looks like a cloud provider.

    Simple prefix check — matches patterns like 'openai/gpt-4', 'anthropic/...'.
    """
    slug = provider_name.split("/", 1)[0].lower()
    return slug in _CLOUD_PREFIXES


# Dict dispatch tables for classify_error
_HTTP_STATUS_MAP: dict[int, ErrorCategory] = {
    429: ErrorCategory.transient,
    503: ErrorCategory.transient,
    400: ErrorCategory.permanent,
    401: ErrorCategory.permanent,
    403: ErrorCategory.permanent,
    404: ErrorCategory.permanent,
    500: ErrorCategory.transient,  # ponytail: transient for idempotent stages; non-idempotent stages should override via classify_error
}

_ERROR_TYPE_MAP: dict[str, ErrorCategory] = {
    "timeout": ErrorCategory.transient,
    "connection_reset": ErrorCategory.transient,
    "retryable": ErrorCategory.transient,
    "rate_limit": ErrorCategory.transient,
    "auth_error": ErrorCategory.permanent,
    "not_found": ErrorCategory.permanent,
    "provider_error": ErrorCategory.permanent,
    "bad_request": ErrorCategory.permanent,
}

# Error types that can override a permanent HTTP status back to transient
_TRANSIENT_ERROR_TYPES: frozenset[str] = frozenset(
    {
        "timeout",
        "connection_reset",
        "retryable",
        "rate_limit",
    }
)


def classify_error(
    http_status: int | None = None,
    error_type: str | None = None,
    exception_type: str | None = None,
    memory_delta_mb: float | None = None,
    memory_threshold_mb: float | None = None,
    stage_critical: bool | None = None,
) -> ErrorCategory:
    """Classify a failure into an ErrorCategory.

    Pure function — no mutable state involved (SC-01).

    Note: exception_type matching is heuristic for v1 — relies on substring
    matching against the exception class name (e.g., \"Critical\" in name →
    stage_failure_critical). A future version should use explicit exception
    type registration or a dispatch table. (ponytail: exception matching
    heuristic, v1)

    Args:
        http_status: HTTP status code from a provider response.
        error_type: Short error type string (e.g., 'timeout', 'connection_reset').
        exception_type: Fully-qualified exception class name.
        memory_delta_mb: Memory delta in MB (for resource checks).
        memory_threshold_mb: Memory threshold in MB.
        stage_critical: Whether the failing stage is critical.

    Returns:
        The matching ErrorCategory.
    """
    category: ErrorCategory | None = None

    # Resource (memory) check first — explicit via memory_delta
    if (
        memory_delta_mb is not None
        and memory_threshold_mb is not None
        and memory_delta_mb > memory_threshold_mb
    ):
        category = ErrorCategory.resource

    # Stage failure via exception type
    if category is None and exception_type is not None:
        exc_lower = exception_type.lower()
        if "critical" in exc_lower:
            category = ErrorCategory.stage_failure_critical
        elif "stage" in exc_lower:
            category = ErrorCategory.stage_failure
        elif "memorybudgeterror" in exc_lower:
            category = ErrorCategory.resource

    # Stage critical flag
    if category is None and stage_critical is not None:
        category = (
            ErrorCategory.stage_failure_critical if stage_critical else ErrorCategory.stage_failure
        )

    # Provider errors via HTTP status dict lookup
    if category is None and http_status is not None:
        category = _HTTP_STATUS_MAP.get(http_status)

    # Transient error type can override permanent HTTP status
    if (
        category == ErrorCategory.permanent
        and error_type is not None
        and error_type.lower() in _TRANSIENT_ERROR_TYPES
    ):
        category = ErrorCategory.transient

    # Error-type-based classification (no HTTP status or unmatched status)
    if category is None and error_type is not None:
        category = _ERROR_TYPE_MAP.get(error_type.lower())

    return category or ErrorCategory.unknown


def _provider_suggestions(provider_name: str, is_cloud: bool | None) -> list[str]:
    """Suggestions for provider-related errors (transient/permanent)."""
    if provider_name:
        if is_cloud:
            return [
                "Check your internet connectivity.",
                "Configure a different provider: `openreview gateway setup`",
            ]
        return [
            "Start your local provider: e.g., `ollama serve` or `openreview gateway start`",
            "Configure a cloud provider: `openreview gateway setup`",
        ]
    return [
        "Run `openreview gateway setup` to configure a provider.",
        "Check that your provider service is running.",
    ]


_SUGGESTION_BUILDERS: dict[ErrorCategory, list[str]] = {
    ErrorCategory.resource: [
        "Reduce document size or split into smaller documents.",
        "Increase the memory budget in config (recovery.memory_threshold_pct).",
        "Close other memory-intensive applications.",
    ],
    ErrorCategory.stage_failure: [
        "Check the document format — ensure it is valid PDF or DOCX.",
        "Run with `--verbose` for detailed error output.",
        "Re-run the pipeline — the failure may be transient.",
    ],
    ErrorCategory.stage_failure_critical: [
        "Check the input document — critical parsing failures often "
        "indicate a corrupt or unsupported format.",
        "Run `openreview precheck review` on a simpler document first.",
        "Report this issue with the document attached (stripped of PII).",
    ],
    ErrorCategory.unknown: [
        "Run with `--verbose` or `--debug` for detailed error output.",
        "Check the openreview logs for more context.",
        "Report this issue with the error details above.",
    ],
}


def suggestion_for(
    category: ErrorCategory,
    provider_name: str,
    privacy_tier: str,
) -> list[str]:
    """Generate actionable suggestions based on error category and context.

    Returns at least 2 suggestions per SC-07.
    """
    is_cloud = is_cloud_provider(provider_name) if provider_name else None

    if category in (ErrorCategory.transient, ErrorCategory.permanent):
        suggestions = _provider_suggestions(provider_name, is_cloud)
    else:
        suggestions = list(
            _SUGGESTION_BUILDERS.get(category, _SUGGESTION_BUILDERS[ErrorCategory.unknown])
        )

    # Privacy tier warning
    if privacy_tier == PRIVACY_TIER_STRICT and is_cloud:
        suggestions.append(
            "Privacy mode is 'strict' — cloud fallback is blocked. "
            "Set tier to 'standard' to allow cloud fallback."
        )

    # Always ensure at least 2 suggestions per SC-07
    if len(suggestions) == 1:
        suggestions.append("Re-run the pipeline — the failure may be transient.")

    return suggestions
