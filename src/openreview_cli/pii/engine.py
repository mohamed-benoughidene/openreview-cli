"""PII stripping engine — Presidio wrapper with page-sequential processing."""

import time
from typing import Any

from openreview_cli.pii.audit import build_audit, write_pii_audit
from openreview_cli.pii.mapping import write_pii_mapping
from openreview_cli.pii.models import PiiEntity, PiiError, PiiResult
from openreview_cli.pii.placeholders import assign_placeholders
from openreview_cli.pii.recognizers import CUSTOM_RECOGNIZERS

_TEMP_PH = "[TEMP_0]"  # ponytail: placeholder overwritten by assign_placeholders


class PiiEngine:
    """PII detection and stripping engine wrapping Presidio analyzer + anonymizer."""

    def __init__(self, threshold: float = 0.7):
        self._threshold = threshold
        self._analyzer: Any = None

    def _ensure_analyzer(self) -> Any:
        if self._analyzer is not None:
            return self._analyzer

        from presidio_analyzer import AnalyzerEngine
        from presidio_analyzer.nlp_engine import SpacyNlpEngine

        try:
            model_config = [{"lang_code": "en", "model_name": "en_core_web_lg"}]
            nlp_engine = SpacyNlpEngine(models=model_config)
            self._analyzer = AnalyzerEngine(nlp_engine=nlp_engine)
        except OSError as err:
            raise PiiError(
                exit_code=9,
                category="model_not_found",
                clause_heading=None,
                phase=None,
                message="PII detection model not found. Run: python -m spacy download en_core_web_lg",
                action="python -m spacy download en_core_web_lg",
            ) from err

        for recognizer in CUSTOM_RECOGNIZERS:
            self._analyzer.registry.add_recognizer(recognizer)

        return self._analyzer

    def detect_on_page(
        self, text: str, threshold: float | None = None, is_non_english: bool = False, clause_heading: str | None = None
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
        self, clauses: list[Any], threshold: float | None = None, page_count: int | None = None
    ) -> tuple[list[Any], list[Any]]:
        threshold = threshold if threshold is not None else self._threshold
        all_entities: list[Any] = []
        warnings: list[Any] = []

        from rich.progress import BarColumn, Progress, TextColumn

        sorted_clauses = sorted(
            clauses,
            key=lambda c: (
                c.source_page or 0,
                c.source_paragraph or 0,
            )
            if hasattr(c, "source_page")
            else 0,
        )

        total_pages = page_count or max((c.source_page or 1 for c in sorted_clauses), default=1)

        overlap_buffer = ""
        with Progress(
            TextColumn("[bold]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total} pages"),
            transient=True,
        ) as progress:
            task = progress.add_task("Stripping PII...", total=total_pages)

            current_page = 0
            for idx, clause in enumerate(sorted_clauses):
                combined = overlap_buffer + clause.text
                is_non_english = getattr(clause, "is_non_english", False)

                if is_non_english:
                    warnings.append(
                        "Non-English text detected in clause '{}' — structured PII stripped, but named entities may remain.".format(
                            clause.title or "untitled"
                        )
                    )

                entities = self.detect_on_page(
                    combined, threshold=threshold, is_non_english=is_non_english,
                    clause_heading=clause.title or "untitled",
                )

                # Filter out entities that fall entirely within the overlap region
                for entity in entities:
                    if entity.start >= len(overlap_buffer):
                        entity.start -= len(overlap_buffer)
                        entity.end -= len(overlap_buffer)
                        all_entities.append(entity)

                overlap_buffer = (
                    clause.text[-50:] if len(clause.text) >= 50 else clause.text
                )

                clause_page = clause.source_page or (idx + 1)
                if clause_page > current_page:
                    current_page = clause_page
                    progress.update(task, completed=current_page - 1)
                    progress.update(
                        task,
                        description=f"Stripping PII... page {current_page}/{total_pages}",
                    )
                    progress.advance(task)

        return all_entities, warnings

    def close(self) -> None:
        self._analyzer = None


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
        all_entities, warnings = engine.detect_all_pages(
            clauses, threshold=threshold, page_count=getattr(document, "page_count", None)
        )

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

        duration = time.perf_counter() - start_time

        page_count = len(clauses)

        return PiiResult(
            stripped_text=stripped_text,
            mapping=mapping,
            entities=all_entities_with_placeholders,
            page_count=page_count,
            duration_seconds=duration,
            warnings=warnings,
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
            clauses, document, threshold=threshold, strip_metadata=strip_metadata, strip_pii_enabled=False
        )

    result = strip_pii(
        clauses, document, threshold=threshold, strip_metadata=strip_metadata
    )

    if result.mapping:
        review_dir = get_review_dir(review_id)
        write_pii_mapping(result.mapping, review_dir, encryption_key or "")

        non_english_count = sum(
            1 for e in result.entities if e.source == "regex"
        )

        audit = build_audit(
            entities=result.entities,
            threshold=threshold,
            duration_seconds=result.duration_seconds,
            page_count=result.page_count,
            metadata_fields_redacted=len(
                [e for e in result.entities if e.source == "metadata"]
            ),
            non_english_sections=non_english_count,
        )
        write_pii_audit(audit, review_dir)

    return result


__all__ = ["PiiEngine", "strip_and_persist", "strip_pii"]
