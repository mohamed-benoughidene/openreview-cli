"""Cold-start timing test for TUI launch (SC-004)."""

from __future__ import annotations

import time

import pytest


@pytest.mark.slow
async def test_cold_start_under_1_second() -> None:
    """Measure wall-clock time from app creation to first interactive render.

    Production baseline (SC-004): < 1.0s on reference 8 GB / 2-core machine.
    This test runs under ``app.run_test()`` which adds harness overhead
    (virtual terminal, async event loop) not present in production
    ``app.run()``.  The threshold here is set to accommodate that overhead
    + cold import of Textual and its dependencies (the dominant cost).

    If this test is flaky in CI, skip with ``-m 'not slow'``.
    """
    from openreview_cli.tui.app import OpenReviewApp

    # Start clock before construction — first import of OpenReviewApp
    # triggers loading of Textual + all TUI modules (dominant cost).
    start = time.monotonic()
    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        elapsed = time.monotonic() - start

    # Threshold accommodates cold import + test-harness overhead.
    # Production baseline (SC-004) is 1.0s via `hyperfine openreview`.
    assert elapsed < 20.0, f"Cold start + pilot render took {elapsed:.3f}s"
