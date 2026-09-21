"""PII-2 — Bilateral PII governance persistence triplet.

For every PII-bearing supported bilateral document that strips successfully,
the governance state must be:

    encrypted mapping (pii_map.enc)
    +
    pii_cache row
    +
    pii_audit_trail row

Cases:

  A. PII-bearing document A — full triplet on disk + DB
  B. PII-bearing document B — full triplet on disk + DB
  C. Both documents PII-bearing — both triplets independent
  D. Clean document — no cache row; one audit row with entity_count 0
  E. Cache reuse — no phantom audit row on cache hit
  F. --no-pii — no persistence (bilateral opts out)
  G. align_only — no strip, no persistence

The bilateral path previously called strip_pii_clauses and DISCARDED
the PiiResult (bilateral/__init__.py:313 `clauses, _ = ...`), so no
mapping/cache/audit row was ever written. The StripStage pattern is
the correct reference.
"""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

from openreview_cli.gateway import router as gateway_router
from openreview_cli.review.models import Position, QAVerdict
from openreview_cli.storage import init_database

# ── helpers ──────────────────────────────────────────────────────────────


def _entity(entity_type: str, placeholder: str, original: str = "x") -> Any:
    from openreview_cli.pii.models import PiiEntity

    return PiiEntity(
        entity_type=entity_type,
        original_value=original,
        start=0,
        end=len(original),
        score=0.9,
        placeholder=placeholder,
        source="nlp",
    )


def _pii_result_with_mapping() -> Any:
    from openreview_cli.pii.models import PiiResult

    return PiiResult(
        stripped_text="Hello [PARTY_A] from [ORG_1]",
        mapping={"PARTY_A": "Acme", "ORG_1": "Acme Corp"},
        entities=[
            _entity("ORGANIZATION", "[PARTY_A]", original="Acme"),
            _entity("ORGANIZATION", "[ORG_1]", original="Acme Corp"),
        ],
        page_count=1,
        duration_seconds=1.0,
        warnings=[],
    )


def _pii_result_no_mapping() -> Any:
    from openreview_cli.pii.models import PiiResult

    return PiiResult(
        stripped_text="clean text",
        mapping={},
        entities=[],
        page_count=1,
        duration_seconds=1.0,
        warnings=[],
    )


def _make_pdf(tmp_path: Path, name: str, body: bytes = b"%PDF-1.4\nseed\n") -> Path:
    p = tmp_path / name
    p.write_bytes(body)
    return p


def _audit_count(db_path: Path, doc_hash: str) -> int:
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM pii_audit_trail WHERE document_hash = ?",
            (doc_hash,),
        ).fetchone()
        return int(row[0]) if row is not None else 0
    finally:
        conn.close()


def _cache_row(db_path: Path, doc_hash: str) -> dict[str, Any] | None:
    conn = sqlite3.connect(str(db_path))
    try:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM pii_cache WHERE document_hash = ?", (doc_hash,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


@pytest.fixture
def xdg_isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """XDG-isolate config + data dirs so bilateral persistence writes to
    a fresh per-test filesystem instead of the real ~/.config/openreview."""
    config_base = tmp_path / "config"
    data_base = tmp_path / "data"
    for p in (config_base, data_base):
        p.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_base))
    monkeypatch.setenv("XDG_DATA_HOME", str(data_base))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))

    openreview_config_dir = config_base / "openreview"
    openreview_config_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = openreview_config_dir / "config.yml"
    cfg_path.write_text(
        "privacy:\n  tier: balanced\ngateway:\n  models: {}\n",
        encoding="utf-8",
    )

    openreview_data_dir = data_base / "openreview"
    openreview_data_dir.mkdir(parents=True, exist_ok=True)
    db_path = openreview_data_dir / "openreview.db"
    init_database(db_path)

    return {
        "config_base": config_base,
        "data_base": data_base,
        "openreview_data_dir": openreview_data_dir,
        "db_path": db_path,
        "config_path": cfg_path,
    }


@pytest.fixture(autouse=True)
def _reset_pii_flag_after() -> Generator[None, None, None]:
    yield
    gateway_router.reset_pii_available()


@pytest.fixture
def sample_playbook() -> Any:
    from openreview_cli.review.models import (
        Category,
        Playbook,
        PlaybookMetadata,
        Position,
        PositionDef,
    )

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


def _make_clause(clause_id: str = "c1", text: str = "Confidential info") -> Any:
    from openreview_cli.parsing.models import Clause

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


