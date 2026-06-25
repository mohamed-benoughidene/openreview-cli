import tracemalloc
from collections.abc import Generator
from pathlib import Path

import pytest

PEAK_MEMORY_FLOOR_BYTES = 110 * 1024 * 1024
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


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
