"""Unit tests for PII stripping in the bilateral comparison pipeline.

RED tests for the compare-PII fix: `precheck compare` previously sent raw
clause text to the LLM (`no_pii` was only a metadata label). After the fix,
`_process_document` strips PII before extraction/QA unless `no_pii` is set,
and honors `allow_partial_pii` / fail-closed `PartialProcessingError`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from openreview_cli.parsing.models import Clause
from openreview_cli.review.models import (
    Category,
    Playbook,
    PlaybookMetadata,
    Position,
    PositionDef,
)


@pytest.fixture
def sample_playbook() -> Playbook:
    fav = PositionDef(description="Short term", exemplars=["3 years"])
    neu = PositionDef(description="Standard term", exemplars=["5 years"])
    unfav = PositionDef(description="Indefinite", exemplars=["perpetuity"])
    cat = Category(
        id="confidentiality-term",
        name="Confidentiality Term",
        description="How long confidentiality survives",
        preferred=fav,
        acceptable=neu,
        walkaway=unfav,
        default_position=Position.ACCEPTABLE,
    )
    meta = PlaybookMetadata(version="1.0.0", description="Test", author="test")
    return Playbook(id="test-nda", mode="precheck", categories=[cat], metadata=meta)


def make_clause(clause_id: str = "c1", text: str = "Confidential info for 3 years") -> Clause:
    return Clause(
        id=clause_id,
        title="Confidentiality",
        text=text,
        level=1,
        parent_id=None,
        source_page=1,
        source_paragraph=None,
        source_span=(0, len(text)),
    )


def _now() -> datetime:
    return datetime.now(UTC)


class TestProcessDocumentStrip:
    """_process_document strips PII before extraction unless no_pii."""

    def test_strips_pii_when_not_no_pii(
        self, monkeypatch: pytest.MonkeyPatch, sample_playbook: Playbook
    ) -> None:
        """strip_pii_clauses is called when no_pii=False (inference path)."""
        from openreview_cli.bilateral import _process_document

        clauses = [make_clause()]
        stripped = [make_clause(text="Confidential info for [TERM_1] years")]

        monkeypatch.setattr(
            "openreview_cli.bilateral._parse_document", lambda p: (object(), clauses)
        )
        calls: list[dict[str, Any]] = []

        def fake_strip(clauses_in, doc_in, **kwargs):  # type: ignore[no-untyped-def]
            calls.append(kwargs)
            return stripped, object()

        monkeypatch.setattr("openreview_cli.pii.strip_pii_clauses", fake_strip)

        # Extraction/QA would run on the STRIPPED text — assert the text sent is stripped.
        captured: list[str] = []

        def fake_extract(*args, **kwargs):  # type: ignore[no-untyped-def]
            captured.append(kwargs.get("clause_text", ""))
            from openreview_cli.review.models import ClauseAssessment, QAVerdict

            return ClauseAssessment(
                clause_id="c1",
                clause_text=kwargs.get("clause_text", ""),
                playbook_category="confidentiality-term",
                position=Position.PREFERRED,
                confidence=0.9,
                citation="x",
                qa_verdict=QAVerdict.agree,
                extraction_model="test",
                qa_model="test",
            )

        # bilateral/__init__.py imports extract_clause at module load; patch the
        # reference in the bilateral namespace.
        monkeypatch.setattr("openreview_cli.bilateral.extract_clause", fake_extract)

        meta, out_clauses, assessments = _process_document(
            "doc_a.pdf", sample_playbook, "extraction", "qa"
        )

        assert len(calls) == 1, "strip_pii_clauses should be called"
        assert calls[0]["allow_partial"] is False
        assert meta.pii_stripped is True
        assert out_clauses == stripped
        assert captured == ["Confidential info for [TERM_1] years"]

    def test_no_strip_when_no_pii(
        self, monkeypatch: pytest.MonkeyPatch, sample_playbook: Playbook
    ) -> None:
        """strip_pii_clauses NOT called when no_pii=True."""
        from openreview_cli.bilateral import _process_document

        clauses = [make_clause()]

        monkeypatch.setattr(
            "openreview_cli.bilateral._parse_document", lambda p: (object(), clauses)
        )
        called: list[bool] = [False]

        def fake_strip(*args, **kwargs):  # type: ignore[no-untyped-def]
            called[0] = True
            return clauses, object()

        monkeypatch.setattr("openreview_cli.pii.strip_pii_clauses", fake_strip)

        meta, out_clauses, _ = _process_document(
            "doc_a.pdf", sample_playbook, "extraction", "qa", no_pii=True
        )

        assert not called[0]
        assert meta.pii_stripped is False
        assert out_clauses == clauses

    def test_allow_partial_passed_through(
        self, monkeypatch: pytest.MonkeyPatch, sample_playbook: Playbook
    ) -> None:
        """allow_partial_pii is forwarded to strip_pii_clauses."""
        from openreview_cli.bilateral import _process_document

        clauses = [make_clause()]
        monkeypatch.setattr(
            "openreview_cli.bilateral._parse_document", lambda p: (object(), clauses)
        )
        calls: list[dict[str, Any]] = []

        def fake_strip(clauses_in, doc_in, **kwargs):  # type: ignore[no-untyped-def]
            calls.append(kwargs)
            return clauses, object()

        monkeypatch.setattr("openreview_cli.pii.strip_pii_clauses", fake_strip)

        _process_document("doc_a.pdf", sample_playbook, "extraction", "qa", allow_partial_pii=True)

        assert calls[0]["allow_partial"] is True

    def test_align_only_no_strip(
        self, monkeypatch: pytest.MonkeyPatch, sample_playbook: Playbook
    ) -> None:
        """align_only performs no strip and reports pii_stripped=False."""
        from openreview_cli.bilateral import _process_document

        clauses = [make_clause()]
        monkeypatch.setattr(
            "openreview_cli.bilateral._parse_document", lambda p: (object(), clauses)
        )
        called: list[bool] = [False]

        def fake_strip(*args, **kwargs):  # type: ignore[no-untyped-def]
            called[0] = True
            return clauses, object()

        monkeypatch.setattr("openreview_cli.pii.strip_pii_clauses", fake_strip)

        meta, out_clauses, _ = _process_document(
            "doc_a.pdf", sample_playbook, "extraction", "qa", align_only=True
        )

        assert not called[0]
        assert meta.pii_stripped is False
        assert out_clauses == clauses


class TestPartialProcessingFailClosed:
    """PartialProcessingError aborts before any LLM call."""

    def test_partial_error_propagates(
        self, monkeypatch: pytest.MonkeyPatch, sample_playbook: Playbook
    ) -> None:
        """PartialProcessingError from strip_pii_clauses is NOT swallowed."""
        from openreview_cli.bilateral import _process_document
        from openreview_cli.pii.models import PartialProcessingError

        clauses = [make_clause()]
        monkeypatch.setattr(
            "openreview_cli.bilateral._parse_document", lambda p: (object(), clauses)
        )

        def fake_strip(*args, **kwargs):  # type: ignore[no-untyped-def]
            raise PartialProcessingError(
                failed_pages=[2],
                successful_pages=[1],
                error_messages={2: "boom"},
            )

        monkeypatch.setattr("openreview_cli.pii.strip_pii_clauses", fake_strip)

        with pytest.raises(PartialProcessingError):
            _process_document("doc_a.pdf", sample_playbook, "extraction", "qa")


class TestRunComparisonStripWiring:
    """run_comparison threads allow_partial_pii into both documents."""

    def test_allow_partial_pii_threaded(
        self, monkeypatch: pytest.MonkeyPatch, sample_playbook: Playbook
    ) -> None:
        """allow_partial_pii reaches strip_pii_clauses for both docs."""
        from openreview_cli.bilateral import run_comparison

        clauses = [make_clause()]
        monkeypatch.setattr(
            "openreview_cli.bilateral._parse_document", lambda p: (object(), clauses)
        )
        calls: list[dict[str, Any]] = []

        def fake_strip(clauses_in, doc_in, **kwargs):  # type: ignore[no-untyped-def]
            calls.append(kwargs)
            return clauses, object()

        monkeypatch.setattr("openreview_cli.pii.strip_pii_clauses", fake_strip)
        # Skip LLM calls entirely (empty clauses → no pairs → no chat).
        monkeypatch.setattr("openreview_cli.bilateral._parse_document", lambda p: (object(), []))

        run_comparison(
            doc_a_path="a.pdf",
            doc_b_path="b.pdf",
            playbook=sample_playbook,
            extraction_model="extraction",
            allow_partial_pii=True,
        )

        assert len(calls) == 2, "both docs should be stripped"
        assert all(c["allow_partial"] is True for c in calls)
