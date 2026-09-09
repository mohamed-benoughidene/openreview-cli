"""PII-1 — ReviewCommand cache-hit `_pii_available` lifecycle.

Establishes the invariant that `_pii_available` is per-operation evidence,
not persistent state from a previous operation. Cases:

  A. Stale state must not leak across sequential ReviewCommand.run() invocations
     in the same process.
  B. A valid cache hit marks `_pii_available = True` because the cached
     artifact is already stripped text.
  C. A cache hit must NOT create a phantom/duplicate PII audit-trail row.
  D. A fresh strip still marks `_pii_available = True` (existing behavior).
  E. Sequential operations on the same ReviewCommand instance cannot leak
     `_pii_available` state from operation N to operation N+1.

Tests use the real ReviewCommand class. Heavy dependencies (_parse_document,
strip_and_persist, PiiCache DB write) are mocked at the seam so the test
isolates the lifecycle defect from PII engine loading, PDF parsing, and
encryption. XDG paths are isolated via monkeypatch.
"""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Generator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from openreview_cli.gateway import router as gateway_router
from openreview_cli.pii.cache import PiiCache
from openreview_cli.pii.models import PiiResult
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


def _pii_result_with_mapping() -> PiiResult:
    return PiiResult(
        stripped_text="Hello [PARTY_A]",
        mapping={"PARTY_A": "Acme"},
        entities=[_entity("ORGANIZATION", "[PARTY_A]", original="Acme")],
        page_count=1,
        duration_seconds=1.0,
        warnings=[],
    )


def _pii_result_no_mapping() -> PiiResult:
    return PiiResult(
        stripped_text="clean text",
        mapping={},
        entities=[],
        page_count=1,
        duration_seconds=1.0,
        warnings=[],
    )


def _write_pii_cache_row(db_path: Path, doc_hash: str, config_hash: str) -> Path:
    """Seed a valid cache row pointing at an existing stripped.txt file."""
    review_dir = db_path.parent / doc_hash[:12]
    review_dir.mkdir(parents=True, exist_ok=True)
    stripped = review_dir / "stripped.txt"
    stripped.write_text("cached stripped content", encoding="utf-8")
    mapping = review_dir / "pii_map.enc"
    mapping.write_text("encrypted-bytes", encoding="utf-8")
    PiiCache(db_path).put(doc_hash, config_hash, str(stripped), str(mapping), ttl_days=30)
    return stripped


@pytest.fixture
def xdg_isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """XDG-isolate the config/data/review directories so ReviewCommand
    touches a fresh, per-test filesystem instead of the real ~/.config.

    platformdirs appends the app name to XDG paths, so get_config_dir()
    returns XDG_CONFIG_HOME/openreview and get_data_dir() returns
    XDG_DATA_HOME/openreview. We materialize the file at the right path
    and pre-initialize the SQLite schema so PiiCache works.
    """
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
        "openreview_config_dir": openreview_config_dir,
        "openreview_data_dir": openreview_data_dir,
        "config_path": cfg_path,
        "db_path": db_path,
    }


@pytest.fixture(autouse=True)
def _reset_pii_flag_after() -> Generator[None, None, None]:
    """Reset the process-global PII flag between tests (test isolation)."""
    yield
    gateway_router.reset_pii_available()


