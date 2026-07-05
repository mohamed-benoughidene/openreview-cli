"""Error recovery framework — intercepts pipeline and gateway failures,
applies automated recovery strategies, and reports outcomes."""

from openreview_cli.config import RecoveryConfig
from openreview_cli.recovery.coordinator import RecoveryCoordinator, RecoverySignal
from openreview_cli.recovery.models import (
    RecoveryContext,
    RecoveryError,
    RecoveryOutcome,
    RecoveryReport,
    classify_error,
    suggestion_for,
)

__all__ = [
    "RecoveryConfig",
    "RecoveryContext",
    "RecoveryCoordinator",
    "RecoveryError",
    "RecoveryOutcome",
    "RecoveryReport",
    "RecoverySignal",
    "classify_error",
    "suggestion_for",
]
