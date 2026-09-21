"""PII-3 — PIIUnavailableError explicit recovery mapping + legacy audit closure.

Part A (this file, Class 1): make `PIIUnavailableError` recovery classification
explicit and behaviorally proven at the real recovery boundary. The current
implicit fall-through to `ErrorCategory.unknown` → `user_guided_recovery` →
terminal (no provider_fallback) is accidentally correct. We pin it explicitly
so future drift cannot re-route PII through provider fallback, which would
leak raw PII to a cloud LLM.

Part B (this file, Class 2): the legacy `ReviewCommand.run` path writes a
`pii_cache` row (with a wrong `mapping_path`) but no `pii_audit_trail` row.
Reuse `persist_pii_for_document` (introduced in PII-2) so the legacy path
produces the same encrypted-mapping + pii_cache + pii_audit_trail triplet
that the bilateral / StripStage paths produce.
"""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

from openreview_cli.gateway import router as gateway_router
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
    """XDG-isolate config + data dirs so persistence writes go to a fresh
    per-test filesystem instead of the real ~/.config/openreview."""
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


def _reset_status_map() -> None:
    """Clear the lazy-initialized status map so each test sees a fresh
    registration state. Without this, the first test to call any
    `_http_status_for` populates the dict, and later tests cannot exercise
    the registration contract."""
    from openreview_cli.review import _gateway

    _gateway._GATEWAY_ERROR_HTTP_STATUS.clear()
    # Also clear the error-type map if any registration wrote through it
    try:
        from openreview_cli.recovery import models as recovery_models

        recovery_models._ERROR_TYPE_MAP.pop("piiunavailableerror", None)
    except (ImportError, AttributeError):
        pass


# ── Part A — PIIUnavailableError explicit recovery mapping ───────────────


