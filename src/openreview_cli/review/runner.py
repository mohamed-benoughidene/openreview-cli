"""Review orchestration runner — extracted from __init__.py to reduce module size."""

from __future__ import annotations

import asyncio
import logging
import sys
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence

    from openreview_cli.pipeline.progress import ProgressEvent

from openreview_cli.pipeline.adapters.parse import ParseStage
from openreview_cli.pipeline.adapters.strip import StripStage
from openreview_cli.pipeline.runner import Pipeline
from openreview_cli.review.models import ReviewReport
from openreview_cli.review.playbook import load_bundled, load_playbook, load_playbook_from_db

logger = logging.getLogger(__name__)


def run_review(  # noqa: PLR0912
    paths: Sequence[str],
    playbook_path: str | None = None,
    playbook_id: str | None = None,
    extraction_model: str = "extraction",
    qa_model: str | None = None,
    no_pii: bool = False,
    verbose: bool = False,
    grounding_mode: str | None = None,
    confidence_threshold: float = 0.7,
    mode_threshold_overrides: dict[str, float] | None = None,
    mode: str = "precheck",
    dual_path: bool = False,
    session_id: str | None = None,
    allow_partial_pii: bool = False,
) -> list[ReviewReport]:
    """Run the PAKTON 3-agent review pipeline on one or more documents.

    Internally delegates to the :mod:`~openreview_cli.pipeline` framework
    with ``ParseStage``, ``StripStage`` (unless ``no_pii``), and
    ``ReviewStage`` stages.

    Parameters
    ----------
    paths : Sequence[str]
        One or more document file paths (.pdf, .docx). Glob expansion
        is handled by the CLI shell.
    playbook_path : str | None
        Path to a custom YAML playbook. ``None`` uses the bundled NDA playbook.
    playbook_id : str | None
        Playbook ID to load from database. Takes precedence over playbook_path.
    extraction_model : str
        Model slot name for the extraction agent.
    qa_model : str | None
        Model slot name for the QA verification agent. ``None`` uses the
        same slot as extraction.
    no_pii : bool
        Skip PII stripping when ``True``.
    verbose : bool
        Print per-clause progress to stderr when ``True``.
    grounding_mode : str | None
        Grounding mode: ``"strict"``, ``"lenient"``, or ``None`` to skip.
    confidence_threshold : float
        Threshold for Green/Amber/Red assignment (0.0-1.0). Default 0.7.
    mode_threshold_overrides : dict[str, float] | None
        Per-mode confidence threshold overrides, e.g. ``{"leasecheck": 0.85}``.
        When the current mode has an override, it takes precedence over
        *confidence_threshold*.
    dual_path : bool
        When ``True``, use dual-path execution: call providers in parallel
        and return first success.  Default ``False`` (sequential).
    session_id : str | None
        Optional caller-provided session identifier for cost attribution.
        When a single document is processed, this ID is used directly.
        When ``None`` or multiple documents, a unique ``review:<uuid>`` ID
        is minted per document.  All extraction, QA, and grounding calls
        for the same document share the same ID.

    Returns
    -------
    list[ReviewReport]
        One report per document, in input order.
    """
    if qa_model is None:
        qa_model = extraction_model

    # Load playbook with precedence: DB id > file path > bundled
    playbook_version: int | None = None
    if playbook_id and playbook_path:
        import warnings

        warnings.warn(
            "Both --playbook and --playbook-path provided. "
            "--playbook (database) takes precedence; --playbook-path is ignored.",
            UserWarning,
            stacklevel=2,
        )
    if playbook_id:
        playbook, playbook_version = load_playbook_from_db(playbook_id)
    elif playbook_path:
        playbook = load_playbook(Path(playbook_path))
    else:
        playbook = load_bundled()

    reports: list[ReviewReport] = []

    n_paths = len(paths)
    for path_str in paths:
        doc_path = Path(path_str)
        if not doc_path.exists():
            logger.warning("Document not found, skipping: %s", doc_path)
            continue

        if verbose:
            print(f"Processing: {doc_path.name}", file=sys.stderr)

        # Mint or reuse session ID — caller-provided ID used only for a
        # single-doc invocation; multi-doc always mints per document.
        doc_session_id: str
        if session_id is not None and n_paths == 1:
            doc_session_id = session_id
        else:
            doc_session_id = f"review:{uuid.uuid4()}"
            logger.info("Minted session ID %s for %s", doc_session_id, doc_path.name)

        try:
            result = _run_review_doc_pipeline(
                doc_path=doc_path,
                playbook=playbook,
                playbook_version=playbook_version,
                extraction_model=extraction_model,
                qa_model=qa_model,
                no_pii=no_pii,
                verbose=verbose,
                confidence_threshold=confidence_threshold,
                mode_threshold_overrides=mode_threshold_overrides,
                mode=mode,
                session_id=doc_session_id,
                allow_partial_pii=allow_partial_pii,
            )
        except Exception as exc:
            logger.warning("Failed to process %s: %s", doc_path, exc)
            if verbose:
                print(f"  Error: {exc}", file=sys.stderr)
            continue

        if result is None:
            continue

        report, clauses = result

        # Citation Grounding (optional, post-pipeline) — uses the original
        # clauses preserved from ParseStage for accurate clause-text-aware
        # grounding metrics.
        if grounding_mode is not None and report.assessments:
            try:
                from openreview_cli.grounding import run_grounding

                grounding_result = run_grounding(
                    report,
                    report.document,  # type: ignore[arg-type]  # DocMeta matches Document subset
                    mode=grounding_mode,  # type: ignore[arg-type]  # validated as 'strict'/'lenient' above
                    source_clauses=clauses,
                    session_id=doc_session_id,
                )
                grounding_result.merge_into(report)
                logger.info(
                    "Grounding: %d/%d grounded (%s mode)",
                    grounding_result.grounded_count,
                    grounding_result.total_claims,
                    grounding_mode,
                )
            except Exception:
                logger.warning("Citation grounding failed, skipping", exc_info=True)
                if verbose:
                    print(
                        "  Warning: citation grounding skipped due to error",
                        file=sys.stderr,
                    )

        reports.append(report)

    return reports


