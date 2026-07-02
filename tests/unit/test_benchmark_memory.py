"""Unit tests for tracemalloc-based memory profiler (T006)."""

from openreview_cli.benchmark.memory import MemoryProfiler


class TestMemoryProfiler:
    def test_measure_simple(self) -> None:
        profiler = MemoryProfiler()

        def small_fn() -> int:
            return 42

        result, peak_mb = profiler.measure(small_fn)
        assert result == 42
        assert peak_mb >= 0.0

    def test_measure_larger_allocation(self) -> None:
        profiler = MemoryProfiler()

        def alloc_fn() -> list[int]:
            return [1] * 100000

        result, peak_mb = profiler.measure(alloc_fn)
        assert len(result) == 100000
        assert peak_mb >= 0.0

    def test_start_stop(self) -> None:
        profiler = MemoryProfiler()
        profiler.start()
        _ = [1] * 50000
        peak_mb = profiler.stop()
        assert peak_mb >= 0.0

    def test_nlpmodel_exempt_default(self) -> None:
        profiler = MemoryProfiler()
        assert profiler.nlpmodel_exempt is True
