"""Report formatting — terminal table + JSON output for negotiation reports."""

from __future__ import annotations

import dataclasses
import io
import json
from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

if TYPE_CHECKING:
    from openreview_cli.negotiation.models import NegotiationReport


def format_terminal(report: NegotiationReport) -> str:
    """Format a NegotiationReport as a human-readable terminal string.

    Uses Rich tables to display per-clause equilibrium strategies,
    payoff summaries, Amber annotations, and aggregate statistics.

    Parameters
    ----------
    report : NegotiationReport
        The negotiation report to format.

    Returns
    -------
    str
        Rendered terminal string.
    """
    buf = io.StringIO()
    console = Console(width=100, force_terminal=False, file=buf)

    _render_disclaimer(console)
    _render_metadata(console, report)

    if not report.strategies:
        console.print("[yellow]No clauses to analyse.[/yellow]")
        return buf.getvalue()

    _render_strategy_table(console, report)
    _render_payoff_summary(console, report)
    _render_cross_reference(console, report)
    _render_amber_details(console, report)
    _render_summary(console, report)

    console.print()
    console.print("[dim]This analysis is advisory only and does not constitute legal advice.[/dim]")
    console.print()

    return buf.getvalue()


def _render_disclaimer(console: Console) -> None:
    """Print the experimental disclaimer header."""
    console.print()
    console.print(
        Panel(
            "[bold yellow]EXPERIMENTAL and advisory only.[/bold yellow] "
            "This analysis uses game-theoretic models with bounded-rationality "
            "approximations. Review with qualified legal counsel before acting "
            "on any recommendation.",
            border_style="yellow",
        )
    )
    console.print()


def _render_metadata(console: Console, report: NegotiationReport) -> None:
    """Print report metadata and header."""
    console.print("[bold]Negotiation Analysis Report[/bold]")
    console.print(f"[dim]Playbook: {report.playbook_id}[/dim]")
    console.print(f"[dim]Generated: {report.generated_at.isoformat()}[/dim]")
    console.print(f"[dim]Confidence threshold: {report.confidence_threshold}[/dim]")
    console.print()


def _render_strategy_table(console: Console, report: NegotiationReport) -> None:
    """Render the per-clause strategy table."""
    table = Table(show_header=True, header_style="bold")
    table.add_column("#", style="dim", width=4)
    table.add_column("Clause", style="cyan", width=24)
    table.add_column("Counteroffer", width=40)
    table.add_column("Equilibrium", width=14)
    table.add_column("Confidence", width=12)
    table.add_column("Status", width=12)

    for i, strategy in enumerate(report.strategies, 1):
        clause_display = strategy.clause_id[:24]
        conf_bar = _confidence_bar(strategy.confidence)

        status: str
        if strategy.is_amber:
            status = "[bold yellow]⚠ AMBER[/bold yellow]"
        elif strategy.confidence >= report.confidence_threshold:
            status = "[green]● OK[/green]"
        else:
            status = "[yellow]⚠ Caution[/yellow]"

        table.add_row(
            str(i),
            clause_display,
            strategy.suggested_counteroffer[:38],
            strategy.equilibrium_type,
            conf_bar,
            status,
        )

    console.print(table)
    console.print()


def _render_payoff_summary(console: Console, report: NegotiationReport) -> None:
    """Render per-clause payoff matrix summary."""
    console.print("[bold]Payoff Summary[/bold]")
    console.print()

    for i, (strategy, pm) in enumerate(
        zip(report.strategies, report.payoff_matrices, strict=False), 1
    ):
        user_row = pm.user_payoffs
        cp_row = pm.counterparty_payoffs

        payoff_table = Table(show_header=True, header_style="dim", box=None)
        payoff_table.add_column("", width=4)
        payoff_table.add_column("Action", width=14)
        payoff_table.add_column("User Payoff", width=14)
        payoff_table.add_column("Counterparty Payoff", width=20)

        for j, action in enumerate(pm.actions):
            u_val = user_row[j][j]
            c_val = cp_row[j][j]
            payoff_table.add_row(
                f"{i}.{j + 1}",
                action,
                f"{u_val:.2f}",
                f"{c_val:.2f}",
            )

        console.print(f"[cyan]{i}.[/cyan] [bold]{strategy.clause_id}[/bold]")
        console.print(payoff_table)
        console.print()


def _render_cross_reference(console: Console, report: NegotiationReport) -> None:
    """Render cross-reference section for alignment divergence."""
    cross_ref_strategies = [
        (idx, s) for idx, s in enumerate(report.strategies, 1) if s.diverges_from_alignment
    ]
    if not cross_ref_strategies:
        return

    console.print("[bold]Cross-Reference: Bilateral Alignment Divergence[/bold]")
    console.print(
        "[dim]Where equilibrium analysis suggests a different approach "
        "than bilateral alignment data.[/dim]"
    )
    console.print()
    cross_table = Table(show_header=True, header_style="bold")
    cross_table.add_column("#", style="dim", width=4)
    cross_table.add_column("Clause", style="cyan", width=24)
    cross_table.add_column("Note", width=60)
    for c_idx, c_strat in cross_ref_strategies:
        cross_table.add_row(
            str(c_idx),
            c_strat.clause_id,
            c_strat.cross_reference_note,
        )
    console.print(cross_table)
    console.print()


