"""Unit tests for pipeline progress module — minimal coverage."""

from __future__ import annotations

from openreview_cli.pipeline.progress import (
    ProgressCallback,
    ProgressEvent,
)


def test_progress_event_required_fields() -> None:
    """ProgressEvent can be created with required fields."""
    event = ProgressEvent(
        stage_index=0,
        total_stages=5,
        stage_name="parse",
        status="running",
    )
    assert event.stage_index == 0
    assert event.status == "running"
    assert event.message is None
    assert event.duration_s is None


def test_progress_event_all_fields() -> None:
    """ProgressEvent with all fields set."""
    event = ProgressEvent(
        stage_index=2,
        total_stages=5,
        stage_name="chunk",
        status="completed",
        message="Chunked 42 clauses",
        duration_s=1.23,
    )
    assert event.duration_s == 1.23
    assert event.message == "Chunked 42 clauses"


def test_progress_callback_type() -> None:
    """ProgressCallback type annotation is callable."""
    events: list[ProgressEvent] = []

    def callback(event: ProgressEvent) -> None:
        events.append(event)

    cb: ProgressCallback = callback
    cb(ProgressEvent(stage_index=0, total_stages=1, stage_name="t", status="running"))
    assert len(events) == 1
    assert events[0].stage_name == "t"
