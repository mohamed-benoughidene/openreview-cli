"""Unit tests for pipeline base module: Stage ABC, StageResult."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from openreview_cli.pipeline.base import Stage, StageResult


class ConcreteStage(Stage):
    """Minimal concrete Stage for testing."""

    name = "test_stage"

    async def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        return {"result": "ok"}


def test_stage_abc_cannot_instantiate() -> None:
    """Stage ABC cannot be instantiated (has abstract method)."""
    with pytest.raises(TypeError):
        Stage()  # type: ignore[abstract]


def test_concrete_stage_instantiation() -> None:
    """Concrete Stage subclass can be instantiated."""
    stage = ConcreteStage()
    assert stage.name == "test_stage"
    assert stage.critical is False


def test_stage_critical_flag() -> None:
    """Stage critical flag can be set via class attribute."""

    class CriticalStage(Stage):
        name = "critical"
        critical = True

        async def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
            return {}

    stage = CriticalStage()
    assert stage.critical is True


def test_stage_result_required_fields() -> None:
    """StageResult can be created with only required fields."""
    sr = StageResult(stage_name="parse", duration_s=1.5)
    assert sr.stage_name == "parse"
    assert sr.duration_s == 1.5
    assert sr.error is None
    assert sr.output_keys == []
    assert sr.skipped is False
    assert sr.memory_mb is None


def test_stage_result_all_fields() -> None:
    """StageResult with all fields set."""
    sr = StageResult(
        stage_name="parse",
        duration_s=2.0,
        error="something went wrong",
        output_keys=["document", "clauses"],
        skipped=False,
        memory_mb=12.5,
    )
    assert sr.stage_name == "parse"
    assert sr.duration_s == 2.0
    assert sr.error == "something went wrong"
    assert sr.output_keys == ["document", "clauses"]
    assert sr.memory_mb == 12.5


def test_stage_run_abstract() -> None:
    """Stage subclasses must implement run()."""

    class NoRunStage(Stage):
        name = "no_run"

    with pytest.raises(TypeError):
        NoRunStage()  # type: ignore[abstract]


def test_concrete_stage_run() -> None:
    """Concrete stage run() returns expected dict."""
    stage = ConcreteStage()
    result = asyncio.run(stage.run({"input": "data"}))
    assert result == {"result": "ok"}
