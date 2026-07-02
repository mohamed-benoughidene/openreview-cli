"""tracemalloc-based per-item memory profiler.

Measures peak memory during benchmark evaluation,
excluding NLP model memory per constitutional exemption.
"""

import gc
import tracemalloc
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


class MemoryProfiler:
    """Per-item memory profiler using tracemalloc."""

    def __init__(self, nlpmodel_exempt: bool = True) -> None:
        self.nlpmodel_exempt = nlpmodel_exempt
        self._snapshot: tracemalloc.Snapshot | None = None

    def start(self) -> None:
        gc.collect()
        tracemalloc.clear_traces()
        tracemalloc.start()
        self._snapshot = None

    def stop(self) -> float:
        _current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        return peak / (1024 * 1024)  # Return MB

    def measure(self, fn: Callable[..., T], *args: object, **kwargs: object) -> tuple[T, float]:
        """Run fn and return (result, peak_memory_mb).

        Excludes NLP model memory if nlpmodel_exempt is True
        by measuring only the delta during execution.
        """
        self.start()
        try:
            result = fn(*args, **kwargs)
        finally:
            peak_mb = self.stop()
        return result, peak_mb
