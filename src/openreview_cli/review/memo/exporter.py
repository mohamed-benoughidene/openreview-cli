"""MemoExporter — orchestrates conversion of ReviewReport to formatted memo files."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from openreview_cli.review.memo.filename import (
    deduplicate,
    generate_filename,
    resolve_output_dir,
)
from openreview_cli.review.memo.formats import (
    DISCLAIMER_TEXT,
    render_docx,
    render_json,
    render_markdown,
)
from openreview_cli.review.memo.models import (
    MemoCitation,
    MemoClause,
    MemoFormat,
    MemoReport,
    MemoSummary,
)

if TYPE_CHECKING:
    from openreview_cli.review.models import ReviewReport

logger = logging.getLogger(__name__)


@dataclass
class MemoExporter:
    """Orchestrator for exporting a ``ReviewReport`` to formatted memo files.

    Usage::

        exporter = MemoExporter(report=report, mode="precheck")
        paths = exporter.export()  # returns dict[MemoFormat, Path]
    """

    _RENDERERS: ClassVar[dict[MemoFormat, Any]] = {
        MemoFormat.MARKDOWN: render_markdown,
        MemoFormat.JSON: render_json,
        MemoFormat.DOCX: render_docx,
    }

    report: ReviewReport
    mode: str
    output_dir: Path = Path("review_results")
    formats: set[MemoFormat] = field(default_factory=lambda: {MemoFormat.MARKDOWN})

    def export(self) -> dict[MemoFormat, Path]:
        """Export the memo in all requested formats.

        Returns
        -------
        dict[MemoFormat, Path]
            Mapping of each format to its output file path.

        Raises
        ------
        ValueError
            If the review has no assessments.
        """
        memo = self._build_memo_report()
        output_dir = resolve_output_dir(self.output_dir)
        results: dict[MemoFormat, Path] = {}

        for fmt in self.formats:
            try:
                render_fn = self._RENDERERS.get(fmt)
                if render_fn is None:
                    logger.warning("Unsupported format: %s — skipping", fmt)
                    continue
                result = render_fn(memo)
                if isinstance(result, str):
                    path = self._write_memo(result, fmt, output_dir)
                else:
                    filename = generate_filename(self.mode, self._document_stem(), fmt)
                    path = deduplicate(output_dir / filename)
                    result.save(str(path))

                results[fmt] = path
                logger.info("Memo exported: %s", path)

            except Exception:
                logger.exception("Failed to export %s format", fmt.value)

        return results

    def _build_memo_report(self) -> MemoReport:
        """Convert the internal ``ReviewReport`` to a ``MemoReport``."""
        assessments = self.report.assessments
        if not assessments:
            raise ValueError("No review results to export. The review did not complete.")

        clauses: list[MemoClause] = []
        for ca in assessments:
            citation = self._build_citation(ca)
            pos_val = ca.position.value if hasattr(ca.position, "value") else ca.position
            clauses.append(
                MemoClause(
                    id=ca.clause_id,
                    title=ca.playbook_category,
                    playbook_requirement=str(pos_val),
                    contract_text=ca.clause_text,
                    assessment="match"
                    if str(pos_val) in ("preferred", "acceptable")
                    else "difference",
                    color=str(ca.color) if ca.color else "amber",
                    confidence=ca.effective_confidence or ca.confidence,
                    citation=citation,
                )
            )

        summary = self.report.summary
        green_count = getattr(summary, "green_count", 0)
        red_count = getattr(summary, "red_count", 0)
        total = len(assessments)
        matches = green_count
        differences = total - green_count if total > 0 else 0

        # Recommendation logic
        recommendation = self._compute_recommendation(red_count, matches, total)

        memo_summary = MemoSummary(
            recommendation=recommendation,
            clauses_checked=total,
            matches=matches,
            differences=differences,
            confidence_avg=getattr(summary, "avg_confidence", 0.0),
            citation_relevance=self.report.cg_metrics.citation_relevance
            if self.report.cg_metrics
            else None,
            citation_locality=self.report.cg_metrics.citation_locality
            if self.report.cg_metrics
            else None,
        )

        return MemoReport(
            memo_version="1.0",
            mode=self.mode,
            document_name=self.report.document.filename,
            playbook_name=self.report.playbook_id,
            playbook_version=str(self.report.playbook_version or ""),
            review_date=datetime.now(UTC).isoformat(),
            overall=memo_summary,
            clauses=clauses,
            disclaimer=DISCLAIMER_TEXT,
        )

    def _compute_recommendation(self, red_count: int, matches: int, total: int) -> str:
        """Determine overall recommendation from assessment counts."""
        if red_count > 0:
            return "reject"
        if total > 0 and matches / total >= 0.95:
            return "approve"
        return "revise"

    def _build_citation(self, ca: Any) -> MemoCitation | None:
        """Extract a MemoCitation from a ClauseAssessment, if available."""
        provenances = getattr(ca, "grounding_provenances", None)
        if provenances:
            first = provenances[0]
            return MemoCitation(clause_id=first.clause_id, paragraph_index=first.paragraph_index)
        citation_str = getattr(ca, "citation", "") or ""
        if not citation_str:
            return None
        return MemoCitation(clause_id=citation_str, paragraph_index=0)

    def _document_stem(self) -> str:
        """Get the sanitised document stem from the report."""
        try:
            filename = self.report.document.filename
            return Path(filename).stem
        except Exception:
            return "document"

    def _write_memo(self, content: str, fmt: MemoFormat, output_dir: Path) -> Path:
        """Write a text-format memo (Markdown or JSON) to disk."""
        filename = generate_filename(self.mode, self._document_stem(), fmt)
        path = deduplicate(output_dir / filename)
        path.write_text(content, encoding="utf-8")
        return path