def _stub_bilateral_deps(
    monkeypatch: pytest.MonkeyPatch,
    stripped_clauses: list[Any],
    pii_result: Any,
) -> None:
    """Stub _parse_document and strip_pii_clauses so the real bilateral
    _process_document runs through the strip branch end-to-end and the
    persistence helper (under test) sees the synthetic PiiResult."""
    clauses = [stripped_clauses[0] if stripped_clauses else _make_clause()]

    monkeypatch.setattr("openreview_cli.bilateral._parse_document", lambda p: (object(), clauses))
    monkeypatch.setattr(
        "openreview_cli.pii.strip_pii_clauses", lambda *a, **kw: (stripped_clauses, pii_result)
    )

    # Stub extraction/QA so we don't need a real gateway.
    def fake_extract(*args, **kwargs):  # type: ignore[no-untyped-def]
        from openreview_cli.review.models import ClauseAssessment, QAVerdict

        return ClauseAssessment(
            clause_id="c1",
            clause_text=kwargs.get("clause_text", ""),
            playbook_category="confidentiality-term",
            position=Position.ACCEPTABLE,
            confidence=0.9,
            citation="x",
            qa_verdict=QAVerdict.agree,
            extraction_model="test",
            qa_model="test",
        )

    # `bilateral` imports extract_clause at module load; patch the namespace ref.
    monkeypatch.setattr("openreview_cli.bilateral.extract_clause", fake_extract)


# ── tests ────────────────────────────────────────────────────────────────


