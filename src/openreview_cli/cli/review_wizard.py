"""Review wizard — interactive flow using the Wizard state machine (T043/T046/T048).

Extends the generic ``Wizard`` with review-specific steps:

    mode_selection → configuration → confirm → processing → results

The wizard handles Ctrl-C at the outer loop level and prints a
cancellation message per spec FR-PP-004.
"""

from __future__ import annotations

import sys
from pathlib import Path

from openreview_cli.cli.review import JURISDICTION_CODES, ReviewMode
from openreview_cli.ui.components.prompt import checkbox, confirm, select
from openreview_cli.types import OutputFormat
from openreview_cli.ui.components.progress import Progress
from openreview_cli.ui.components.spinner import Spinner
from openreview_cli.ui.components.status_line import format_clause_label
from openreview_cli.ui.components.table import SGTable
from openreview_cli.ui.components.wizard import StepDef, Wizard

# ---------------------------------------------------------------------------
# Step definitions  (spec §2.11 — review flow)
# ---------------------------------------------------------------------------

REVIEW_STEPS: list[StepDef] = [
    StepDef("mode_selection", "Select Mode"),
    StepDef("configuration", "Configure"),
    StepDef("confirm", "Confirm"),
    StepDef("processing", "Processing"),
    StepDef("results", "Results"),
]


# ---------------------------------------------------------------------------
# ReviewFlowWizard
# ---------------------------------------------------------------------------


