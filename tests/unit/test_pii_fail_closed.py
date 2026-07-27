"""PII fail-closed by default; --allow-partial-pii continues with warning."""

from __future__ import annotations

from typing import Any

import pytest
from _pytest.monkeypatch import MonkeyPatch

from openreview_cli.parsing.models import Clause
from openreview_cli.pii.engine import PiiEngine
from openreview_cli.pii.models import PartialProcessingError


def _clause(n: int) -> Clause:
    return Clause(
        id=f"c{n}",
        title=f"Clause {n}",
        text=f"Text of clause {n}, contact john@example.com.",
        level=1,
        parent_id=None,
        source_page=n,
        source_paragraph=None,
        source_span=None,
    )


def _flaky(engine: PiiEngine, monkeypatch: MonkeyPatch) -> None:
    real_detect = engine.detect_on_page

    def flaky_detect(
        text: str,
        threshold: float | None = None,
        is_non_english: bool = False,
        clause_heading: str | None = None,
    ) -> list[Any]:
        if clause_heading == "Clause 2":
            raise RuntimeError("presidio boom")
        return real_detect(
            text,
            threshold=threshold,
            is_non_english=is_non_english,
            clause_heading=clause_heading,
        )

    monkeypatch.setattr(engine, "detect_on_page", flaky_detect)


def test_default_raises_on_failed_page(pii_engine: PiiEngine, monkeypatch: MonkeyPatch) -> None:
    _flaky(pii_engine, monkeypatch)
    with pytest.raises(PartialProcessingError) as exc_info:
        pii_engine.detect_all_pages([_clause(1), _clause(2), _clause(3)])
    assert exc_info.value.failed_pages == [2]
    assert 2 in exc_info.value.error_messages


def test_allow_partial_continues_with_failed_pages_reported(
    pii_engine: PiiEngine,
    monkeypatch: MonkeyPatch,
) -> None:
    _flaky(pii_engine, monkeypatch)
    entities, warnings, failed_pages, errors = pii_engine.detect_all_pages(
        [_clause(1), _clause(2), _clause(3)], allow_partial=True
    )
    assert failed_pages == [2]
    assert 2 in errors