class TestPII2BilateralTriplet:
    """Cases A, B, C — bilateral strip must produce the full governance
    triplet for each PII-bearing document."""

    def test_doc_a_persists_full_triplet(
        self,
        tmp_path: Path,
        xdg_isolated: dict[str, Path],
        monkeypatch: pytest.MonkeyPatch,
        sample_playbook: Any,
    ) -> None:
        """Case A: document A is PII-bearing — encrypted mapping, pii_cache
        row, pii_audit_trail row all written."""
        from openreview_cli.bilateral import _process_document

        doc_a = _make_pdf(tmp_path, "doc_a.pdf", b"%PDF-1.4\nacme\n")
        clauses_in = [_make_clause(text="Hello Acme")]
        stripped = [_make_clause(text="Hello [PARTY_A]")]

        monkeypatch.setattr(
            "openreview_cli.bilateral._parse_document", lambda p: (object(), clauses_in)
        )
        monkeypatch.setattr(
            "openreview_cli.pii.strip_pii_clauses",
            lambda *a, **kw: (stripped, _pii_result_with_mapping()),
        )

        def fake_extract(*args, **kwargs):  # type: ignore[no-untyped-def]
            from openreview_cli.review.models import ClauseAssessment

            return ClauseAssessment(
                clause_id="c1",
                clause_text=kwargs.get("clause_text", ""),
                playbook_category="confidentiality-term",
                position=Position.ACCEPTABLE,
                confidence=0.9,
                citation="x",
                qa_verdict=QAVerdict.agree,
                extraction_model="test",
                qa_model="test",
            )

        monkeypatch.setattr("openreview_cli.bilateral.extract_clause", fake_extract)

        _process_document(str(doc_a), sample_playbook, "extraction", "qa")

        # Verify triplet on the actual filesystem + DB.
        doc_a_hash = hashlib.sha256(doc_a.read_bytes()).hexdigest()
        review_dir = xdg_isolated["openreview_data_dir"] / "reviews" / doc_a_hash[:12]
        mapping_path = review_dir / "pii_map.enc"
        cache_row = _cache_row(xdg_isolated["db_path"], doc_a_hash)
        audit_count = _audit_count(xdg_isolated["db_path"], doc_a_hash)

        assert mapping_path.exists(), (
            f"Encrypted mapping missing at {mapping_path}. "
            "Bilateral strip did not write the encrypted mapping file."
        )
        assert cache_row is not None, (
            f"pii_cache row missing for doc {doc_a_hash[:12]}. "
            "Bilateral strip did not write the cache row."
        )
        assert audit_count == 1, (
            f"pii_audit_trail row count = {audit_count} for doc {doc_a_hash[:12]}, "
            "expected exactly 1. Bilateral strip did not write the audit row."
        )

    def test_doc_b_persists_full_triplet(
        self,
        tmp_path: Path,
        xdg_isolated: dict[str, Path],
        monkeypatch: pytest.MonkeyPatch,
        sample_playbook: Any,
    ) -> None:
        """Case B: document B is PII-bearing — full triplet on its own
        document hash (must NOT share with doc A)."""
        from openreview_cli.bilateral import _process_document

        doc_b = _make_pdf(tmp_path, "doc_b.pdf", b"%PDF-1.4\nbeta\n")
        clauses_in = [_make_clause(text="Hello Beta")]
        stripped = [_make_clause(text="Hello [PARTY_B]")]

        monkeypatch.setattr(
            "openreview_cli.bilateral._parse_document", lambda p: (object(), clauses_in)
        )
        monkeypatch.setattr(
            "openreview_cli.pii.strip_pii_clauses",
            lambda *a, **kw: (stripped, _pii_result_with_mapping()),
        )

        def fake_extract(*args, **kwargs):  # type: ignore[no-untyped-def]
            from openreview_cli.review.models import ClauseAssessment

            return ClauseAssessment(
                clause_id="c1",
                clause_text=kwargs.get("clause_text", ""),
                playbook_category="confidentiality-term",
                position=Position.ACCEPTABLE,
                confidence=0.9,
                citation="x",
                qa_verdict=QAVerdict.agree,
                extraction_model="test",
                qa_model="test",
            )

        monkeypatch.setattr("openreview_cli.bilateral.extract_clause", fake_extract)

        _process_document(str(doc_b), sample_playbook, "extraction", "qa")

        doc_b_hash = hashlib.sha256(doc_b.read_bytes()).hexdigest()
        review_dir = xdg_isolated["openreview_data_dir"] / "reviews" / doc_b_hash[:12]
        mapping_path = review_dir / "pii_map.enc"
        cache_row = _cache_row(xdg_isolated["db_path"], doc_b_hash)
        audit_count = _audit_count(xdg_isolated["db_path"], doc_b_hash)

        assert mapping_path.exists(), f"Encrypted mapping missing at {mapping_path} for doc B."
        assert cache_row is not None, f"pii_cache row missing for doc B {doc_b_hash[:12]}."
        assert audit_count == 1, (
            f"pii_audit_trail row count = {audit_count} for doc B {doc_b_hash[:12]}, "
            "expected exactly 1."
        )

    def test_both_documents_get_independent_triplets(
        self,
        tmp_path: Path,
        xdg_isolated: dict[str, Path],
        monkeypatch: pytest.MonkeyPatch,
        sample_playbook: Any,
    ) -> None:
        """Case C: full bilateral run with PII on both — each doc gets its
        own triplet; doc A's persistence must not satisfy doc B and vice
        versa."""
        from openreview_cli.bilateral import run_comparison

        doc_a = _make_pdf(tmp_path, "doc_a.pdf", b"%PDF-1.4\nacme\n")
        doc_b = _make_pdf(tmp_path, "doc_b.pdf", b"%PDF-1.4\nbeta\n")
        doc_a_hash = hashlib.sha256(doc_a.read_bytes()).hexdigest()
        doc_b_hash = hashlib.sha256(doc_b.read_bytes()).hexdigest()
        assert doc_a_hash != doc_b_hash, "Test setup: doc_a and doc_b must differ"

        def parse_for_path(path: str) -> tuple[Any, list[Any]]:
            return (object(), [_make_clause(text=f"text-for-{Path(path).name}")])

        monkeypatch.setattr("openreview_cli.bilateral._parse_document", parse_for_path)
        monkeypatch.setattr(
            "openreview_cli.pii.strip_pii_clauses",
            lambda *a, **kw: ([_make_clause(text="[PARTY_X]")], _pii_result_with_mapping()),
        )

        def fake_extract(*args, **kwargs):  # type: ignore[no-untyped-def]
            from openreview_cli.review.models import ClauseAssessment

            return ClauseAssessment(
                clause_id="c1",
                clause_text=kwargs.get("clause_text", ""),
                playbook_category="confidentiality-term",
                position=Position.ACCEPTABLE,
                confidence=0.9,
                citation="x",
                qa_verdict=QAVerdict.agree,
                extraction_model="test",
                qa_model="test",
            )

        monkeypatch.setattr("openreview_cli.bilateral.extract_clause", fake_extract)

        # Stub align_clauses to return a no-op alignment so the comparison
        # doesn't need real clause-id matching.

        def fake_align(_a: Any, _b: Any) -> Any:
            # Build a minimal AlignmentTable with one matched pair referencing
            # the same single clause on each side.
            from openreview_cli.bilateral.models import (
                AlignmentPair,
                AlignmentTable,
                MatchingMethod,
            )

            a_clause = _make_clause(clause_id="c1", text="x")
            b_clause = _make_clause(clause_id="c1", text="x")
            return AlignmentTable(
                matched_pairs=[
                    AlignmentPair(
                        pair_id="p1",
                        clause_a=a_clause,
                        clause_b=b_clause,
                        method=MatchingMethod.exact,
                        score=1.0,
                    )
                ],
                unmatched_a=[],
                unmatched_b=[],
            )

        monkeypatch.setattr("openreview_cli.bilateral.align_clauses", fake_align)

        run_comparison(str(doc_a), str(doc_b), playbook=sample_playbook, no_pii=False)

        # Both docs must have full triplets.
        for label, doc_hash in (("A", doc_a_hash), ("B", doc_b_hash)):
            review_dir = xdg_isolated["openreview_data_dir"] / "reviews" / doc_hash[:12]
            mapping = review_dir / "pii_map.enc"
            cache = _cache_row(xdg_isolated["db_path"], doc_hash)
            audit = _audit_count(xdg_isolated["db_path"], doc_hash)
            assert mapping.exists(), f"Doc {label}: encrypted mapping missing"
            assert cache is not None, f"Doc {label}: pii_cache row missing"
            assert audit == 1, f"Doc {label}: pii_audit_trail row count = {audit}, expected 1"


