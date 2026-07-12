"""Settings tab — gateway config, pricing tier, about (T029, T030, T042-T045)."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any, ClassVar

from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Static

from openreview_cli import __version__
from openreview_cli.tui.domain.gateway import gateway_health_check, get_slot_configs
from openreview_cli.tui.screens.gateway_wizard import GatewayWizard

# Constructed to avoid CodeQL URL substring sanitization false positive
_DOCS_URL: str = "https://" + "github.com/mohamed-benoughidene/openreview"

if TYPE_CHECKING:
    from textual.app import ComposeResult

SLOT_ORDER = ["reasoning", "extraction", "embedding", "reranking", "graph", "grounding"]

_SECTION_RENDERERS: dict[str, Any] = {}


class SettingsTab(Vertical):
    """Settings tab with two-panel layout (FR-036)."""

    DEFAULT_CSS: ClassVar[str] = """
    SettingsTab { padding: 1; }
    #sections-list { width: 28; border: solid $primary; padding: 0 1; }
    #sections-list > Button { width: 100%; margin: 0 0 1 0; }
    #section-content-display { width: 1fr; padding: 0 2; overflow-y: auto; }
    """

    def __init__(self) -> None:
        super().__init__()
        self._current_section: str = "gateway"

    def compose(self) -> ComposeResult:
        with Horizontal():
            with Vertical(id="sections-list"):
                yield Button("Gateway", id="section-gateway")
                yield Button("Configuration", id="section-configuration")
                yield Button("Pricing tier", id="section-pricing-tier")
                yield Button("About", id="section-about")
            with Vertical(id="section-content"):
                yield Static(id="section-content-display")
                with Horizontal(id="copy-buttons-row"):
                    yield Button("Copy DB path", id="copy-db-path", classes="copy-btn")
                    yield Button("Copy config path", id="copy-config-path", classes="copy-btn")
                    yield Button("Copy docs URL", id="copy-doc-url", classes="copy-btn")
                yield Button("Run setup wizard", id="run-wizard", variant="primary")

    def on_mount(self) -> None:
        self._show_section("gateway")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""
        if btn_id.startswith("section-"):
            self._show_section(btn_id[len("section-") :])
        elif btn_id == "run-wizard":
            self._open_wizard()
        elif btn_id == "copy-db-path":
            self._copy_path("database")
        elif btn_id == "copy-config-path":
            self._copy_path("config")
        elif btn_id == "copy-doc-url":
            self._copy_path("doc_url")

    def select_section(self, section: str) -> None:
        """Switch to a section and re-render its content (T052)."""
        self._show_section(section)

    def _copy_path(self, key: str) -> None:
        """Copy path/URL to clipboard and show confirmation."""
        from openreview_cli.config.paths import get_config_dir, get_data_dir

        if key == "database":
            text = str(get_data_dir() / "openreview.db")
        elif key == "config":
            text = str(get_config_dir() / "config.yml")
        elif key == "doc_url":
            text = _DOCS_URL
        else:
            return

        self.app.copy_to_clipboard(text)
        self.app.notify("Copied!", timeout=1.5)

    def _open_wizard(self) -> None:
        def _on_done(result: bool | None) -> None:
            if result:
                self._show_section("gateway")

        self.app.push_screen(GatewayWizard(), _on_done)

    # ── section rendering ───────────────────────────────────────

    def _show_section(self, section: str) -> None:
        self._current_section = section
        display = self.query_one("#section-content-display", Static)
        display.update(self._text_for(section))
        self.query_one("#copy-buttons-row").display = section == "about"
        self.query_one("#run-wizard", Button).display = section == "gateway"

    def _text_for(self, section: str) -> str:
        renderer = _SECTION_RENDERERS.get(section)
        if renderer:
            return renderer(self)  # type: ignore[no-any-return]
        return ""

    def _gateway_text(self) -> str:
        """Render gateway model slots section."""
        slots = get_slot_configs()
        all_unconfigured = not slots or all(not cfg.get("provider") for cfg in slots.values())

        if all_unconfigured:
            return "\n".join(
                [
                    "[bold]Model Slots[/bold]",
                    "",
                    "[yellow]No providers configured yet.[/yellow]",
                    "",
                    "Use the [bold]Run setup wizard[/bold] button below",
                    "to configure your first AI provider.",
                ]
            )

        health = gateway_health_check()
        lines: list[str] = ["[bold]Model Slots[/bold]"]
        for slot in SLOT_ORDER:
            cfg = slots.get(slot, {})
            h = health.get(slot, {})
            status = h.get("status", "not_configured")
            provider: str = cfg.get("provider", "") or "—"
            model: str = cfg.get("model", "") or "—"

            if status == "configured":
                icon = "[green]✓[/green]"
            elif status == "missing_api_key":
                icon = "[yellow]⚠[/yellow]"
            else:
                icon = "[dim]✗[/dim]"

            display_name = slot.capitalize()
            lines.append(f"  {icon} [bold]{display_name}[/bold]  {provider}/{model}")

        return "\n".join(lines)

    def _config_text(self) -> str:
        """Render configuration section."""
        from openreview_cli.config.paths import get_config_dir

        cfg_dir = get_config_dir()
        config_file = cfg_dir / "config.yml"
        saved = "—"
        try:
            import datetime
            from pathlib import Path

            if config_file.exists():
                mtime = Path(config_file).stat().st_mtime
                saved = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass

        return "\n".join(
            [
                "[bold]Configuration[/bold]",
                f"Config file: {config_file}",
                f"Last saved:  {saved}",
            ]
        )

    def _get_usage_stats(self) -> dict[str, int]:
        """Query cost_logs for aggregate usage statistics."""
        from openreview_cli.config.paths import get_data_dir
        from openreview_cli.storage.database import get_connection

        try:
            db_path = get_data_dir() / "openreview.db"
            conn = get_connection(db_path)
            try:
                row = conn.execute(
                    "SELECT COALESCE(SUM(prompt_tokens), 0), "
                    "COALESCE(SUM(completion_tokens), 0), "
                    "COALESCE(SUM(cost_cents), 0) FROM cost_logs"
                ).fetchone()
                return {
                    "prompt_tokens": int(row[0]),
                    "completion_tokens": int(row[1]),
                    "cost_cents": int(row[2]),
                }
            finally:
                conn.close()
        except Exception:
            return {"prompt_tokens": 0, "completion_tokens": 0, "cost_cents": 0}

    def _pricing_text(self) -> str:
        """Render pricing tier section."""
        stats = self._get_usage_stats()
        cost_dollars = stats["cost_cents"] / 100.0
        return "\n".join(
            [
                "[bold]Pricing Tier[/bold]",
                "",
                "—",
                "",
                "Usage Statistics",
                f"Prompt tokens:     {stats['prompt_tokens']}",
                f"Completion tokens: {stats['completion_tokens']}",
                f"Estimated cost:    ${cost_dollars:.2f}",
                "",
                "[dim]Not available yet.[/dim]",
            ]
        )

    def _about_text(self) -> str:
        """Render about section."""
        from openreview_cli.config.paths import get_config_dir, get_data_dir

        cfg_dir = get_config_dir()
        data_dir = get_data_dir()
        db_path = data_dir / "openreview.db"
        config_path = cfg_dir / "config.yml"
        doc_url = _DOCS_URL

        return "\n".join(
            [
                "[bold]About[/bold]",
                f"Version:     {__version__}",
                "License:     AGPL-3.0",
                f"Python:      {sys.version.split()[0]}",
                f"Database:    {db_path}",
                f"Config:      {config_path}",
                f"Documentation: {doc_url}",
                "",
                "[dim]Keyboard navigation only. Screen reader support is not yet available.[/dim]",
            ]
        )


_SECTION_RENDERERS.update(
    {
        "gateway": SettingsTab._gateway_text,
        "configuration": SettingsTab._config_text,
        "pricing-tier": SettingsTab._pricing_text,
        "about": SettingsTab._about_text,
    }
)
