"""Integration tests for memory budget during bilateral comparison (T068-T069).

Verifies that peak memory during the comparison pipeline stays under
the hardware budget (<100 MB ex-NLP-model for full pipeline, <50 MB for
alignment-only mode).
"""

from __future__ import annotations

import pytest


@pytest.mark.memory
class TestBilateralMemoryFullPipeline:
    """Peak memory during full comparison pipeline must be <100 MB ex-model."""

    def test_full_pipeline_under_100mb(self) -> None:
        """Full comparison pipeline peak memory <100 MB (ex-NLP-model)."""
        # ponytail: placeholder — requires tracemalloc setup and mock documents
        # Implement when benchmark fixtures are available
        pass


@pytest.mark.memory
class TestBilateralMemoryAlignOnly:
    """Peak memory during alignment-only mode must be <50 MB."""

    def test_align_only_under_50mb(self) -> None:
        """Align-only mode peak memory <50 MB (no model inference)."""
        # ponytail: placeholder — requires tracemalloc setup
        # Implement when benchmark fixtures are available
        pass