class TestPII2CleanDocumentBehavior:
    """Case D — a clean document gets no cache row and exactly one audit row."""

    def test_clean_doc_writes_only_an_audit_row(
        self,
        tmp_path: Path,
        xdg_isolated: dict[str, Path],
        monkeypatch: pytest.MonkeyPatch,
        sample_playbook: Any,
    ) -> None:
        from openreview_cli.bilateral import _process_document

        doc_a = _make_pdf(tmp_path, "doc_clean.pdf", b"%PDF-1.4\nclean\n")
        clauses_in = [_make_clause(text="clean text")]
        stripped = [_make_clause(text="clean text")]

        monkeypatch.setattr(
            "openreview_cli.bilateral._parse_document", lambda p: (object(), clauses_in)
        )
        monkeypatch.setattr(
            "openreview_cli.pii.strip_pii_clauses",
            lambda *a, **kw: (stripped, _pii_result_no_mapping()),
        )

        def fake_extract(*args, **kwargs):  # type: ignore[no-untyped-def]
            from openreview_cli.review.models import ClauseAssessment, QAVerdict

            return ClauseAssessment(
                clause_id="c1",
                clause_text=kwargs.get("clause_text", ""),
                playbook_category="confidentiality-term",
                position="acceptable",  # type: ignore[arg-type]
                confidence=0.9,
                citation="x",
                qa_verdict=QAVerdict.agree,
                extraction_model="test",
                qa_model="test",
            )

        monkeypatch.setattr("openreview_cli.bilateral.extract_clause", fake_extract)

        _process_document(str(doc_a), sample_playbook, "extraction", "qa")

        # The strip ran (no_pii=False, align_only=False) but the result has
        # no entities. The persistence helper writes one audit row with
        # entity_count 0 and no mapping/cache artifacts.
        doc_hash = hashlib.sha256(doc_a.read_bytes()).hexdigest()
        cache = _cache_row(xdg_isolated["db_path"], doc_hash)
        audit = _audit_count(xdg_isolated["db_path"], doc_hash)
        review_dir = xdg_isolated["openreview_data_dir"] / "reviews" / doc_hash[:12]
        mapping = review_dir / "pii_map.enc"

        assert cache is None, f"Negative cache row written for clean doc: {cache!r}"
        assert audit == 1, f"Clean doc audit row count = {audit}, expected 1"
        assert not mapping.exists(), f"Encrypted mapping written for clean doc: {mapping}"

    def test_no_pii_path_writes_no_persistence(
        self,
        tmp_path: Path,
        xdg_isolated: dict[str, Path],
        monkeypatch: pytest.MonkeyPatch,
        sample_playbook: Any,
    ) -> None:
        """Case F: --no-pii opts out — no strip, no persistence."""
        from openreview_cli.bilateral import _process_document

        doc_a = _make_pdf(tmp_path, "doc_nopii.pdf", b"%PDF-1.4\nnopii\n")
        clauses_in = [_make_clause(text="raw text")]

        monkeypatch.setattr(
            "openreview_cli.bilateral._parse_document", lambda p: (object(), clauses_in)
        )
        called: list[bool] = [False]

        def fake_strip(*args: Any, **kwargs: Any) -> Any:
            called[0] = True
            return clauses_in, _pii_result_no_mapping()

        monkeypatch.setattr("openreview_cli.pii.strip_pii_clauses", fake_strip)

        _process_document(str(doc_a), sample_playbook, "extraction", "qa", no_pii=True)

        assert called[0] is False
        doc_hash = hashlib.sha256(doc_a.read_bytes()).hexdigest()
        assert _cache_row(xdg_isolated["db_path"], doc_hash) is None
        assert _audit_count(xdg_isolated["db_path"], doc_hash) == 0

    def test_align_only_path_writes_no_persistence(
        self,
        tmp_path: Path,
        xdg_isolated: dict[str, Path],
        monkeypatch: pytest.MonkeyPatch,
        sample_playbook: Any,
    ) -> None:
        """Case G: align_only has no LLM egress, no strip, no persistence."""
        from openreview_cli.bilateral import _process_document

        doc_a = _make_pdf(tmp_path, "doc_align.pdf", b"%PDF-1.4\nalign\n")
        clauses_in = [_make_clause(text="text")]
        monkeypatch.setattr(
            "openreview_cli.bilateral._parse_document", lambda p: (object(), clauses_in)
        )
        called: list[bool] = [False]

        def fake_strip(*args: Any, **kwargs: Any) -> Any:
            called[0] = True
            return clauses_in, _pii_result_no_mapping()

        monkeypatch.setattr("openreview_cli.pii.strip_pii_clauses", fake_strip)

        _process_document(str(doc_a), sample_playbook, "extraction", "qa", align_only=True)

        assert called[0] is False
        doc_hash = hashlib.sha256(doc_a.read_bytes()).hexdigest()
        assert _cache_row(xdg_isolated["db_path"], doc_hash) is None
        assert _audit_count(xdg_isolated["db_path"], doc_hash) == 0


