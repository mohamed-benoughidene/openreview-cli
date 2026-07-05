"""Report formatting — terminal table + JSON output."""

from __future__ import annotations

import dataclasses
import io
import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence

from openreview_cli.review.colors import AssessmentColor
from openreview_cli.review.models import Position, ReviewReport


def format_terminal(  # noqa: PLR0912, PLR0915  # ponytail: function extraction would add more complexity
    report: ReviewReport,
    privacy_footer: str | None = None,
) -> str:
    """Format a ``ReviewReport`` as a human-readable terminal string.

    Produces a Rich-styled table with per-clause position badges, confidence
    bars, Amber highlights, and a roll-up summary section.

    Parameters
    ----------
    report : ReviewReport
        The review report to format.
    privacy_footer : str | None
        Optional privacy tier footer line(s) appended at the end.

    Returns the rendered string (no side effects).
    """
    # ponytail: safety net — ensure colors are assigned for directly-constructed reports
    if report.assessments and report.assessments[0].color is None:
        from openreview_cli.review.colors import assign_colors

        assign_colors(report.assessments, threshold=report.confidence_threshold)
    from rich.console import Console
    from rich.table import Table

    buf = io.StringIO()
    console = Console(width=100, force_terminal=False, file=buf)

    # Header
    console.print()
    console.print("[bold]NDA Review Report[/bold]")
    if report.playbook_version is not None:
        console.print(
            f"[dim]Playbook: {report.playbook_id} (version {report.playbook_version})[/dim]"
        )
    else:
        console.print(f"[dim]Playbook: {report.playbook_id}[/dim]")
    console.print()

    # Document metadata
    pii_status = "Yes" if report.document.pii_stripped else "No"
    console.print(
        f"Document: [bold]{report.document.filename}[/bold] "
        f"({report.document.page_count} pages, {report.document.clause_count} clauses)"
    )
    console.print(f"PII stripped: {pii_status}")
    console.print(f"Generated: {report.generated_at.isoformat()}")
    console.print()

    if not report.assessments:
        console.print("[yellow]No clauses to assess.[/yellow]")
        if privacy_footer:
            console.print()
            console.print(privacy_footer)
        return buf.getvalue()

    # Check if grounding data is present
    has_grounding = any(ca.grounding_verdict is not None for ca in report.assessments)

    # Per-clause table
    table = Table(show_header=True, header_style="bold")
    table.add_column("#", style="dim", width=4)
    table.add_column("Clause", style="cyan", width=40)
    table.add_column("Category", width=24)
    table.add_column("Position", width=14)
    table.add_column("Confidence", width=12)
    if has_grounding:
        table.add_column("Gnd", width=6)
    table.add_column("Status", width=10)

    for i, ca in enumerate(report.assessments, 1):
        clause_display = ca.clause_text[:80].replace("\n", " ")
        if len(ca.clause_text) > 80:
            clause_display += "..."

        pos_text = _position_style(ca)
        conf_bar = _confidence_bar(ca.confidence)
        category_display = (
            ca.playbook_category.replace("-", " ").title() if ca.playbook_category else "—"
        )

        if ca.color == AssessmentColor.green:
            status = "[green]● OK[/green]"
        elif ca.color == AssessmentColor.red:
            status = "[bold red]● RED[/bold red]"
        else:
            status = "[bold yellow]⚠ AMBER[/bold yellow]"

        row: list[str] = [str(i), clause_display, category_display, pos_text, conf_bar]
        if has_grounding:
            row.append(_grounding_style(ca))
        row.append(status)
        table.add_row(*row)

    console.print(table)
    console.print()

    # Amber reason details
    amber_details = [
        (idx, ca)
        for idx, ca in enumerate(report.assessments, 1)
        if ca.color == AssessmentColor.amber and ca.amber_reasons
    ]
    if amber_details:
        console.print("[bold]Amber Details[/bold]")
        for a_idx, ca in amber_details:
            reasons = ca.amber_reasons or []
            reason_strs: list[str] = []
            for r in reasons:
                if r == "low_confidence" and ca.effective_confidence is not None:
                    reason_strs.append(f"Low confidence ({ca.effective_confidence:.2f})")
                else:
                    reason_strs.append(str(r).replace("_", " ").title())
            console.print(f"  #{a_idx}: {', '.join(reason_strs)}")
        console.print()

    # Summary
    summary = report.summary
    console.print("[bold]Summary[/bold]")
    console.print(f"  Green:       {summary.green_count}")
    console.print(f"  Amber:       {summary.amber_count}")
    console.print(f"  Red:         {summary.red_count}")
    console.print(f"  Preferred:   {summary.preferred_count}")
    console.print(f"  Acceptable:  {summary.acceptable_count}")
    console.print(f"  Walkaway:    {summary.walkaway_count}")
    console.print(f"  Uncertain:   {summary.uncertain_count}")
    console.print(f"  No-match:    {summary.no_match_count}")
    console.print()
    console.print(f"[bold]  Amber flags:  {summary.amber_count}[/bold]")
    console.print(
        f"  Avg confidence: {summary.avg_confidence:.2f}"
        if summary.avg_confidence
        else "  Avg confidence: —"
    )
    console.print(f"  Avg effective confidence: {summary.avg_effective_confidence:.2f}")
    console.print(f"  Confidence threshold: {report.confidence_threshold}")
    if has_grounding:
        _print_grounding_summary(report, console)
    console.print()

    # Privacy tier footer (FR-08, SC-05)
    if privacy_footer:
        console.print(privacy_footer)
        console.print()

    return buf.getvalue()


