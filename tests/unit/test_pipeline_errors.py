"""Unit tests for pipeline error hierarchy — parametrized."""

from __future__ import annotations

import pytest

from openreview_cli.pipeline.errors import (
    CriticalStageError,
    MemoryBudgetError,
    PipelineError,
    StageError,
)

ERROR_CLASSES = [
    (PipelineError, PipelineError, True),
    (StageError, PipelineError, True),
    (CriticalStageError, StageError, True),
    (CriticalStageError, PipelineError, True),
    (MemoryBudgetError, PipelineError, True),
]

INSTANCES = [
    (PipelineError("base"), "base"),
    (StageError("stage"), "stage"),
    (CriticalStageError("critical"), "critical"),
    (MemoryBudgetError("memory"), "memory"),
]


@pytest.mark.parametrize("err_cls,parent,should_match", ERROR_CLASSES)
def test_hierarchy(err_cls: type, parent: type, should_match: bool) -> None:
    err = err_cls("test")
    if should_match:
        assert isinstance(err, parent)


@pytest.mark.parametrize("err,expected_msg", INSTANCES)
def test_str(err: Exception, expected_msg: str) -> None:
    assert str(err) == expected_msg


def test_critical_carries_report() -> None:
    err = CriticalStageError("fail", pipeline_report="partial")
    assert err.pipeline_report == "partial"


def test_critical_default_report() -> None:
    err = CriticalStageError("fail")
    assert err.pipeline_report is None