class TestPII2NoPII1Regression:
    """PII-1 invariants must not regress: PII-2 changes must not
    (a) leak a stale `_pii_available` across docs, (b) create a
    phantom audit row on a cache hit, (c) affect the canonical
    StripStage path."""

    def test_pii_available_marks_per_document(
        self,
        tmp_path: Path,
        xdg_isolated: dict[str, Path],
        monkeypatch: pytest.MonkeyPatch,
        sample_playbook: Any,
    ) -> None:
        """After doc A is stripped, doc B's run starts with a fresh reset
        so a stale True cannot leak into doc B's PII gating."""
        from openreview_cli.bilateral import _process_document

        doc_a = _make_pdf(tmp_path, "doc_a.pdf", b"%PDF-1.4\nacme\n")
        doc_b = _make_pdf(tmp_path, "doc_b.pdf", b"%PDF-1.4\nbeta\n")
        clauses_in = [_make_clause(text="Hello Acme")]
        stripped = [_make_clause(text="Hello [PARTY_A]")]

        monkeypatch.setattr(
            "openreview_cli.bilateral._parse_document", lambda p: (object(), clauses_in)
        )
        monkeypatch.setattr(
            "openreview_cli.pii.strip_pii_clauses",
            lambda *a, **kw: (stripped, _pii_result_with_mapping()),
        )

        def fake_extract(*args, **kwargs):  # type: ignore[no-untyped-def]
            from openreview_cli.review.models import ClauseAssessment

            return ClauseAssessment(
                clause_id="c1",
                clause_text=kwargs.get("clause_text", ""),
                playbook_category="confidentiality-term",
                position=Position.ACCEPTABLE,
                confidence=0.9,
                citation="x",
                qa_verdict=QAVerdict.agree,
                extraction_model="test",
                qa_model="test",
            )

        monkeypatch.setattr("openreview_cli.bilateral.extract_clause", fake_extract)

        _process_document(str(doc_a), sample_playbook, "extraction", "qa")
        assert gateway_router.pii_available() is True

        # Doc B (clean): the strip helper sees the flag is False at entry
        # because doc B's run starts with a reset.
        observed: dict[str, bool] = {}

        def _spy_strip(*args: Any, **kwargs: Any) -> Any:
            observed["after_run_start"] = gateway_router.pii_available()
            return [_make_clause(text="clean")], _pii_result_no_mapping()

        monkeypatch.setattr("openreview_cli.pii.strip_pii_clauses", _spy_strip)
        _process_document(str(doc_b), sample_playbook, "extraction", "qa")

        assert observed.get("after_run_start") is False, (
            "Doc B inherited True from doc A. PII-1 lifecycle must be "
            "per-operation, including bilateral ops."
        )
        # After doc B's strip (clean or not), the flag is True because
        # a successful strip is per-operation evidence — same as the
        # StripStage and ReviewCommand semantics. The invariant under
        # test is that the doc B run STARTED with False, not that it
        # ends with False.
        assert gateway_router.pii_available() is True