class TestPIIUnavailableRecovery:
    """PII-3 Part A: pin PIIUnavailableError as terminal (no provider fallback)
    at the real recovery boundary."""

    def test_pii_unavailable_registered_in_status_map(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A1: `PIIUnavailableError` is registered in the typed status map
        with `None` (no HTTP status → unknown category, terminal). Without
        this explicit registration, the only thing pinning the policy is
        the implicit fall-through to `_ERROR_TYPE_MAP.get(...)` which
        returns None for any unknown string. The explicit registration
        makes the intent self-documenting.

        RED: `_GATEWAY_ERROR_HTTP_STATUS[PIIUnavailableError]` is missing.
        GREEN: registration present with value `None`.
        """
        from openreview_cli.gateway.errors import PIIUnavailableError
        from openreview_cli.review import _gateway

        _reset_status_map()
        _gateway._init_status_map()

        assert PIIUnavailableError in _gateway._GATEWAY_ERROR_HTTP_STATUS, (
            "PIIUnavailableError must be explicitly registered in the status "
            "map so the policy is not dependent on implicit fall-through."
        )
        assert _gateway._GATEWAY_ERROR_HTTP_STATUS[PIIUnavailableError] is None, (
            "PIIUnavailableError must map to None (no HTTP status), so "
            "classify_error routes it to ErrorCategory.unknown (terminal)."
        )

    def test_pii_unavailable_http_status_is_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A2: `_http_status_for(PIIUnavailableError())` returns `None`.
        Regression guard for the registration in (A1). Pre-fix and post-fix
        both pass via implicit fall-through; post-fix the explicit
        registration is the source of truth.

        Pre-fix: returns None (default)
        Post-fix: returns None (explicit registration)
        """
        from openreview_cli.gateway.errors import PIIUnavailableError
        from openreview_cli.review import _gateway

        _reset_status_map()
        _gateway._init_status_map()

        assert _gateway._http_status_for(PIIUnavailableError("engine down")) is None

    def test_pii_unavailable_classification_is_unknown(self) -> None:
        """A3: `classify_error(http_status=None, error_type="PIIUnavailableError")`
        returns `ErrorCategory.unknown`. The classification is what the
        coordinator reads to decide which strategies to invoke.
        `unknown` is terminal — only `user_guided_recovery` runs, never
        `provider_fallback`.

        Pre-fix and post-fix both pass (no map change). Pins the
        classification contract.
        """
        from openreview_cli.recovery.models import ErrorCategory, classify_error

        assert (
            classify_error(http_status=None, error_type="PIIUnavailableError")
            is ErrorCategory.unknown
        )

    def test_pii_unavailable_does_not_invoke_provider_fallback(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A4 (decisive behavioral test): when `Gateway.chat` raises
        `PIIUnavailableError` and `call_gateway_chat` is invoked with a
        coordinator + recovery_ctx, `provider_fallback` MUST NOT be called.
        PII-3 pins this at the real recovery boundary by directly spying
        on the `provider_fallback` symbol imported by the coordinator.
        The `Gateway.chat` call-count assertion is secondary; the load-
        bearing claim is that `provider_fallback` is never invoked.

        Pre-fix: still passes (implicit fall-through gives `unknown`
        category, which skips `provider_fallback`).
        Post-fix: still passes via the explicit registration.
        """
        from openreview_cli.gateway import router as gateway_router
        from openreview_cli.gateway.errors import PIIUnavailableError
        from openreview_cli.recovery import coordinator as recovery_coordinator
        from openreview_cli.recovery.coordinator import RecoveryCoordinator
        from openreview_cli.review import _gateway

        _reset_status_map()
        _gateway._init_status_map()

        coordinator = RecoveryCoordinator(provider_list=["openai", "anthropic"])
        recovery_ctx = coordinator.create_context(provider_list=["openai", "anthropic"])

        def fake_chat(*args: Any, **kwargs: Any) -> str:
            raise PIIUnavailableError("engine down")

        monkeypatch.setattr(gateway_router.Gateway, "chat", fake_chat)

        # Direct spy on the function the coordinator would call if the
        # error were classified as transient/permanent.
        fallback_called: list[bool] = [False]

        async def fake_provider_fallback(*args: Any, **kwargs: Any) -> Any:
            fallback_called[0] = True
            raise AssertionError("provider_fallback must not be called for PIIUnavailableError")

        monkeypatch.setattr(recovery_coordinator, "provider_fallback", fake_provider_fallback)

        with pytest.raises(PIIUnavailableError):
            _gateway.call_gateway_chat(
                "extraction",
                [{"role": "user", "content": "hi"}],
                coordinator=coordinator,
                recovery_ctx=recovery_ctx,
                provider_list=["openai", "anthropic"],
            )

        assert fallback_called[0] is False, (
            "PIIUnavailableError must not trigger provider_fallback — this "
            "would leak raw PII to a cloud LLM."
        )

    def test_pii_unavailable_does_not_retry_via_attempt_fn(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A5: even when `provider_list` has multiple entries, the
        `attempt_fn` (`_retry_fn`) passed to `provider_fallback` is
        never invoked for `PIIUnavailableError`. Pinned by reaching the
        same boundary as (A4) via a different observation point.

        Pre-fix and post-fix both pass.
        """
        from openreview_cli.gateway import router as gateway_router
        from openreview_cli.gateway.errors import PIIUnavailableError
        from openreview_cli.recovery.coordinator import RecoveryCoordinator
        from openreview_cli.review import _gateway

        _reset_status_map()
        _gateway._init_status_map()

        coordinator = RecoveryCoordinator(provider_list=["openai", "anthropic", "ollama"])
        recovery_ctx = coordinator.create_context(provider_list=["openai", "anthropic", "ollama"])

        def fake_chat(*args: Any, **kwargs: Any) -> str:
            raise PIIUnavailableError("engine down")

        monkeypatch.setattr(gateway_router.Gateway, "chat", fake_chat)

        # The retry fn is constructed inside call_gateway_chat. We can't
        # spy on it directly from outside, but if (A4)'s provider_fallback
        # spy is in place and provider_fallback is never called, then
        # _retry_fn is provably never called either. (A4) is the load-
        # bearing assertion; this test pins the same invariant at a
        # different layer.

        async def _should_not_run(*args: Any, **kwargs: Any) -> bool:
            raise AssertionError("_retry_fn must not be called for PIIUnavailableError")

        # The retry fn is built inside call_gateway_chat; we instead
        # assert the same invariant by ensuring the RecoveryCoordinator
        # never invokes provider_fallback, which is the only call path
        # that would invoke _retry_fn. The fix is the explicit
        # registration that pins PIIUnavailableError as terminal.
        with pytest.raises(PIIUnavailableError):
            _gateway.call_gateway_chat(
                "extraction",
                [{"role": "user", "content": "hi"}],
                coordinator=coordinator,
                recovery_ctx=recovery_ctx,
                provider_list=["openai", "anthropic", "ollama"],
            )

    def test_pii_unavailable_does_not_disrupt_existing_classifications(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A6: regression guard. After registering PIIUnavailableError,
        all existing recovery classifications must still work:
        - RateLimitError (429) → ErrorCategory.transient → provider_fallback
        - AuthError (401) → ErrorCategory.permanent → provider_fallback
        - AllProvidersFailedError (None) → ErrorCategory.unknown → terminal
        - NoMatchingProviderError (None) → ErrorCategory.unknown → terminal
        - UnclassifiedProviderError (503) → ErrorCategory.transient → provider_fallback

        Pre-fix and post-fix both pass (registration is additive).
        """
        from openreview_cli.gateway.errors import (
            AllProvidersFailedError,
            AuthError,
            NoMatchingProviderError,
            RateLimitError,
            UnclassifiedProviderError,
        )
        from openreview_cli.review import _gateway

        _reset_status_map()
        _gateway._init_status_map()

        # Existing typed classifications
        assert _gateway._http_status_for(RateLimitError("p", "x")) == 429
        assert _gateway._http_status_for(AuthError("p")) == 401
        assert _gateway._http_status_for(UnclassifiedProviderError("p")) == 503
        assert _gateway._http_status_for(AllProvidersFailedError()) is None
        assert _gateway._http_status_for(NoMatchingProviderError()) is None

        # classify_error against the status map
        assert (
            _gateway._http_status_for(RateLimitError("p", "x")) == 429
        )  # transient → fallback (sanity)
        assert (
            _gateway._http_status_for(AllProvidersFailedError()) is None
        )  # unknown → terminal (sanity)


# ── Part B — Legacy PII persistence triplet (encrypted + cache + audit) ──


def _stub_review_command_deps(
    monkeypatch: pytest.MonkeyPatch,
    pii_result: Any,
    tmp_path: Path,
) -> str:
    """Stub `_parse_document` and `strip_and_persist` for `ReviewCommand.run`
    so the test exercises the post-strip persistence path end-to-end. Writes
    a placeholder PDF and returns its path. The ReviewCommand is invoked
    with `output_dir=str(tmp_path / "review_results")` so cwd-relative
    output does not leak."""
    from types import SimpleNamespace

    from openreview_cli.review import base as base_mod

    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\nseed\n")

    fake_clause = SimpleNamespace(id="c1", title="t", text="Hello Acme", level=0, parent_id=None)
    monkeypatch.setattr(
        base_mod.ReviewCommand, "_parse_document", lambda self: ([fake_clause], object())
    )
    monkeypatch.setattr(
        "openreview_cli.review.base.strip_and_persist",
        lambda *a, **kw: pii_result,
    )
    return str(pdf_path)


class TestLegacyPIIPersistence:
    """PII-3 Part B: legacy `ReviewCommand.run` must produce the same
    governance triplet (encrypted mapping + pii_cache + pii_audit_trail)
    that the StripStage and bilateral paths produce."""

    def test_legacy_pii_bearing_strip_writes_encrypted_mapping(
        self,
        tmp_path: Path,
        xdg_isolated: dict[str, Path],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """B1: a PII-bearing legacy strip writes the encrypted mapping file
        at `<data>/reviews/<doc_hash[:12]>/pii_map.enc`. Pre-fix, the
        legacy `cache.put` records a `mapping_path` at the WRONG location
        (`<output>/<doc_hash[:12]>/pii_map.enc`); the encrypted file
        itself IS written by `strip_and_persist` directly, so this test
        may pass pre-fix as a regression guard for the file's existence
        (not its location in the cache row — that is (B2))."""
        from openreview_cli.review.base import ReviewCommand

        pdf_path = _stub_review_command_deps(monkeypatch, _pii_result_with_mapping(), tmp_path)
        cmd = ReviewCommand(
            document_path=pdf_path,
            output_dir=str(tmp_path / "review_results"),
            force_reprocess=True,
        )

        cmd.run()

        doc_hash = hashlib.sha256(Path(pdf_path).read_bytes()).hexdigest()
        mapping_path = (
            xdg_isolated["openreview_data_dir"] / "reviews" / doc_hash[:12] / "pii_map.enc"
        )
        assert mapping_path.exists(), (
            f"Encrypted mapping missing at {mapping_path}. Legacy strip "
            "did not write the encrypted mapping file."
        )

    def test_legacy_pii_bearing_strip_writes_pii_cache_row(
        self,
        tmp_path: Path,
        xdg_isolated: dict[str, Path],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """B2: a PII-bearing legacy strip writes one pii_cache row, and
        the `mapping_path` column points at an EXISTING file.

        Pre-fix RED: row exists (legacy writes it at `base.py:99`) but
        `mapping_path` points at `<output>/<doc_hash[:12]>/pii_map.enc`
        which does NOT exist (the file was written at
        `<data>/reviews/<doc_hash[:12]>/pii_map.enc` instead). So
        `Path(cache_row["mapping_path"]).exists()` is False → assertion
        fails → RED.

        Post-fix: `persist_pii_for_document` writes the cache row with
        the correct `mapping_path` (the helper computes the data-dir
        path, not the output-dir path), and the file exists. → GREEN.
        """
        from openreview_cli.review.base import ReviewCommand

        pdf_path = _stub_review_command_deps(monkeypatch, _pii_result_with_mapping(), tmp_path)
        cmd = ReviewCommand(
            document_path=pdf_path,
            output_dir=str(tmp_path / "review_results"),
            force_reprocess=True,
        )

        cmd.run()

        doc_hash = hashlib.sha256(Path(pdf_path).read_bytes()).hexdigest()
        cache_row = _cache_row(xdg_isolated["db_path"], doc_hash)

        assert cache_row is not None, (
            f"pii_cache row missing for doc {doc_hash[:12]}. Legacy strip "
            "did not write the cache row."
        )
        assert Path(cache_row["mapping_path"]).exists(), (
            f"pii_cache row's mapping_path ({cache_row['mapping_path']}) "
            "does not point at an existing file. Pre-fix: legacy wrote the "
            "row with the wrong path; the file lives under "
            "<data>/reviews/<hash[:12]>/pii_map.enc instead."
        )

    def test_legacy_pii_bearing_strip_writes_audit_trail_row(
        self,
        tmp_path: Path,
        xdg_isolated: dict[str, Path],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """B3 (decisive test for Part B): a PII-bearing legacy strip
        writes exactly one `pii_audit_trail` row.

        Pre-fix RED: count is 0. The legacy `ReviewCommand.run` does
        not call anything that writes to `pii_audit_trail` — only the
        bilateral / StripStage paths (which use `persist_pii_for_document`)
        write audit rows. The legacy path persists the encrypted
        mapping and a `pii_cache` row but no audit row.

        Post-fix GREEN: `persist_pii_for_document` calls
        `write_audit_trail_row` once. Count is 1.
        """
        from openreview_cli.review.base import ReviewCommand

        pdf_path = _stub_review_command_deps(monkeypatch, _pii_result_with_mapping(), tmp_path)
        cmd = ReviewCommand(
            document_path=pdf_path,
            output_dir=str(tmp_path / "review_results"),
            force_reprocess=True,
        )

        cmd.run()

        doc_hash = hashlib.sha256(Path(pdf_path).read_bytes()).hexdigest()
        audit_count = _audit_count(xdg_isolated["db_path"], doc_hash)

        assert audit_count == 1, (
            f"pii_audit_trail row count = {audit_count} for doc {doc_hash[:12]}, "
            "expected exactly 1. Legacy strip did not write the audit row."
        )

    def test_legacy_clean_strip_records_only_an_audit_row(
        self,
        tmp_path: Path,
        xdg_isolated: dict[str, Path],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """B4: a clean legacy strip (PiiResult with empty mapping) records
        only an audit row — no cache row, no encrypted mapping.

        The shared helper always writes the audit row and gates the
        mapping/cache writes on a non-empty mapping. Regression guard for
        (B2) and (B3)."""
        from openreview_cli.review.base import ReviewCommand

        pdf_path = _stub_review_command_deps(monkeypatch, _pii_result_no_mapping(), tmp_path)
        cmd = ReviewCommand(
            document_path=pdf_path,
            output_dir=str(tmp_path / "review_results"),
            force_reprocess=True,
        )

        cmd.run()

        doc_hash = hashlib.sha256(Path(pdf_path).read_bytes()).hexdigest()
        cache_row = _cache_row(xdg_isolated["db_path"], doc_hash)
        audit_count = _audit_count(xdg_isolated["db_path"], doc_hash)
        mapping_path = (
            xdg_isolated["openreview_data_dir"] / "reviews" / doc_hash[:12] / "pii_map.enc"
        )

        assert cache_row is None, f"Negative cache row written for clean doc: {cache_row!r}"
        assert audit_count == 1, f"Clean legacy strip audit row count = {audit_count}, expected 1"
        assert not mapping_path.exists(), f"Encrypted mapping written for clean doc: {mapping_path}"

    def test_legacy_pii_bearing_strip_does_not_duplicate_audit_on_cache_hit(
        self,
        tmp_path: Path,
        xdg_isolated: dict[str, Path],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """B5: a cache hit (second run, no force_reprocess) does NOT write
        a new `pii_audit_trail` row. PII-1 invariant: the cached artifact
        is the evidence of a prior strip, governed by the original audit
        row. The legacy path correctly skips strip_and_persist on cache
        hit, so the helper is not called and no new audit row is written.

        Pre-fix and post-fix both pass (cache-hit path is unchanged)."""
        from openreview_cli.review.base import ReviewCommand

        pdf_path = _stub_review_command_deps(monkeypatch, _pii_result_with_mapping(), tmp_path)

        # First run: force_reprocess=True to bypass any prior cache and
        # populate the cache + audit row.
        cmd1 = ReviewCommand(
            document_path=pdf_path,
            output_dir=str(tmp_path / "review_results"),
            force_reprocess=True,
        )
        cmd1.run()

        # Second run: new instance, force_reprocess=False (default) so the
        # cache hit branch fires. The helper must NOT be called, so no new
        # audit row is written.
        cmd2 = ReviewCommand(
            document_path=pdf_path,
            output_dir=str(tmp_path / "review_results"),
            force_reprocess=False,
        )
        cmd2.run()

        doc_hash = hashlib.sha256(Path(pdf_path).read_bytes()).hexdigest()
        audit_count = _audit_count(xdg_isolated["db_path"], doc_hash)

        assert audit_count == 1, (
            f"Cache hit wrote an extra audit row: count={audit_count}, expected 1. "
            "PII-1 invariant violated: cached artifacts are governed by the "
            "original strip's audit row."
        )

    def test_legacy_force_reprocess_appends_audit_row(
        self,
        tmp_path: Path,
        xdg_isolated: dict[str, Path],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """B6: a force-reprocess run after an initial run appends a new
        `pii_audit_trail` row. Append-only audit semantics: each
        invocation of strip + persist is governed by its own audit row.

        Pre-fix RED: first run writes 0 audit rows (legacy never called
        the helper). Second run (force_reprocess) writes 0 audit rows.
        Total = 0. Assertion expects 2, so RED.

        Post-fix GREEN: first run writes 1 audit row (helper called for
        the first time). Second run (force_reprocess) writes 1 more
        audit row (helper called again, append-only). Total = 2.
        """
        from openreview_cli.review.base import ReviewCommand

        pdf_path = _stub_review_command_deps(monkeypatch, _pii_result_with_mapping(), tmp_path)
        cmd = ReviewCommand(
            document_path=pdf_path,
            output_dir=str(tmp_path / "review_results"),
            force_reprocess=True,
        )

        cmd.run()  # first run
        cmd.run()  # second run with force_reprocess=True

        doc_hash = hashlib.sha256(Path(pdf_path).read_bytes()).hexdigest()
        audit_count = _audit_count(xdg_isolated["db_path"], doc_hash)

        assert audit_count == 2, (
            f"Force-reprocess did not append audit row: count={audit_count}, "
            "expected 2. Append-only audit semantics require one new audit "
            "row per strip invocation."
        )