def _grounding_style(ca: Any) -> str:
    """Return a styled grounding verdict for terminal output."""
    from openreview_cli.grounding.models import GroundingVerdict

    if ca.grounding_verdict is None:
        return "[dim]—[/dim]"
    if ca.grounding_verdict == GroundingVerdict.GROUNDED:
        return "[green]G[/green]"
    if ca.grounding_verdict == GroundingVerdict.UNGROUNDED:
        return "[red]U[/red]"
    return "[yellow]?[/yellow]"


def _print_grounding_summary(report: Any, console: Any) -> None:
    """Print grounding summary line to console."""
    from openreview_cli.grounding.models import GroundingVerdict

    grounded = sum(
        1 for ca in report.assessments if ca.grounding_verdict == GroundingVerdict.GROUNDED
    )
    ungrounded = sum(
        1 for ca in report.assessments if ca.grounding_verdict == GroundingVerdict.UNGROUNDED
    )
    uncertain = sum(
        1 for ca in report.assessments if ca.grounding_verdict == GroundingVerdict.UNCERTAIN
    )
    not_processed = sum(1 for ca in report.assessments if ca.grounding_verdict is None)

    parts: list[str] = []
    parts.append(f"[green]{grounded} grounded[/green]")
    if ungrounded:
        parts.append(f"[red]{ungrounded} ungrounded[/red]")
    if uncertain:
        parts.append(f"[yellow]{uncertain} uncertain[/yellow]")
    if not_processed:
        parts.append(f"[dim]{not_processed} not processed[/dim]")
    console.print(f"  Grounding: {', '.join(parts)}")


def _position_style(ca: Any) -> str:
    """Return a styled position string for terminal output."""
    mapping: dict[Position, str] = {
        Position.PREFERRED: "[green]Preferred[/green]",
        Position.ACCEPTABLE: "[yellow]Acceptable[/yellow]",
        Position.WALKAWAY: "[red]Walkaway[/red]",
        Position.UNCERTAIN: "[bold red]Uncertain[/bold red]",
    }
    return mapping.get(ca.position, str(ca.position.value))


def _confidence_bar(confidence: float) -> str:
    """Render a simple confidence bar."""
    filled = int(confidence * 10)
    bar = "█" * filled + "░" * (10 - filled)
    return f"{confidence:.2f} {bar}"


def format_json(reports: ReviewReport | Sequence[ReviewReport]) -> str:
    """Format one or more ReviewReports as JSON.

    Parameters
    ----------
    reports : ReviewReport | Sequence[ReviewReport]
        Single report or list of reports (for batch mode).

    Returns
    -------
    str
        JSON string with indentation.
    """
    if isinstance(reports, ReviewReport):
        # ponytail: safety net — ensure colors are assigned for directly-constructed reports
        if reports.assessments and reports.assessments[0].color is None:
            from openreview_cli.review.colors import assign_colors

            assign_colors(reports.assessments, threshold=reports.confidence_threshold)
        data: dict[str, Any] | list[dict[str, Any]] = _report_to_dict(reports)
    else:
        for r in reports:
            if r.assessments and r.assessments[0].color is None:
                from openreview_cli.review.colors import assign_colors

                assign_colors(r.assessments, threshold=r.confidence_threshold)
        data = [_report_to_dict(r) for r in reports]
    return json.dumps(data, indent=2, default=str, ensure_ascii=False)


def _report_to_dict(report: ReviewReport) -> dict[str, Any]:
    """Convert a ReviewReport to a serialisable dict using dataclasses.asdict().

    ``asdict`` handles nested dataclasses recursively. ``json.dumps(default=str)``
    in ``format_json`` handles ``datetime`` and ``StrEnum`` serialisation.

    ``is_amber`` is a ``@property`` on ``ClauseAssessment`` (not a dataclass field),
    so it is not included by ``asdict`` — we add it manually from the live objects.
    """
    data = dataclasses.asdict(report)
    # Restore is_amber from the @property (asdict uses _is_amber field instead)
    for assessment, a_dict in zip(report.assessments, data.get("assessments", []), strict=True):
        a_dict.pop("_is_amber", None)
        a_dict["is_amber"] = assessment.is_amber
    return data
