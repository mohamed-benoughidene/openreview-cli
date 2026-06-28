from __future__ import annotations

import enum
import sys
from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console
from rich.table import Table

from openreview_cli.config.loader import load_config
from openreview_cli.config.paths import get_config_dir
from openreview_cli.types import OutputFormat as OutputFormat  # noqa: PLC0414
from openreview_cli.ui.components.prompt import checkbox, confirm, select
from openreview_cli.ui.console import renderer


class ReviewMode(enum.StrEnum):
    FULL = "full"
    CLAUSE_BY_CLAUSE = "clause-by-clause"
    RISK_SCAN = "risk-scan"


JURISDICTION_CODES: list[dict[str, str]] = [
    {"code": "us-de", "label": "United States — Delaware"},
    {"code": "us-ca", "label": "United States — California"},
    {"code": "us-ny", "label": "United States — New York"},
    {"code": "us-tx", "label": "United States — Texas"},
    {"code": "us-il", "label": "United States — Illinois"},
    {"code": "uk", "label": "United Kingdom"},
    {"code": "eu-gdpr", "label": "European Union — GDPR"},
    {"code": "eu-de", "label": "European Union — Germany"},
    {"code": "eu-fr", "label": "European Union — France"},
    {"code": "ca", "label": "Canada"},
    {"code": "au", "label": "Australia"},
    {"code": "sg", "label": "Singapore"},
]

SUPPORTED_EXTENSIONS = {".pdf", ".docx"}


@dataclass
class ReviewConfiguration:
    file_path: Path
    mode: ReviewMode
    jurisdiction: str | None = None
    output_format: OutputFormat | None = None
    clauses: list[str] | None = field(default=None)

    def __post_init__(self) -> None:
        if not self.file_path.exists():
            raise ValueError(f"File not found: {self.file_path}")
        if self.mode in (ReviewMode.FULL, ReviewMode.CLAUSE_BY_CLAUSE):
            if self.jurisdiction is None:
                raise ValueError("jurisdiction is required for full/clause-by-clause mode")
            if self.output_format is None:
                raise ValueError("output_format is required for full/clause-by-clause mode")
        if (
            self.mode == ReviewMode.CLAUSE_BY_CLAUSE
            and self.clauses is not None
            and len(self.clauses) == 0
        ):
            raise ValueError("clauses must be non-empty or None")