class ReviewFlowWizard(Wizard):
    """Interactive review wizard built on the ``Wizard`` state machine.

    Parameters
    ----------
    file_path:
        Path to the contract file being reviewed.
    """

    def __init__(self, file_path: str, no_pii: bool = False) -> None:
        super().__init__(steps=REVIEW_STEPS)
        self.file_path = Path(file_path)
        self._no_pii = no_pii
        self._findings: list[dict[str, str]] = []

    # -- step handlers -------------------------------------------------------

    def _step_mode_selection(self) -> str | None:
        """Prompt the user to choose a review mode."""
        result = select(
            "Select review mode",
            choices=["full", "clause-by-clause", "risk-scan"],
            default="full",
            hint="use arrow keys",
        )
        if result is None:
            return None  # Esc on first step → exit
        self.data["mode"] = ReviewMode(result)
        return self._next()

    def _step_configuration(self) -> str | None:
        """Prompt for jurisdiction, output format, and optional clauses."""
        mode = self.data.get("mode")

        # Risk scan needs no configuration
        if mode == ReviewMode.RISK_SCAN:
            return self._next()

        # Jurisdiction
        choices = [f"{j['code']} — {j['label']}" for j in JURISDICTION_CODES]
        jur_result = select(
            "Select jurisdiction",
            choices=choices + ["← Back"],
            default=choices[0],
            hint="use arrow keys",
        )
        if jur_result is None or jur_result == "← Back":
            return self._back()
        self.data["jurisdiction"] = jur_result.split(" — ")[0]

        # Output format
        fmt_choices = ["table", "json", "plain"]
        fmt_result = select(
            "Select output format",
            choices=fmt_choices + ["← Back"],
            default="json",
        )
        if fmt_result is None or fmt_result == "← Back":
            return self._back()
        self.data["output_format"] = OutputFormat(fmt_result)

        # Clauses for clause-by-clause mode
        if mode == ReviewMode.CLAUSE_BY_CLAUSE:
            clause_ids = [str(i) for i in range(1, 51)]
            clauses_result = checkbox(
                "Select clauses to review (space to toggle, enter to confirm)",
                choices=clause_ids + ["← Back"],
            )
            if clauses_result is None or clauses_result == ["← Back"]:
                return self._back()
            self.data["clauses"] = clauses_result

        return self._next()

    def _step_confirm(self) -> str | None:
        """Show a summary of the configuration and ask for confirmation."""
        mode: ReviewMode | None = self.data.get("mode")
        jurisdiction = self.data.get("jurisdiction")
        output_format = self.data.get("output_format")
        clauses = self.data.get("clauses")

        # Simple confirmation display (spec §2.11)
        print(f"  File: {self.file_path}")
        if mode:
            print(f"  Mode: {mode.value}")
        if jurisdiction:
            print(f"  Jurisdiction: {jurisdiction}")
        if output_format:
            print(f"  Output Format: {output_format.value}")
        if clauses:
            print(f"  Clauses: {', '.join(clauses)}")
        print()

        confirmed = confirm("Proceed with this configuration?")
        if confirmed is None:
            return None  # Ctrl-C
        if not confirmed:
            # Go back to mode selection (not previous step) to match original
            # ReviewWizard behavior and avoid risk-scan auto-advance loops
            return "mode_selection"

        return self._next()

    def _step_processing(self) -> str | None:
        """Run the review analysis with progress/spinner feedback.

        Uses ``Progress`` for determinate clause-by-clause analysis and
        ``Spinner`` for indeterminate PII/AI steps.
        """
        mode: ReviewMode | None = self.data.get("mode")
        clauses: list[str] | None = self.data.get("clauses")

        # Determine total clauses for the progress bar
        total: int = 10  # default mock count

        # ponytail: empty-doc check — real parsing wires here
        if total == 0:
            from openreview_cli.ui.components.panel import warning_panel

            warning_panel(
                "No standard clauses detected. The document may be a scanned image, "
                "unreadable PDF, or non-standard format.",
                title="No Clauses Found",
            )
            return self._next()
        if mode == ReviewMode.CLAUSE_BY_CLAUSE and clauses:
            total = len(clauses)
        elif mode == ReviewMode.FULL:
            total = 12  # typical clause count in a contract

        # Indeterminate: PII stripping
        with Spinner("Stripping PII from document..."):
            pass  # stub — real PII engine not wired yet

        # Determinate: clause-by-clause analysis
        with Progress(total, "Analyzing clauses") as progress:
            for i in range(1, total + 1):
                label = format_clause_label(i, total, f"Clause {i}")
                progress.update(label)
                progress.advance(1)

        # Indeterminate: AI generation
        with Spinner("Generating review findings..."):
            pass  # stub — real AI engine not wired yet

        # Store mock findings for the Results step
        self._findings = [
            {
                "risk": "High",
                "clause": "Indemnification",
                "finding": "Unlimited liability with no cap",
                "recommendation": "Cap liability at contract value",
            },
            {
                "risk": "Medium",
                "clause": "Governing Law",
                "finding": "Foreign jurisdiction clause",
                "recommendation": "Change to local law",
            },
            {
                "risk": "Low",
                "clause": "Termination",
                "finding": "30-day notice period",
                "recommendation": "Acceptable",
            },
        ]

        return self._next()

    def _step_results(self) -> str | None:
        """Display the review findings in an SGTable."""
        mode: ReviewMode | None = self.data.get("mode")
        output_format: OutputFormat = self.data.get(
            "output_format", OutputFormat.TABLE
        )

        columns: list[tuple[str, str, int]] = [
            ("Risk", "bold red", 10),
            ("Clause", "bold", 25),
            ("Finding", "", 40),
            ("Recommendation", "green", 40),
        ]

        rows: list[tuple[str, ...]] = [
            (f["risk"], f["clause"], f["finding"], f["recommendation"])
            for f in self._findings
        ]

        table = SGTable(
            title=f"Review Results ({mode.value if mode else 'full'})",
            columns=columns,
            rows=rows,
            output_format=output_format,
        )
        table.render()

        return None  # Exit after results

    # -- interrupt handler ---------------------------------------------------

    @staticmethod
    def _handle_interrupt() -> None:
        """Print cancellation message per spec FR-PP-004 and exit."""
        print("Review cancelled. Partial results were not saved.", file=sys.stderr)
        sys.exit(1)
