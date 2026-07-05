"""Progress event types for pipeline execution."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

# ponytail: spec-required v1 — no consumer yet; used by recovery coordinator progress events
StageStatus = Literal["running", "completed", "failed", "skipped", "recovering", "degraded"]


@dataclass
class ProgressEvent:
    """Event emitted during pipeline execution for user-facing progress.

    Attributes:
        stage_index: 0-based index of the current stage.
        total_stages: Total number of stages in the pipeline.
        stage_name: Name of the current stage.
        status: Current stage status.
        message: Optional human-readable detail.
        duration_s: Stage wall-clock duration (set on completed/failed).
    """

    stage_index: int
    total_stages: int
    stage_name: str
    status: StageStatus
    message: str | None = None
    duration_s: float | None = field(default=None)


ProgressCallback = Callable[[ProgressEvent], None]
"""Signature for progress callback functions."""