class ReviewWizard:
    def __init__(
        self,
        file_path: str,
        non_interactive: bool = False,
        mode: str | None = None,
        jurisdiction: str | None = None,
        output_format: str | None = None,
        clauses: list[str] | None = None,
        no_pii: bool = False,
    ) -> None:
        self.file_path = Path(file_path)
        self.non_interactive = non_interactive
        self._mode = mode
        self._jurisdiction = jurisdiction
        self._output_format = output_format
        self._clauses = clauses
        self._no_pii = no_pii
        self.console = Console()

    def _validate_file(self) -> None:
        if not self.non_interactive and not renderer.is_interactive:
            self.console.print(
                "[yellow]Non-interactive terminal detected. "
                "Use --non-interactive flag or run in a terminal.[/yellow]"
            )
            sys.exit(1)
        if not self.file_path.exists():
            self.console.print(f"[red]Error: file not found '{self.file_path}'[/red]")
            sys.exit(1)
        if self.file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            self.console.print(
                f"[red]Error: unsupported file type '{self.file_path.suffix}'. "
                f"Supported: {', '.join(SUPPORTED_EXTENSIONS)}[/red]"
            )
            sys.exit(1)
        if not self._is_valid_file(self.file_path):
            self.console.print(
                f"[red]Error: file '{self.file_path}' appears to be corrupted or not a valid "
                f"file of type {self.file_path.suffix}.[/red]"
            )
            sys.exit(1)

    def run(self) -> ReviewConfiguration:
        self._validate_file()

        if self.non_interactive:
            return self._non_interactive_flow()

        self._preflight_check()

        while True:
            mode = self._prompt_mode()
            if mode is None:
                self.console.print("[yellow]Cancelled.[/yellow]")
                sys.exit(0)

            if mode == ReviewMode.RISK_SCAN:
                config = ReviewConfiguration(
                    file_path=self.file_path,
                    mode=ReviewMode.RISK_SCAN,
                )
                if self.confirm_summary(config):
                    return config
                continue

            jur = self._prompt_jurisdiction()
            if jur is None:
                continue

            fmt = self._prompt_output_format()
            if fmt is None:
                continue

            clauses: list[str] | None = None
            if mode == ReviewMode.CLAUSE_BY_CLAUSE:
                clauses = self._prompt_clauses()
                if clauses is None:
                    continue

            config = ReviewConfiguration(
                file_path=self.file_path,
                mode=mode,
                jurisdiction=jur,
                output_format=fmt,
                clauses=clauses,
            )
            if self.confirm_summary(config):
                return config

    def _non_interactive_flow(self) -> ReviewConfiguration:
        if self._mode is None:
            self.console.print("[red]Error: --mode is required in non-interactive mode[/red]")
            sys.exit(1)
        try:
            mode = ReviewMode(self._mode)
        except ValueError:
            self.console.print(
                f"[red]Error: invalid mode '{self._mode}'. "
                f"Choose from: {', '.join(m.value for m in ReviewMode)}[/red]"
            )
            sys.exit(1)

        jur: str | None = None
        fmt: OutputFormat | None = None
        if mode in (ReviewMode.FULL, ReviewMode.CLAUSE_BY_CLAUSE):
            if self._jurisdiction is None:
                self.console.print(
                    "[red]Error: --jurisdiction is required in non-interactive mode for full/clause-by-clause[/red]"
                )
                sys.exit(1)
            jur = self._jurisdiction
            if self._output_format is None:
                self.console.print(
                    "[red]Error: --output is required in non-interactive mode for full/clause-by-clause[/red]"
                )
                sys.exit(1)
            try:
                fmt = OutputFormat(self._output_format)
            except ValueError:
                self.console.print(
                    f"[red]Error: invalid output format '{self._output_format}'. "
                    f"Choose from: {', '.join(o.value for o in OutputFormat)}[/red]"
                )
                sys.exit(1)

        clauses: list[str] | None = None
        if mode == ReviewMode.CLAUSE_BY_CLAUSE and self._clauses is not None:
            if len(self._clauses) == 0:
                self.console.print("[red]Error: --clauses requires at least one clause ID[/red]")
                sys.exit(1)
            clauses = self._clauses

        return ReviewConfiguration(
            file_path=self.file_path,
            mode=mode,
            jurisdiction=jur,
            output_format=fmt,
            clauses=clauses,
        )

    def _preflight_check(self) -> None:
        config_path = get_config_dir() / "config.yml"
        if not config_path.exists():
            self.console.print(
                "[yellow]Gateway not configured. Run 'openreview gateway setup' first.[/yellow]"
            )
            setup_now = confirm("Run gateway setup now?")
            if setup_now:
                from openreview_cli.gateway.wizard import SetupWizard

                SetupWizard().run()
                return
            self.console.print("[dim]Continuing with defaults...[/dim]")
            return

        try:
            config = load_config(config_path)
            models = config.get("gateway", {}).get("models", {})
            chat_slots = {"reasoning", "extraction", "graph"}
            has_chat = any(models.get(s, {}).get("primary") for s in chat_slots)
            has_embed = bool(models.get("embedding", {}).get("primary"))
            if not has_chat or not has_embed:
                self.console.print(
                    "[yellow]Gateway is missing required models. "
                    "Need at least one chat slot (reasoning/extraction/graph) and one embedding slot configured.[/yellow]"
                )
                setup_now = confirm("Run gateway setup now?")
                if setup_now:
                    from openreview_cli.gateway.wizard import SetupWizard

                    SetupWizard().run()
        except Exception:
            self.console.print("[yellow]Could not read gateway config.[/yellow]")

    @staticmethod
    def _is_valid_file(path: Path) -> bool:
        try:
            header = path.read_bytes()[:4]
        except (OSError, PermissionError):
            return False
        if path.suffix.lower() == ".pdf":
            return header.startswith(b"%PDF")
        if path.suffix.lower() == ".docx":
            return header.startswith(b"PK\x03\x04")
        return True

    def _prompt_mode(self) -> ReviewMode | None:
        result = select(
            "Select review mode",
            choices=["full", "clause-by-clause", "risk-scan"],
            default="full",
            hint="use arrow keys",
        )
        if result is None:
            return None
        return ReviewMode(result)

    def _prompt_jurisdiction(self) -> str | None:
        choices = [f"{j['code']} — {j['label']}" for j in JURISDICTION_CODES] + ["← Back"]
        result = select(
            "Select jurisdiction",
            choices=choices,
            default=choices[0],
            hint="use arrow keys",
        )
        if result is None or result == "← Back":
            return None
        code = result.split(" — ")[0]
        return code

    def _prompt_output_format(self) -> OutputFormat | None:
        choices = ["table", "json", "plain", "← Back"]
        result = select(
            "Select output format",
            choices=choices,
            default="json",
        )
        if result is None or result == "← Back":
            return None
        return OutputFormat(result)

    def _prompt_clauses(self) -> list[str] | None:
        clause_ids = [str(i) for i in range(1, 51)]
        result = checkbox(
            "Select clauses to review (space to toggle, enter to confirm)",
            choices=[*clause_ids, "← Back"],
        )
        if result is None or result == ["← Back"]:
            return None
        return result

    def confirm_summary(self, config: ReviewConfiguration) -> bool:
        self.console.print("\n[bold]Review Configuration Summary:[/bold]")
        table = Table()
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("File", str(config.file_path))
        table.add_row("Mode", config.mode.value)
        if config.jurisdiction:
            table.add_row("Jurisdiction", config.jurisdiction)
        if config.output_format:
            table.add_row("Output Format", config.output_format.value)
        if config.clauses is not None:
            table.add_row("Clauses", ", ".join(config.clauses))

        self.console.print(table)
        result = confirm("Proceed with this configuration?")
        return bool(result)
