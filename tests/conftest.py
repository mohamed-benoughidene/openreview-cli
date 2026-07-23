import asyncio
import functools
import logging
import threading
import tracemalloc
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

from openreview_cli.pii.engine import PiiEngine
from openreview_cli.pipeline.base import Stage


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if item.get_closest_marker("network"):
            item.add_marker(pytest.mark.enable_socket)


# Silence transformers advisory/info warnings during pytest runs.
# Avoids "I/O operation on closed file" from warnings emitted while
# pytest has already closed the capture output.
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("transformers.modeling_utils").setLevel(logging.ERROR)
logging.getLogger("transformers.tokenization_utils_base").setLevel(logging.ERROR)
logging.getLogger("transformers.configuration_utils").setLevel(logging.ERROR)
logging.getLogger("transformers.integrations.tensor_parallel").setLevel(logging.ERROR)
logging.getLogger("transformers.integrations.tensor_parallel").setLevel(logging.ERROR)

PEAK_MEMORY_FLOOR_BYTES = 110 * 1024 * 1024
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


# ── Shared PII engine (ponytail: one spaCy model load per session, not per test) ──

_shared_pii_engine: dict[str, "PiiEngine"] = {}
_shared_pii_engine_lock = threading.Lock()


def _get_shared_pii_engine() -> "PiiEngine":
    """Return one warmed PiiEngine for the whole session.

    Loads spaCy (en_core_web_lg) once; every PII test reuses the instance
    instead of reloading the ~600 MB model on each test.
    """
    if "engine" not in _shared_pii_engine:
        with _shared_pii_engine_lock:
            if "engine" not in _shared_pii_engine:
                engine = PiiEngine(threshold=0.7)
                engine._ensure_analyzer()
                _shared_pii_engine["engine"] = engine
    return _shared_pii_engine["engine"]


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


@pytest.fixture(scope="session")
def pii_engine() -> "PiiEngine":
    """Session-scoped shared PiiEngine for tests that build their own engine."""
    return _get_shared_pii_engine()


@pytest.fixture(autouse=True)
def _inject_shared_pii_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    """Feed the shared PiiEngine into strip_pii/strip_pii_clauses when none passed.

    Non-PII tests never load the model; it loads lazily on the first real PII
    call and is reused for the rest of the session.
    """
    from openreview_cli.pii.engine import strip_pii, strip_pii_clauses

    real_strip_pii = strip_pii
    real_strip_clauses = strip_pii_clauses

    @functools.wraps(real_strip_pii)
    def _patched_strip_pii(*args: Any, engine: "PiiEngine | None" = None, **kwargs: Any) -> Any:
        return real_strip_pii(*args, engine=engine or _get_shared_pii_engine(), **kwargs)

    @functools.wraps(real_strip_clauses)
    def _patched_strip_clauses(*args: Any, engine: "PiiEngine | None" = None, **kwargs: Any) -> Any:
        return real_strip_clauses(*args, engine=engine or _get_shared_pii_engine(), **kwargs)

    monkeypatch.setattr("openreview_cli.pii.engine.strip_pii", _patched_strip_pii)
    monkeypatch.setattr("openreview_cli.pii.engine.strip_pii_clauses", _patched_strip_clauses)
