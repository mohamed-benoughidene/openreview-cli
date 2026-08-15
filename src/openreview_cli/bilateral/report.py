"""Report formatting — terminal table + JSON output for bilateral comparison.

Mirrors ``openreview_cli/review/report.py`` patterns.

Public API
----------
format_comparison_terminal : Render a ``ComparisonReport`` as a terminal string.
format_comparison_json    : Serialize a ``ComparisonReport`` as JSON.
compute_summary           : Build a ``ComparisonSummary`` from assessments.
"""

from __future__ import annotations

import dataclasses
import io
import json
from typing import TYPE_CHECKING, Any

from openreview_cli.review.colors import AssessmentColor

if TYPE_CHECKING:
    from openreview_cli.bilateral.models import (
        ComparisonReport,
        ComparisonSummary,
        PairedAssessment,
    )


EXPERIMENTAL_DISCLAIMER = (
    "EXPERIMENTAL: Bilateral comparison is a research-grade feature. "
    "Results are provided for informational purposes only and do not "
    "constitute legal advice. Accuracy is bounded by research "
    "(F1 ≤64% on discrepancy detection). Always verify findings "
    "with qualified legal counsel."
)


def format_comparison_terminal(
    report: ComparisonReport,
    verbose: bool = False,
) -> str:
    """Format a ``ComparisonReport`` as a human-readable terminal string.

    Produces a Rich-styled table with per-pair divergence, confidence,
    color badges, and a roll-up summary section.

    Parameters
    ----------
    report : ComparisonReport
        The comparison report to format.
    verbose : bool
        Show full RCBSF dimensions, alignment_quality, rationale, citations.

    Returns
    -------
    str
        The rendered terminal string.
    """
    # Safety net — ensure colors are assigned for directly-constructed reports
    if report.assessments and report.assessments[0].color is None:
        from openreview_cli.bilateral.colors import assign_paired_colors

        assign_paired_colors(report.assessments, confidence_threshold=report.confidence_threshold)

    from rich.console import Console

    buf = io.StringIO()
    console = Console(width=100, force_terminal=False, file=buf)

    # ── Header disclaimer ──
    console.print()
    console.print("[bold]╔══════════════════════════════════════════════════╗[/bold]")
    console.print("[bold]║  NX-1 BILATERAL COMPARISON — EXPERIMENTAL      ║[/bold]")
    console.print("[bold]║  Comparison accuracy ≤64% F1 ceiling.          ║[/bold]")
    console.print("[bold]║  Do not rely on this tool for legal advice.    ║[/bold]")
    console.print("[bold]╚══════════════════════════════════════════════════╝[/bold]")
    console.print()

    # ── Document info ──
    console.print("[bold]Documents:[/bold]")
    _print_doc_meta(console, "Party A", report.document_a)
    _print_doc_meta(console, "Party B", report.document_b)
    console.print(f"  [dim]Confidence threshold: {report.confidence_threshold}[/dim]")
    console.print()

    if not report.assessments:
        console.print("[yellow]No clause pairs to compare.[/yellow]")
        return buf.getvalue()

    # ── Per-pair table ──
    _print_pairs_table(console, report, verbose)

    # ── Unmatched section ──
    um_a = report.alignment_table.unmatched_a
    um_b = report.alignment_table.unmatched_b
    if um_a or um_b:
        console.print("[bold]Unmatched clauses:[/bold]")
        if um_a:
            ids_a = ", ".join(c.id for c in um_a)
            console.print(f"  [yellow]Party A only:[/yellow] {ids_a}")
        if um_b:
            ids_b = ", ".join(c.id for c in um_b)
            console.print(f"  [yellow]Party B only:[/yellow] {ids_b}")
        console.print()

    # ── Disclaimer footer ──
    console.print("[dim]══════════════════════════════════════════════════[/dim]")
    console.print(f"[dim]{EXPERIMENTAL_DISCLAIMER}[/dim]")
    console.print()

    return buf.getvalue()


def _print_doc_meta(console: Any, label: str, meta: Any) -> None:
    """Print a document metadata line to console."""
    filename = getattr(meta, "filename", "?")
    pages = getattr(meta, "page_count", 0)
    clauses = getattr(meta, "clause_count", 0)
    pii = getattr(meta, "pii_stripped", False)
    pii_str = ", PII stripped" if pii else ", no PII"
    console.print(f"  {label}: [bold]{filename}[/bold] ({pages} pages, {clauses} clauses{pii_str})")


