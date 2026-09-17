"""Unit test for ``progress_callback`` forwarding in ``run_review`` (P1/T5)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from openreview_cli.pipeline.progress import ProgressEvent


def test_run_review_forwards_progress_callback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``run_review`` must pass its ``progress_callback`` to the doc pipeline."""
    from openreview_cli.review import runner

    doc = tmp_path / "doc.pdf"
    doc.write_bytes(b"%PDF-1.4")

    seen: dict[str, Any] = {}

    def fake_pipeline(**kwargs: Any) -> None:
        # Returns None implicitly: no report produced, so run_review skips it.
        seen.update(kwargs)

    def fake_playbook() -> object:
        return object()

    monkeypatch.setattr(runner, "load_bundled", fake_playbook)
    monkeypatch.setattr(runner, "_run_review_doc_pipeline", fake_pipeline)

    received: list[ProgressEvent] = []

    def sentinel(event: ProgressEvent) -> None:
        received.append(event)

    runner.run_review([str(doc)], progress_callback=sentinel)

    assert seen.get("progress_callback") is sentinel
    assert received == []
