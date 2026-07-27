"""PII stripping engine — Presidio wrapper with page-sequential processing."""

import logging
import time
from collections.abc import Callable
from typing import Any

from openreview_cli.parsing.models import Clause
from openreview_cli.pii.audit import build_audit, write_pii_audit
from openreview_cli.pii.mapping import write_pii_mapping
from openreview_cli.pii.models import (
    PiiEntity,
    PiiError,
    PiiResult,
)
from openreview_cli.pii.placeholders import assign_placeholders
from openreview_cli.pii.recognizers import get_custom_recognizers

_TEMP_PH = "[TEMP_0]"  # ponytail: placeholder overwritten by assign_placeholders

logger = logging.getLogger(__name__)


class PiiEngine:
    """PII detection and stripping engine wrapping Presidio analyzer + anonymizer."""

    def __init__(self, threshold: float = 0.7):
        self._threshold = threshold
        self._analyzer: Any = None
        self._is_available_cache: bool | None = None

    def _ensure_analyzer(self) -> Any:
        if self._analyzer is not None:
            return self._analyzer

        from presidio_analyzer import AnalyzerEngine
        from presidio_analyzer.nlp_engine import SpacyNlpEngine

        try:
            model_config = [{"lang_code": "en", "model_name": "en_core_web_lg"}]
            nlp_engine = SpacyNlpEngine(models=model_config)
            self._analyzer = AnalyzerEngine(nlp_engine=nlp_engine)
        except (OSError, SystemExit) as err:
            raise PiiError(
                exit_code=9,
                category="model_not_found",
                clause_heading=None,
                phase=None,
                message="PII detection model not found. Run: python -m spacy download en_core_web_lg",
                action="python -m spacy download en_core_web_lg",
            ) from err

        for recognizer in get_custom_recognizers():
            self._analyzer.registry.add_recognizer(recognizer)

        return self._analyzer

    def detect_on_page(
        self,
        text: str,
        threshold: float | None = None,
        is_non_english: bool = False,
        clause_heading: str | None = None,
    ) -> list[Any]:
        analyzer = self._ensure_analyzer()
        threshold = threshold if threshold is not None else self._threshold

        try:
            results = analyzer.analyze(
                text=text,
                language="en",
                score_threshold=threshold,
            )

            if is_non_english:
                results = [r for r in results if r.score >= 1.0]
        except Exception as exc:
            phase = "regex phase" if is_non_english else "NER phase"
            heading = clause_heading or "Unknown"
            raise PiiError(
                exit_code=9,
                category="engine_crash",
                clause_heading=heading,
                phase=phase,
                message=f"PII detection failed while processing clause '{heading}' ({phase}). Run with --no-pii to skip stripping. Report this bug.",
                action="Run with --no-pii to skip stripping. Report this bug.",
            ) from exc

        entities = []
        for r in results:
            entity = PiiEntity(
                entity_type=r.entity_type,
                original_value=text[r.start : r.end],
                start=r.start,
                end=r.end,
                score=r.score,
                placeholder=_TEMP_PH,
                source="regex" if r.score == 1.0 else "nlp",
            )
            entities.append(entity)

        return entities

    def detect_all_pages(
        self,
        clauses: list[Any],
        threshold: float | None = None,
        page_count: int | None = None,
        allow_partial: bool = False,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> tuple[list[Any], list[Any], list[int], dict[int, str]]:
        threshold = threshold if threshold is not None else self._threshold
        all_entities: list[Any] = []
        warnings: list[Any] = []
        failed_pages: list[int] = []
        error_messages: dict[int, str] = {}
        successful_pages: list[int] = []

        sorted_clauses = sorted(
            clauses,
            key=lambda c: (
                (
                    c.source_page or 0,
                    c.source_paragraph or 0,
                )
                if hasattr(c, "source_page")
                else 0
            ),
        )

        total_pages = page_count or max((c.source_page or 1 for c in sorted_clauses), default=1)

        overlap_buffer = ""
        current_page = 0
        for idx, clause in enumerate(sorted_clauses):
            combined = overlap_buffer + clause.text
            is_non_english = getattr(clause, "is_non_english", False)
            clause_page = clause.source_page or (idx + 1)

            if is_non_english:
                warnings.append(
                    "Non-English text detected in clause '{}' — structured PII stripped, but named entities may remain.".format(
                        clause.title or "untitled"
                    )
                )

            try:
                entities = self.detect_on_page(
                    combined,
                    threshold=threshold,
                    is_non_english=is_non_english,
                    clause_heading=clause.title or "untitled",
                )

                for entity in entities:
                    if entity.start >= len(overlap_buffer):
                        entity.start -= len(overlap_buffer)
                        entity.end -= len(overlap_buffer)
                        all_entities.append(entity)

                successful_pages.append(clause_page)
            except Exception as exc:
                failed_pages.append(clause_page)
                error_messages[clause_page] = str(exc)

            overlap_buffer = clause.text[-50:] if len(clause.text) >= 50 else clause.text

            if clause_page > current_page:
                current_page = clause_page
                if progress_callback is not None:
                    progress_callback(
                        f"Stripping PII... page {current_page}/{total_pages}",
                        current_page,
                        total_pages,
                    )

        if failed_pages and not allow_partial:
            from openreview_cli.pii.models import PartialProcessingError

            raise PartialProcessingError(
                failed_pages=sorted(set(failed_pages)),
                successful_pages=successful_pages,
                error_messages=error_messages,
            )

        return all_entities, warnings, sorted(set(failed_pages)), error_messages

    def is_available(self) -> bool:
        """Lightweight readiness check — probe the PII engine.

        Attempts analyze("test") once per operation. Caches result in
        _is_available_cache. Returns True if analysis succeeds, False otherwise.
        """
        if self._is_available_cache is not None:
            return self._is_available_cache

        try:
            engine = self._ensure_analyzer()
            engine.analyze(text="test", language="en")
            self._is_available_cache = True
        except Exception as exc:
            logger.warning("PII engine unavailable: %s", exc)
            self._is_available_cache = False
        return self._is_available_cache

    def close(self) -> None:
        self._analyzer = None
        self._is_available_cache = None


def _redact_metadata(document: Any) -> list[Any]:
    """Redact metadata fields from a document."""
    from pathlib import Path

    entities = []
    source_path = Path(document.source_path)
    filename = source_path.name

    metadata_entity = PiiEntity(
        entity_type="FILENAME",
        original_value=filename,
        start=0,
        end=len(filename),
        score=1.0,
        placeholder=_TEMP_PH,
        source="metadata",
    )
    entities.append(metadata_entity)

    for field, entity_type in [("author", "AUTHOR"), ("title", "TITLE"), ("company", "COMPANY")]:
        value = getattr(document, field, None)
        if value:
            entities.append(
                PiiEntity(
                    entity_type=entity_type,
                    original_value=str(value),
                    start=0,
                    end=len(str(value)),
                    score=1.0,
                    placeholder=_TEMP_PH,
                    source="metadata",
                )
            )

    return entities


def strip_pii(
    clauses: list[Any],
    document: Any,
    *,
    threshold: float = 0.7,
    strip_pii_enabled: bool = True,
    strip_metadata: bool = True,
    engine: PiiEngine | None = None,
    allow_partial: bool = False,
    progress_callback: Callable[[str, int, int], None] | None = None,
) -> PiiResult:
    """Strip PII from a list of clauses.

    Returns a PiiResult with the stripped text, mapping, and audit data.
    """
    if not strip_pii_enabled:
        return PiiResult(
            stripped_text=" ".join(c.text for c in clauses),
            mapping={},
            entities=[],
            page_count=len(clauses),
            duration_seconds=0.0,
            warnings=["PII stripping disabled. Contract text may be sent to providers as-is."],
        )

    start_time = time.perf_counter()

    own_engine = engine is None
    if own_engine:
        engine = PiiEngine(threshold=threshold)

    try:
        # Metadata redaction
        metadata_entities = []
        if strip_metadata:
            metadata_entities = _redact_metadata(document)

        # Page-sequential detection
        assert engine is not None
        all_entities, warnings, failed_pages, _error_msgs = engine.detect_all_pages(
            clauses,
            threshold=threshold,
            page_count=getattr(document, "page_count", None),
            allow_partial=allow_partial,
            progress_callback=progress_callback,
        )
        if failed_pages:
            warnings.append(f"PII processing partial: {len(failed_pages)} page(s) failed")

        # Placeholder assignment
        mapping, all_entities_with_placeholders = assign_placeholders(
            all_entities, metadata_entities=metadata_entities
        )

        # Text replacement (longest-first to avoid substring collisions)
        stripped_text = " ".join(c.text for c in clauses)
        sorted_placeholders = sorted(
            mapping.items(),
            key=lambda x: len(x[1]),
            reverse=True,
        )
        for key, original in sorted_placeholders:
            stripped_text = stripped_text.replace(original, f"[{key}]")

        # Ensure every placeholder appears in the stripped text.  Metadata
        # entities (FILENAME, AUTHOR, TITLE, COMPANY) and some custom-recognizer
        # matches may have original values that don't appear verbatim in the
        # clause text (e.g. due to overlap-buffer shifting in detect_all_pages).
        for key in list(mapping):
            placeholder = f"[{key}]"
            if placeholder not in stripped_text:
                stripped_text = stripped_text + f" {placeholder}"

        duration = time.perf_counter() - start_time

        page_count = len(clauses)

        return PiiResult(
            stripped_text=stripped_text,
            mapping=mapping,
            entities=all_entities_with_placeholders,
            page_count=page_count,
            duration_seconds=duration,
            warnings=warnings,
            failed_pages=failed_pages if failed_pages else None,
        )
    finally:
        if own_engine and engine is not None:
            engine.close()


def strip_and_persist(
    clauses: list[Any],
    document: Any,
    review_id: str,
    *,
    threshold: float = 0.7,
    strip_pii_enabled: bool = True,
    encryption_key: str | None = None,
    strip_metadata: bool = True,
) -> PiiResult:
    """Strip PII and persist the mapping + audit to the review directory."""
    from openreview_cli.config.paths import get_review_dir

    if not strip_pii_enabled:
        return strip_pii(
            clauses,
            document,
            threshold=threshold,
            strip_metadata=strip_metadata,
            strip_pii_enabled=False,
        )

    result = strip_pii(clauses, document, threshold=threshold, strip_metadata=strip_metadata)

    if result.mapping:
        review_dir = get_review_dir(review_id)
        write_pii_mapping(result.mapping, review_dir, encryption_key or "")

        non_english_count = sum(1 for e in result.entities if e.source == "regex")

        audit = build_audit(
            entities=result.entities,
            threshold=threshold,
            duration_seconds=result.duration_seconds,
            page_count=result.page_count,
            metadata_fields_redacted=len([e for e in result.entities if e.source == "metadata"]),
            non_english_sections=non_english_count,
        )
        write_pii_audit(audit, review_dir)

    return result


def strip_pii_clauses(
    clauses: list[Any],
    document: Any,
    *,
    threshold: float = 0.7,
    strip_pii_enabled: bool = True,
    strip_metadata: bool = True,
    engine: PiiEngine | None = None,
    allow_partial: bool = False,
    progress_callback: Callable[[str, int, int], None] | None = None,
) -> tuple[list[Any], PiiResult]:
    """Strip PII from each clause's text individually while preserving metadata.

    Returns:
        tuple of (list[Clause] — same clauses with PII-stripped text,
                  PiiResult — unified stripping result across all clauses)
    """
    if not strip_pii_enabled:
        return list(clauses), PiiResult(
            stripped_text=" ".join(c.text for c in clauses),
            mapping={},
            entities=[],
            page_count=max(len(clauses), 1),
            duration_seconds=0.0,
            warnings=["PII stripping disabled. Contract text may be sent to providers as-is."],
        )

    start_time = time.perf_counter()

    own_engine = engine is None
    if own_engine:
        engine = PiiEngine(threshold=threshold)

    try:
        metadata_entities: list[PiiEntity] = []
        if strip_metadata:
            metadata_entities = _redact_metadata(document)

        assert engine is not None
        all_entities, warnings, failed_pages, _error_msgs = engine.detect_all_pages(
            clauses,
            threshold=threshold,
            page_count=getattr(document, "page_count", None),
            allow_partial=allow_partial,
            progress_callback=progress_callback,
        )
        if failed_pages:
            warnings.append(f"PII processing partial: {len(failed_pages)} page(s) failed")

        mapping, all_entities_with_placeholders = assign_placeholders(
            all_entities,
            metadata_entities=metadata_entities,
        )

        sorted_placeholders = sorted(
            mapping.items(),
            key=lambda x: len(x[1]),
            reverse=True,
        )

        stripped_clauses: list[Clause] = []
        for clause in clauses:
            text = clause.text
            for key, original in sorted_placeholders:
                text = text.replace(original, f"[{key}]")
            stripped_clauses.append(
                Clause(
                    id=clause.id,
                    title=clause.title,
                    text=text,
                    level=clause.level,
                    parent_id=clause.parent_id,
                    source_page=clause.source_page,
                    source_paragraph=clause.source_paragraph,
                    source_span=clause.source_span,
                )
            )

        stripped_text = " ".join(c.text for c in stripped_clauses)

        for key in list(mapping):
            placeholder = f"[{key}]"
            if placeholder not in stripped_text:
                stripped_text = stripped_text + f" {placeholder}"
                if stripped_clauses:
                    last = stripped_clauses[-1]
                    stripped_clauses[-1] = Clause(
                        id=last.id,
                        title=last.title,
                        text=last.text + f" {placeholder}",
                        level=last.level,
                        parent_id=last.parent_id,
                        source_page=last.source_page,
                        source_paragraph=last.source_paragraph,
                        source_span=last.source_span,
                    )

        duration = time.perf_counter() - start_time
        page_count = len(clauses) or 1

        result = PiiResult(
            stripped_text=stripped_text,
            mapping=mapping,
            entities=all_entities_with_placeholders,
            page_count=page_count,
            duration_seconds=duration,
            warnings=warnings,
            failed_pages=failed_pages if failed_pages else None,
        )

        return stripped_clauses, result
    finally:
        if own_engine and engine is not None:
            engine.close()


def strip_pii_for_tier(
    text: str,
    tier: str,
    document: Any,
    *,
    strip_metadata: bool = True,
) -> PiiResult:
    """Strip PII from plain text using per-tier score threshold.

    Convenience wrapper that looks up the tier's PII score threshold
    and delegates to *strip_pii*.  Does not change the existing
    *strip_pii* signature.

    Parameters
    ----------
    text : str
        Raw contract text to strip.
    tier : str
        Privacy tier name (``"maximum"``, ``"balanced"``,
        ``"performance"``).
    document : Any
        Document object for metadata redaction.
    strip_metadata : bool, optional
        Whether to redact metadata fields (default ``True``).

    Returns
    -------
    PiiResult
        Stripped text, mapping, entities, and audit data.

    Raises
    ------
    KeyError
        If *tier* is not a recognised privacy tier.
    """
    from openreview_cli.gateway.tier_accuracy import get_target

    target = get_target(tier)
    clause = Clause(
        id="1",
        title="Tier strip",
        text=text,
        level=1,
        parent_id=None,
        source_page=None,
        source_paragraph=0,
        source_span=(0, len(text)),
    )
    return strip_pii(
        [clause],
        document,
        threshold=target.pii_score_threshold,
        strip_metadata=strip_metadata,
    )


__all__ = [
    "PiiEngine",
    "strip_and_persist",
    "strip_pii",
    "strip_pii_clauses",
    "strip_pii_for_tier",
]