def _render_amber_details(console: Console, report: NegotiationReport) -> None:
    """Render detailed amber-flagged strategy info."""
    amber_strategies = [(idx, s) for idx, s in enumerate(report.strategies, 1) if s.is_amber]
    if not amber_strategies:
        return

    console.print("[bold]Amber Details[/bold]")
    for a_idx, strategy in amber_strategies:
        console.print(f"  #{a_idx}: {strategy.clause_id}")
        console.print(
            f"        Confidence: {strategy.confidence:.2f} "
            f"(threshold: {report.confidence_threshold})"
        )
        if strategy.assumptions:
            for assump in strategy.assumptions:
                console.print(f"        • {assump}")
    console.print()


def _render_summary(console: Console, report: NegotiationReport) -> None:
    """Render aggregate summary statistics."""
    summary = report.summary
    console.print("[bold]Summary[/bold]")
    console.print(f"  Total clauses analysed:  {summary.total_clauses}")
    console.print(f"  Amber flags:             {summary.amber_count}")
    console.print(f"  Impasse count:           {summary.impasse_count}")
    console.print(f"  Deadlock risk:           {'YES' if summary.deadlock_risk else 'No'}")
    console.print(f"  Avg confidence:          {summary.avg_confidence:.2f}")

    eq_dist = summary.equilibrium_distribution
    if eq_dist:
        console.print()
        console.print("[bold]Equilibrium Distribution[/bold]")
        for eq_type, count in sorted(eq_dist.items()):
            console.print(f"  {eq_type}: {count}")


def format_json(report: NegotiationReport) -> str:
    """Format a NegotiationReport as JSON.

    Parameters
    ----------
    report : NegotiationReport
        The report to serialise.

    Returns
    -------
    str
        Pretty-printed JSON string.
    """
    data = dataclasses.asdict(report)
    return json.dumps(data, indent=2, default=str, ensure_ascii=False)


def format_memo(report: NegotiationReport) -> str:
    """Format a plain-text memo summary.

    Parameters
    ----------
    report : NegotiationReport
        The report to format.

    Returns
    -------
    str
        Plain-text memo.
    """
    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("NEGOTIATION ANALYSIS MEMO")
    lines.append("=" * 60)
    lines.append("")
    lines.append("EXPERIMENTAL and advisory only. Review with qualified legal counsel.")
    lines.append("")
    lines.append(f"Playbook: {report.playbook_id}")
    lines.append(f"Generated: {report.generated_at.isoformat()}")
    lines.append("")

    if not report.strategies:
        lines.append("No clauses analysed.")
        return "\n".join(lines)

    lines.append(f"Clauses analysed: {len(report.strategies)}")
    lines.append("")

    for i, strategy in enumerate(report.strategies, 1):
        lines.append(f"{i}. {strategy.clause_id}")
        lines.append(f"   Counteroffer: {strategy.suggested_counteroffer}")
        lines.append(f"   Predicted outcome: {strategy.predicted_outcome}")
        lines.append(f"   Equilibrium: {strategy.equilibrium_type}")
        lines.append(f"   Confidence: {strategy.confidence:.2f}")
        if strategy.is_amber:
            lines.append("   [AMBER]")
        if strategy.diverges_from_alignment:
            lines.append(f"   Divergence: {strategy.cross_reference_note}")
        if strategy.assumptions:
            for assump in strategy.assumptions:
                lines.append(f"   * {assump}")
        lines.append("")

    # Payoff matrix summary
    lines.append("--- Payoff Summary ---")
    lines.append("")
    for i, (strategy, pm) in enumerate(
        zip(report.strategies, report.payoff_matrices, strict=False), 1
    ):
        lines.append(f"{i}. {strategy.clause_id}")
        for j, action in enumerate(pm.actions):
            u_val = pm.user_payoffs[j][j]
            c_val = pm.counterparty_payoffs[j][j]
            lines.append(f"   {action}: user={u_val:.2f}, cp={c_val:.2f}")
        lines.append("")

    lines.append("--- Summary ---")
    lines.append(f"Total: {report.summary.total_clauses}")
    lines.append(f"Amber: {report.summary.amber_count}")
    lines.append(f"Impasse: {report.summary.impasse_count}")
    lines.append(f"Deadlock risk: {'Yes' if report.summary.deadlock_risk else 'No'}")
    lines.append(f"Avg confidence: {report.summary.avg_confidence:.2f}")
    lines.append("")
    lines.append("Advisory only — not legal advice.")

    return "\n".join(lines)


def _confidence_bar(confidence: float) -> str:
    """Render a simple confidence bar."""
    filled = int(confidence * 10)
    bar = "█" * filled + "░" * (10 - filled)
    return f"{confidence:.2f} {bar}"