def _stub_parse(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch ReviewCommand._parse_document to return a fake clause list
    (no PDF parsing, no PII engine)."""
    from openreview_cli.review import base as base_mod

    fake_clause = SimpleNamespace(id="c1", title="t", text="Hello Acme", level=0, parent_id=None)
    monkeypatch.setattr(
        base_mod.ReviewCommand, "_parse_document", lambda self: ([fake_clause], object())
    )


def _make_doc(tmp_path: Path, name: str = "doc.pdf", body: bytes = b"%PDF-1.4\n") -> Path:
    p = tmp_path / name
    p.write_bytes(body)
    return p


# ── tests ────────────────────────────────────────────────────────────────


class TestPII1StaleStateDoesNotLeak:
    """Case A — operation N+1 must not inherit `_pii_available=True`
    from a previous operation that succeeded."""

    def test_fresh_strip_then_disabled_run_resets_flag(
        self, tmp_path: Path, xdg_isolated: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Operation 1: PII-bearing doc + fresh strip marks True.
        Operation 2: --no-pii on a different doc MUST reset to False.
        """
        from openreview_cli.review.base import ReviewCommand

        doc1 = _make_doc(tmp_path, "d1.pdf", b"%PDF-1.4\nop1\n")
        _stub_parse(monkeypatch)
        monkeypatch.setattr(
            "openreview_cli.review.base.strip_and_persist",
            lambda *a, **kw: _pii_result_with_mapping(),
        )

        cmd1 = ReviewCommand(
            document_path=str(doc1), pii_enabled=True, output_dir=str(tmp_path / "out1")
        )
        result1 = cmd1.run()
        assert result1["cached"] is False
        assert gateway_router.pii_available() is True

        doc2 = _make_doc(tmp_path, "d2.pdf", b"%PDF-1.4\nop2\n")
        _stub_parse(monkeypatch)

        cmd2 = ReviewCommand(
            document_path=str(doc2), pii_enabled=False, output_dir=str(tmp_path / "out2")
        )
        result2 = cmd2.run()
        assert result2["cached"] is False
        assert gateway_router.pii_available() is False

    def test_clean_fresh_strip_does_not_leak_true_to_next_op(
        self, tmp_path: Path, xdg_isolated: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Operation 1: PII-bearing doc + fresh strip -> True.
        Operation 2: PII-enabled but clean doc starts in a process where
        the flag is True. The second op's start MUST reset the flag so
        its own cloud calls are correctly gated.
        """
        from openreview_cli.review.base import ReviewCommand

        doc1 = _make_doc(tmp_path, "d1.pdf", b"%PDF-1.4\nop1\n")
        _stub_parse(monkeypatch)
        monkeypatch.setattr(
            "openreview_cli.review.base.strip_and_persist",
            lambda *a, **kw: _pii_result_with_mapping(),
        )
        cmd1 = ReviewCommand(
            document_path=str(doc1), pii_enabled=True, output_dir=str(tmp_path / "out1")
        )
        assert cmd1.run()["cached"] is False
        assert gateway_router.pii_available() is True

        doc2 = _make_doc(tmp_path, "d2.pdf", b"%PDF-1.4\nop2\n")
        _stub_parse(monkeypatch)
        observed: dict[str, bool] = {}

        def _spy_strip(*args: Any, **kwargs: Any) -> Any:
            observed["after_run_start"] = gateway_router.pii_available()
            return _pii_result_no_mapping()

        monkeypatch.setattr("openreview_cli.review.base.strip_and_persist", _spy_strip)
        cmd2 = ReviewCommand(
            document_path=str(doc2), pii_enabled=True, output_dir=str(tmp_path / "out2")
        )
        cmd2.run()
        assert observed.get("after_run_start") is False, (
            "ReviewCommand.run did not reset _pii_available at operation "
            "start -- stale True from prior operation leaked into op 2"
        )


class TestPII1CacheHitMarksFlag:
    """Case B -- a valid cache hit MUST mark `_pii_available = True`."""

    def test_cache_hit_marks_pii_available(
        self, tmp_path: Path, xdg_isolated: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from openreview_cli.review.base import ReviewCommand

        sentinel_config_hash = "sentinel-config-hash"

        from openreview_cli.review import base as base_mod

        monkeypatch.setattr(
            base_mod.ReviewCommand, "_compute_config_hash", lambda self: sentinel_config_hash
        )

        doc1 = _make_doc(tmp_path, "d1.pdf", b"%PDF-1.4\nseed\n")
        doc_hash = hashlib.sha256(doc1.read_bytes()).hexdigest()
        db_path: Path = xdg_isolated["db_path"]
        _write_pii_cache_row(db_path, doc_hash, sentinel_config_hash)

        gateway_router.reset_pii_available()
        assert gateway_router.pii_available() is False

        _stub_parse(monkeypatch)

        cmd = ReviewCommand(
            document_path=str(doc1), pii_enabled=True, output_dir=str(tmp_path / "out")
        )
        result = cmd.run()
        assert result["cached"] is True

        assert gateway_router.pii_available() is True, (
            "Cache hit did not mark _pii_available=True -- the cached "
            "artifact is already-stripped text and IS the evidence"
        )


class TestPII1CacheHitNoPhantomAudit:
    """Case C -- a cache hit must NOT create a phantom PII audit-trail row."""

    def test_cache_hit_does_not_write_audit_row(
        self, tmp_path: Path, xdg_isolated: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from openreview_cli.review.base import ReviewCommand

        sentinel_config_hash = "sentinel-config-hash"

        from openreview_cli.review import base as base_mod

        monkeypatch.setattr(
            base_mod.ReviewCommand, "_compute_config_hash", lambda self: sentinel_config_hash
        )

        doc1 = _make_doc(tmp_path, "d1.pdf", b"%PDF-1.4\nseed\n")
        doc_hash = hashlib.sha256(doc1.read_bytes()).hexdigest()
        db_path: Path = xdg_isolated["db_path"]
        _write_pii_cache_row(db_path, doc_hash, sentinel_config_hash)

        _stub_parse(monkeypatch)

        cmd = ReviewCommand(
            document_path=str(doc1), pii_enabled=True, output_dir=str(tmp_path / "out")
        )
        result = cmd.run()
        assert result["cached"] is True

        conn = sqlite3.connect(str(db_path))
        try:
            rows = conn.execute(
                "SELECT * FROM pii_audit_trail WHERE document_hash = ?",
                (doc_hash,),
            ).fetchall()
        finally:
            conn.close()
        assert rows == [], (
            f"Cache hit created phantom audit rows for doc {doc_hash[:12]}: "
            f"{rows!r}. Audit rows are written only by a fresh strip."
        )


class TestPII1FreshStripStillWorks:
    """Case D -- fresh strip path is unchanged."""

    def test_fresh_pii_strip_marks_flag(
        self, tmp_path: Path, xdg_isolated: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from openreview_cli.review.base import ReviewCommand

        doc = _make_doc(tmp_path, "d.pdf", b"%PDF-1.4\nfresh\n")
        _stub_parse(monkeypatch)
        monkeypatch.setattr(
            "openreview_cli.review.base.strip_and_persist",
            lambda *a, **kw: _pii_result_with_mapping(),
        )
        gateway_router.reset_pii_available()
        cmd = ReviewCommand(
            document_path=str(doc), pii_enabled=True, output_dir=str(tmp_path / "out")
        )
        result = cmd.run()
        assert result["cached"] is False
        assert gateway_router.pii_available() is True


class TestPII1SequentialSameInstance:
    """Case E -- sequential ReviewCommand.run() calls in one process.
    Op N's `_pii_available` must not silently affect op N+1."""

    def test_two_sequential_runs_reset_each_time(
        self, tmp_path: Path, xdg_isolated: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from openreview_cli.review.base import ReviewCommand

        doc1 = _make_doc(tmp_path, "d1.pdf", b"%PDF-1.4\nop1\n")
        _stub_parse(monkeypatch)
        monkeypatch.setattr(
            "openreview_cli.review.base.strip_and_persist",
            lambda *a, **kw: _pii_result_with_mapping(),
        )
        cmd = ReviewCommand(
            document_path=str(doc1), pii_enabled=True, output_dir=str(tmp_path / "out1")
        )
        cmd.run()
        assert gateway_router.pii_available() is True

        doc2 = _make_doc(tmp_path, "d2.pdf", b"%PDF-1.4\nop2\n")
        _stub_parse(monkeypatch)
        observed: list[bool] = []

        def _spy_strip(*args: Any, **kwargs: Any) -> Any:
            observed.append(gateway_router.pii_available())
            return _pii_result_no_mapping()

        monkeypatch.setattr("openreview_cli.review.base.strip_and_persist", _spy_strip)
        cmd2 = ReviewCommand(
            document_path=str(doc2), pii_enabled=True, output_dir=str(tmp_path / "out2")
        )
        cmd2.run()
        assert observed == [False], (
            f"Expected flag=False at second op's strip entry, got {observed!r}. "
            "Stale True from op 1 leaked into op 2."
        )
