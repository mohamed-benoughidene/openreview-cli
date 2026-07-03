"""Report formatting — terminal table + JSON output."""

from __future__ import annotations

import dataclasses
import io
import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence

from openreview_cli.review.models import Position, ReviewReport


def format_terminal(report: ReviewReport) -> str:  # noqa: PLR0915  # ponytail: function extraction would add more complexity
    """Format a ``ReviewReport`` as a human-readable terminal string.

    Produces a Rich-styled table with per-clause position badges, confidence
    bars, Amber highlights, and a roll-up summary section.

    Returns the rendered string (no side effects).
    """
    from rich.console import Console
    from rich.table import Table

    buf = io.StringIO()
    console = Console(width=100, force_terminal=False, file=buf)

    # Header
    console.print()
    console.print("[bold]NDA Review Report[/bold]")
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
    table.add_column("Status", width=8)

    for i, ca in enumerate(report.assessments, 1):
        clause_display = ca.clause_text[:80].replace("\n", " ")
        if len(ca.clause_text) > 80:
            clause_display += "..."

        pos_text = _position_style(ca)
        conf_bar = _confidence_bar(ca.confidence)
        status = "[bold red]⚠ AMBER[/bold red]" if ca.is_amber else "[dim]OK[/dim]"
        category_display = (
            ca.playbook_category.replace("-", " ").title() if ca.playbook_category else "—"
        )

        row: list[str] = [str(i), clause_display, category_display, pos_text, conf_bar]
        if has_grounding:
            row.append(_grounding_style(ca))
        row.append(status)
        table.add_row(*row)

    console.print(table)
    console.print()

    # Summary
    summary = report.summary
    console.print("[bold]Summary[/bold]")
    console.print(f"  Favorable:   {summary.favorable_count}")
    console.print(f"  Neutral:     {summary.neutral_count}")
    console.print(f"  Unfavorable: {summary.unfavorable_count}")
    console.print(f"  Uncertain:   {summary.uncertain_count}")
    console.print(f"  No-match:    {summary.no_match_count}")
    console.print()
    console.print(f"[bold]  Amber flags:  {summary.amber_count}[/bold]")
    console.print(
        f"  Avg confidence: {summary.avg_confidence:.2f}"
        if summary.avg_confidence
        else "  Avg confidence: —"
    )
    if has_grounding:
        _print_grounding_summary(report, console)
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
        Position.favorable: "[green]Favorable[/green]",
        Position.neutral: "[yellow]Neutral[/yellow]",
        Position.unfavorable: "[red]Unfavorable[/red]",
        Position.uncertain: "[bold red]Uncertain[/bold red]",
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
        data: dict[str, Any] | list[dict[str, Any]] = _report_to_dict(reports)
    else:
        data = [_report_to_dict(r) for r in reports]
    return json.dumps(data, indent=2, default=str, ensure_ascii=False)


def _report_to_dict(report: ReviewReport) -> dict[str, Any]:
    """Convert a ReviewReport to a serialisable dict using dataclasses.asdict().

    ``asdict`` handles nested dataclasses recursively. ``json.dumps(default=str)``
    in ``format_json`` handles ``datetime`` and ``StrEnum`` serialisation.
    """
    return dataclasses.asdict(report)
