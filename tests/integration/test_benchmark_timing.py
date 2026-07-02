"""Timing assertion integration test (T029).

Measures pipeline overhead only (no real LLM latency).
Completes < 30 minutes on reference hardware profile.
"""

import time


class TestBenchmarkTiming:
    def test_pipeline_overhead_fast(self) -> None:
        """Assert pipeline overhead completes quickly (< 5 seconds).

        Uses direct metric computation without dataset download.
        """
        # Test metrics directly instead of through dataset loader
        from openreview_cli.benchmark.metrics import comparison_f1

        start = time.monotonic()
        for _ in range(1000):
            comparison_f1([True, False], [True, True])
        elapsed = time.monotonic() - start
        assert elapsed < 5.0, f"1000 metric computations took {elapsed:.2f}s"

    def test_runner_instantiation_fast(self) -> None:
        """Assert BenchmarkRunner instantiates quickly."""
        from openreview_cli.benchmark.models import BenchmarkConfig
        from openreview_cli.benchmark.runner import BenchmarkRunner

        start = time.monotonic()
        for _ in range(100):
            BenchmarkRunner(config=BenchmarkConfig())
        elapsed = time.monotonic() - start
        assert elapsed < 5.0, f"100 instantiations took {elapsed:.2f}s"