def _print_pairs_table(console: Any, report: Any, verbose: bool) -> None:  # noqa: PLR0912, PLR0915
    """Render the per-pair assessment table."""
    from rich.table import Table

    summary = report.summary
    summary_str = _summary_line(summary)

    table = Table(show_header=True, header_style="bold")
    table.add_column("#", style="dim", width=4)
    table.add_column("Clause", style="cyan", width=28)

    if verbose:
        table.add_column("Party A", width=14)
        table.add_column("Party B", width=14)
        table.add_column("Divergence", width=14)
        table.add_column("Dim", width=12)
        table.add_column("Quality", width=8)
        table.add_column("Conf.", width=8)
        table.add_column("Status", width=8)
    else:
        table.add_column("A Position", width=14)
        table.add_column("B Position", width=14)
        table.add_column("Divergence", width=14)
        table.add_column("Conf.", width=8)
        table.add_column("Status", width=8)

    for i, pa in enumerate(report.assessments, 1):
        heading = pa.alignment.clause_a.title or pa.alignment.clause_b.title or "—"
        heading_display = heading[: min(len(heading), 28)]

        a_pos = _position_badge(pa.party_a_assessment)
        b_pos = _position_badge(pa.party_b_assessment)

        divergence_text = _divergence_text(pa)
        conf_bar = _confidence_display(pa.confidence)
        status = _color_badge(pa.color)

        if verbose:
            dim_text = pa.primary_dimension.value if pa.primary_dimension else "—"
            quality = f"{pa.alignment_quality:.2f}" if pa.alignment_quality is not None else "—"
            table.add_row(
                str(i),
                heading_display,
                a_pos,
                b_pos,
                divergence_text,
                dim_text,
                quality,
                conf_bar,
                status,
            )
        else:
            table.add_row(str(i), heading_display, a_pos, b_pos, divergence_text, conf_bar, status)

    console.print(table)
    console.print()

    # Verbose details: show rationale, citations for each assessment
    if verbose:
        for i, pa in enumerate(report.assessments, 1):
            details: list[str] = []
            if pa.primary_dimension:
                details.append(f"Dimension: {pa.primary_dimension.value}")
            if pa.alignment_quality is not None:
                details.append(f"Quality: {pa.alignment_quality:.2f}")
            if pa.rationale:
                details.append(f"Rationale: {pa.rationale[:200]}")
            if pa.citations:
                for j, c in enumerate(pa.citations, 1):
                    details.append(f"  Citation {j}: {c[:200]}")
            if details:
                console.print(f"  [#{i}] {'; '.join(details)}")
            else:
                console.print(f"  [#{i}] No additional details")
        console.print()

    # ── Summary footer ──
    console.print("[bold]Summary[/bold]")
    console.print(f"  {summary_str}")
    console.print(
        f"  [bold]Amber flags: {summary.amber_count}[/bold]" if summary.amber_count > 0 else ""
    )


def _summary_line(summary: Any) -> str:
    """Build a one-line summary string."""
    parts: list[str] = [
        f"Total pairs: {summary.total_pairs}",
        f"Green: {summary.green_count}",
        f"Amber: {summary.amber_count}",
        f"Red: {summary.red_count}",
    ]
    if hasattr(summary, "agreement_rate"):
        parts.append(f"Agreement rate: {summary.agreement_rate:.0%}")
    if hasattr(summary, "avg_alignment_quality") and summary.avg_alignment_quality > 0:
        parts.append(f"Avg alignment: {summary.avg_alignment_quality:.2f}")
    return " | ".join(parts)


def _position_badge(assessment: Any) -> str:
    """Render a coloured position badge."""
    from openreview_cli.review.models import Position

    pos = assessment.position if hasattr(assessment, "position") else None
    mapping: dict[Position, str] = {
        Position.PREFERRED: "[green]Preferred[/green]",
        Position.ACCEPTABLE: "[yellow]Acceptable[/yellow]",
        Position.WALKAWAY: "[red]Walkaway[/red]",
        Position.UNCERTAIN: "[bold red]Uncertain[/bold red]",
    }
    if pos and isinstance(pos, Position):
        return mapping.get(pos, str(pos.value))
    return str(pos or "—")


def _divergence_text(pa: Any) -> str:
    """Render the divergence column text."""
    if pa.has_divergence:
        return "[red]Divergent[/red]"
    if pa.divergence.value == "uncertain":
        return "[yellow]Uncertain[/yellow]"
    return "[green]Aligned[/green]"


