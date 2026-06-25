"""Memory budget validation skeleton for PII stripping (SC-005)."""

import pytest


@pytest.mark.memory
class TestPiiMemory:
    """Memory-budget placeholder (SC-005)."""

    def test_memory_skeleton(self) -> None:
        """Placeholder for SC-005 memory validation.

        Will process a 50-page seeded document with tracemalloc
        and assert peak < 100 MB (excluding NLP model baseline).
        """
