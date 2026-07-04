import asyncio
import tracemalloc
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

from openreview_cli.pipeline.base import Stage

PEAK_MEMORY_FLOOR_BYTES = 110 * 1024 * 1024
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


# ── Shared pipeline mock stages ─────────────────────────────────────────────


class MockStage(Stage):
    """Stage that returns a configurable dict and counts calls."""

    def __init__(
        self,
        name: str,
        return_value: dict[str, Any] | None = None,
        sleep: float = 0,
        critical: bool = False,
    ) -> None:
        self.name = name
        self.critical = critical
        self._return = return_value if return_value is not None else {name: f"{name}_out"}
        self._sleep = sleep
        self.call_count = 0

    async def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        self.call_count += 1
        if self._sleep:
            await asyncio.sleep(self._sleep)
        return dict(self._return)


class TrackingStage(Stage):
    """Stage that records the context it received."""

    def __init__(self, name: str, return_value: dict[str, Any] | None = None) -> None:
        self.name = name
        self._return = return_value or {name: f"{name}_out"}
        self.received_ctx: dict[str, Any] | None = None

    async def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        self.received_ctx = dict(ctx)
        return dict(self._return)


class ErrorStage(Stage):
    """Stage that raises a configurable error on run."""

    def __init__(
        self,
        name: str,
        critical: bool = False,
        error_cls: type[Exception] | None = None,
    ) -> None:
        self.name = name
        self.critical = critical
        from openreview_cli.pipeline.errors import StageError

        self._error_cls = error_cls or StageError
        self.call_count = 0

    async def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        self.call_count += 1
        raise self._error_cls(f"{self.name} failed")


class SlowStage(Stage):
    """Stage that sleeps to simulate long work (for cancellation tests)."""

    def __init__(self, name: str, sleep: float = 10) -> None:
        self.name = name
        self._sleep = sleep
        self.started = asyncio.Event()
        self.completed = False

    async def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        self.started.set()
        await asyncio.sleep(self._sleep)
        self.completed = True
        return {self.name: "done"}


@pytest.fixture
def memory_tracker() -> Generator[None, None, None]:
    """Enforce the constitutional peak-memory floor of 110 MB."""
    tracemalloc.start()
    try:
        yield
    finally:
        _current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        assert peak < PEAK_MEMORY_FLOOR_BYTES, (
            f"Peak memory {peak / 1024 / 1024:.1f} MB exceeds "
            f"{PEAK_MEMORY_FLOOR_BYTES / 1024 / 1024:.0f} MB floor"
        )


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the path to the test fixtures directory."""
    return FIXTURES_DIR