def _confidence_display(confidence: float) -> str:
    """Render a confidence value."""
    filled = int(confidence * 10)
    bar = "█" * filled + "░" * (10 - filled)
    return f"{confidence:.2f} {bar}"


def _color_badge(color: AssessmentColor | None) -> str:
    """Render a three-color status badge."""
    if color is None:
        return "[dim]—[/dim]"
    if color == AssessmentColor.green:
        return "[green]● OK[/green]"
    if color == AssessmentColor.red:
        return "[bold red]● RED[/bold red]"
    return "[bold yellow]⚠ AMBER[/bold yellow]"


# ── JSON output ──


def format_comparison_json(report: ComparisonReport) -> str:
    """Serialize a ComparisonReport as indented JSON.

    Parameters
    ----------
    report : ComparisonReport
        The comparison report to serialize.

    Returns
    -------
    str
        JSON string with indentation.
    """
    # Safety net — ensure colors are assigned
    if report.assessments and report.assessments[0].color is None:
        from openreview_cli.bilateral.colors import assign_paired_colors

        assign_paired_colors(report.assessments, confidence_threshold=report.confidence_threshold)

    data = _report_to_dict(report)
    return json.dumps(data, indent=2, default=str, ensure_ascii=False)


def _report_to_dict(report: ComparisonReport) -> dict[str, Any]:
    """Convert a ComparisonReport to a serialisable dict."""
    data = dataclasses.asdict(report)

    # Build alignment dict
    align = report.alignment_table
    data["alignment"] = {
        "pairs": [dataclasses.asdict(p) for p in align.matched_pairs],
        "unmatched_a_ids": [c.id for c in align.unmatched_a],
        "unmatched_b_ids": [c.id for c in align.unmatched_b],
        "total_a": len(align.matched_pairs) * 2 + len(align.unmatched_a),
        "total_b": len(align.matched_pairs) * 2 + len(align.unmatched_b),
        "alignment_rate": round(align.alignment_rate, 4),
    }

    # Summary dict
    s = report.summary
    data["summary"] = {
        "total_pairs": s.total_pairs,
        "divergences": s.divergent_count,
        "unmatched_a": len(align.unmatched_a),
        "unmatched_b": len(align.unmatched_b),
        "agreement_rate": round(s.agreement_rate, 4),
        "green_count": s.green_count,
        "amber_count": s.amber_count,
        "red_count": s.red_count,
        "avg_alignment_quality": round(s.avg_alignment_quality, 4)
        if s.avg_alignment_quality
        else 0.0,
        "confidence_threshold": report.confidence_threshold,
    }

    return data


# ── Summary computation ──


def compute_summary(assessments: list[PairedAssessment]) -> ComparisonSummary:
    """Compute aggregate statistics from a list of paired assessments.

    Parameters
    ----------
    assessments : list[PairedAssessment]
        The paired assessments to summarise.

    Returns
    -------
    ComparisonSummary
        Aggregate statistics including green/amber/red counts.
    """
    from openreview_cli.bilateral.models import ComparisonSummary, DivergenceVerdict

    total = len(assessments)
    if total == 0:
        return ComparisonSummary()

    divergent_count = 0
    aligned_count = 0
    uncertain_count = 0
    green_count = 0
    amber_count = 0
    red_count = 0
    quality_sum = 0.0

    for pa in assessments:
        if pa.has_divergence:
            divergent_count += 1
        elif pa.divergence == DivergenceVerdict.aligned:
            aligned_count += 1
        elif pa.divergence == DivergenceVerdict.uncertain:
            uncertain_count += 1

        if pa.color == AssessmentColor.green:
            green_count += 1
        elif pa.color == AssessmentColor.amber:
            amber_count += 1
        elif pa.color == AssessmentColor.red:
            red_count += 1

        quality_sum += pa.alignment_quality

    avg_quality = quality_sum / total if total > 0 else 0.0
    agreement_rate = aligned_count / total if total > 0 else 0.0

    return ComparisonSummary(
        divergent_count=divergent_count,
        aligned_count=aligned_count,
        uncertain_count=uncertain_count,
        green_count=green_count,
        amber_count=amber_count,
        red_count=red_count,
        total_pairs=total,
        avg_alignment_quality=round(avg_quality, 4),
        agreement_rate=round(agreement_rate, 4),
    )