def _run_review_doc_pipeline(
    doc_path: str | Path,
    playbook: Any,
    playbook_version: int | None,
    extraction_model: str,
    qa_model: str,
    no_pii: bool,
    verbose: bool,
    confidence_threshold: float,
    mode_threshold_overrides: dict[str, float] | None = None,
    mode: str = "precheck",
    session_id: str | None = None,
    allow_partial_pii: bool = False,
) -> tuple[ReviewReport, list[Any]] | None:
    """Run a pipeline for a single document using the pipeline framework.

    Composes ``ParseStage``, optional ``StripStage``, and ``ReviewStage``
    to produce a ``ReviewReport``.  The report is extracted from
    ``ReviewStage.report`` after pipeline execution completes.

    Returns ``(report, clauses)`` where *clauses* are the parsed source
    clauses (used for downstream grounding).

    Parameters
    ----------
    session_id:
        Optional session identifier for cost attribution.  Passed through
        to the review stage so all extraction and QA calls for this
        document share the same ID.
    """
    from openreview_cli.review.pipeline import ReviewStage

    review_stage = ReviewStage(
        playbook=playbook,
        extraction_model=extraction_model,
        qa_model=qa_model,
        confidence_threshold=confidence_threshold,
        mode_threshold_overrides=mode_threshold_overrides,
        playbook_version=playbook_version,
        verbose=verbose,
        mode=mode,
        session_id=session_id,
    )

    stages: list[Any] = [ParseStage()]
    if not no_pii:
        stages.append(StripStage(no_pii=False, allow_partial=allow_partial_pii))
    stages.append(review_stage)

    def _progress(event: ProgressEvent) -> None:
        if verbose:
            print(
                f"[{event.stage_index + 1}/{event.total_stages}] {event.stage_name}..."
                if event.status == "running"
                else f"[{event.stage_index + 1}/{event.total_stages}] "
                f"{event.stage_name} {event.status}",
                file=sys.stderr,
            )

    pipeline = Pipeline(stages=stages, progress_callback=_progress)

    pipeline_ctx: dict[str, Any] = {"document_path": str(doc_path)}
    try:
        asyncio.run(pipeline.run(pipeline_ctx))
    except Exception:
        logger.exception("Pipeline failed for %s", doc_path)
        return None

    if review_stage.report is None:
        return None

    # ponytail: read source_clauses from pipeline context (survives stage.cleanup
    # which sets review_stage.clauses to None after merge into context)
    source_clauses: list[Any] = pipeline_ctx.get("source_clauses", [])
    return review_stage.report, source_clauses
