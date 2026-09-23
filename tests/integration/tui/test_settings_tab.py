"""Integration tests for Settings tab (T028)."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from textual.widgets import Button, Static

from openreview_cli import __version__
from openreview_cli.pii.cache import PiiCache
from openreview_cli.tui.app import OpenReviewApp
from openreview_cli.tui.screens.pii_data import PiiDataScreen

MOCK_SLOTS: dict[str, dict[str, Any]] = {
    "reasoning": {"provider": "openai", "model": "gpt-4o", "configured": True},
    "extraction": {"provider": "anthropic", "model": "claude-3-haiku-20240307", "configured": True},
    "embedding": {"provider": "openai", "model": "text-embedding-3-small", "configured": True},
    "reranking": {"provider": "", "model": "", "configured": False},
    "graph": {"provider": "openai", "model": "gpt-4o", "configured": True},
    "grounding": {"provider": "", "model": "", "configured": False},
}

MOCK_HEALTH: dict[str, dict[str, Any]] = {
    "reasoning": {"status": "configured", "provider": "openai"},
    "extraction": {"status": "configured", "provider": "anthropic"},
    "embedding": {"status": "configured", "provider": "openai"},
    "reranking": {"status": "not_configured"},
    "graph": {"status": "configured", "provider": "openai"},
    "grounding": {"status": "not_configured"},
}


@pytest.fixture(autouse=True)
def patch_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch settings tab's imported domain references."""
    monkeypatch.setattr(
        "openreview_cli.tui.tabs.settings.get_slot_configs",
        lambda: MOCK_SLOTS,
    )
    monkeypatch.setattr(
        "openreview_cli.tui.tabs.settings.gateway_health_check",
        lambda: MOCK_HEALTH,
    )


def _seed_stored_pii(db_path: Path, doc_hash: str, base_dir: Path, entities: int = 3) -> None:
    """Write the real encrypted-mapping artifacts + cache/audit rows."""
    review_dir = base_dir / "reviews" / doc_hash[:12]
    review_dir.mkdir(parents=True, exist_ok=True)
    mapping = review_dir / "pii_map.enc"
    stripped = review_dir / "stripped.txt"
    mapping.write_text("{}", encoding="utf-8")
    stripped.write_text("hello", encoding="utf-8")
    PiiCache(db_path).put(doc_hash, "cfg", str(stripped), str(mapping))
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "INSERT INTO pii_audit_trail "
            "(document_hash, timestamp, entity_count, entity_type_distribution, "
            " processing_time_ms, config_hash, status, failed_pages) "
            "VALUES (?, ?, ?, '{}', 0, 'cfg', 'success', '[]')",
            (doc_hash, datetime.now(UTC).isoformat(), entities),
        )
        conn.commit()
    finally:
        conn.close()


class TestSettingsTab:
    """T028 — Settings tab integration tests."""

    async def test_settings_two_panel_layout(self) -> None:
        """Open Settings tab, assert sections list + content area visible."""
        app = OpenReviewApp()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.press("5")
            await pilot.pause()

            sections_list = app.query_one("#sections-list")
            assert sections_list is not None
            assert sections_list.visible

            section_content = app.query_one("#section-content")
            assert section_content is not None
            assert section_content.visible

            for section_id in (
                "section-gateway",
                "section-configuration",
                "section-pricing-tier",
                "section-pii-data",
                "section-about",
            ):
                btn = app.query_one(f"#{section_id}")
                assert btn is not None
                assert btn.visible

    async def test_settings_pricing_tier_em_dash(self) -> None:
        """Select Pricing tier, assert '—' with 'not available yet' note."""
        app = OpenReviewApp()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.press("5")
            await pilot.pause()
            await pilot.click("#section-pricing-tier")
            await pilot.pause()

            display = app.query_one("#section-content-display", Static)
            text = display.content
            assert "—" in text
            assert "not available yet" in text.lower()

    async def test_settings_configuration_section_renders(self) -> None:
        """Select Configuration section, assert renders."""
        app = OpenReviewApp()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.press("5")
            await pilot.pause()
            await pilot.click("#section-configuration")
            await pilot.pause()

            display = app.query_one("#section-content-display", Static)
            text = display.content
            assert "Configuration" in text or "config" in text.lower()

    async def test_settings_about_section_renders(self) -> None:
        """Select About section, assert version, license, accessibility note."""
        app = OpenReviewApp()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.press("5")
            await pilot.pause()
            await pilot.click("#section-about")
            await pilot.pause()

            display = app.query_one("#section-content-display", Static)
            text = display.content
            assert __version__ in text
            assert "AGPL-3.0" in text
            assert "Python" in text
            assert "Keyboard navigation" in text

    async def test_settings_gateway_section_shows_slots(self) -> None:
        """Select Gateway section, assert 6 slot rows visible."""
        app = OpenReviewApp()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.press("5")
            await pilot.pause()

            display = app.query_one("#section-content-display", Static)
            text = display.content
            assert "Reasoning" in text
            assert "gpt-4o" in text
            assert "Extraction" in text
            assert "Embedding" in text
            assert "Reranking" in text
            assert "Graph" in text
            assert "Grounding" in text

            btn = app.query_one("#run-wizard", Button)
            assert btn is not None
            assert btn.visible

    # ── Gap #1: gateway backup model line ───────────────────────────

    async def test_gateway_section_shows_backup_model(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A slot with a backup model renders a read-only backup line."""
        monkeypatch.setitem(MOCK_SLOTS["reasoning"], "fallback", "anthropic/claude-3-5-haiku")

        app = OpenReviewApp()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.press("5")
            await pilot.pause()

            display = app.query_one("#section-content-display", Static)
            assert "claude-3-5-haiku" in display.content

    # ── T042: About section details ─────────────────────────────────

    async def test_about_shows_version(self) -> None:
        """About section displays application version."""
        app = OpenReviewApp()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.press("5")
            await pilot.pause()
            await pilot.click("#section-about")
            await pilot.pause()
            display = app.query_one("#section-content-display", Static)
            assert __version__ in display.content

    async def test_about_shows_paths(self) -> None:
        """About section shows database and config paths."""
        app = OpenReviewApp()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.press("5")
            await pilot.pause()
            await pilot.click("#section-about")
            await pilot.pause()
            display = app.query_one("#section-content-display", Static)
            assert "Database:" in display.content
            assert "Config:" in display.content

    async def test_about_shows_documentation_url(self) -> None:
        """About section shows documentation URL."""
        app = OpenReviewApp()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.press("5")
            await pilot.pause()
            await pilot.click("#section-about")
            await pilot.pause()
            display = app.query_one("#section-content-display", Static)
            assert "Documentation:" in display.content
            assert "openreview" in display.content

    # ── T043: Configuration & Pricing tier sections ─────────────────

    async def test_configuration_section_shows_path(self) -> None:
        """Configuration section shows config file path."""
        app = OpenReviewApp()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.press("5")
            await pilot.pause()
            await pilot.click("#section-configuration")
            await pilot.pause()
            display = app.query_one("#section-content-display", Static)
            assert "Config file:" in display.content

    async def test_pricing_tier_shows_usage_stats(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Pricing tier section shows usage statistics."""
        from openreview_cli.tui.tabs.settings import SettingsTab

        def mock_usage(self: Any) -> dict[str, int]:
            return {"prompt_tokens": 1234, "completion_tokens": 567, "cost_cents": 42}

        monkeypatch.setattr(SettingsTab, "_get_usage_stats", mock_usage)

        app = OpenReviewApp()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.press("5")
            await pilot.pause()
            await pilot.click("#section-pricing-tier")
            await pilot.pause()
            display = app.query_one("#section-content-display", Static)
            assert "Pricing Tier" in display.content
            assert "Usage Statistics" in display.content
            assert "1234" in display.content
            assert "567" in display.content
            assert "$0.42" in display.content

    async def test_pricing_tier_em_dash_with_note(self) -> None:
        """Pricing tier shows em-dash with 'not available yet' note."""
        app = OpenReviewApp()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.press("5")
            await pilot.pause()
            await pilot.click("#section-pricing-tier")
            await pilot.pause()
            display = app.query_one("#section-content-display", Static)
            assert "—" in display.content
            assert "not available yet" in display.content.lower()

    # ── T044: Copy-to-clipboard ─────────────────────────────────────

    async def test_copy_database_path_to_clipboard(self) -> None:
        """Click copy DB path button, assert clipboard contains db path."""
        app = OpenReviewApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("5")
            await pilot.pause()
            await pilot.click("#section-about")
            await pilot.pause()

            await pilot.click("#copy-db-path")
            await pilot.pause()

            assert app._clipboard is not None
            assert ".db" in app._clipboard

    async def test_copy_config_path_to_clipboard(self) -> None:
        """Click copy config path button, assert clipboard contains config path."""
        app = OpenReviewApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("5")
            await pilot.pause()
            await pilot.click("#section-about")
            await pilot.pause()

            await pilot.click("#copy-config-path")
            await pilot.pause()

            assert app._clipboard is not None
            assert "config" in app._clipboard.lower()

    async def test_copy_documentation_url_to_clipboard(self) -> None:
        """Click copy docs URL button, assert clipboard contains URL."""
        app = OpenReviewApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("5")
            await pilot.pause()
            await pilot.click("#section-about")
            await pilot.pause()

            await pilot.click("#copy-doc-url")
            await pilot.pause()

            assert app._clipboard is not None
            assert "mohamed-benoughidene" in app._clipboard

    async def test_copy_shows_confirmation(self) -> None:
        """Click copy button, assert 'Copied!' notification appears."""
        notified: list[str] = []
        app = OpenReviewApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("5")
            await pilot.pause()
            await pilot.click("#section-about")
            await pilot.pause()

            # Capture notify calls
            original_notify = app.notify
            app.notify = lambda msg, **kw: notified.append(msg)  # type: ignore[method-assign]

            await pilot.click("#copy-db-path")
            await pilot.pause()

            assert "Copied!" in notified

    # ── T058: Zero-provider prompt ──────────────────────────────────

    async def test_zero_providers_shows_setup_prompt(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Empty slot configs shows setup prompt instead of slot list."""
        monkeypatch.setattr(
            "openreview_cli.tui.tabs.settings.get_slot_configs",
            lambda: {},
        )
        app = OpenReviewApp()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.press("5")
            await pilot.pause()

            display = app.query_one("#section-content-display", Static)
            text = display.content
            assert "No providers configured yet" in text
            assert "Run setup wizard" in text

    # ── T045: Accessibility note ────────────────────────────────────

    async def test_about_shows_accessibility_note(self) -> None:
        """About section shows accessibility note."""
        app = OpenReviewApp()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.press("5")
            await pilot.pause()
            await pilot.click("#section-about")
            await pilot.pause()
            display = app.query_one("#section-content-display", Static)
            assert "Keyboard navigation" in display.content

    # ── T046: Accessibility & privacy in About ─────────────────────────

    async def test_about_section_documents_accessibility(self) -> None:
        """About must state the keyboard scope and the screen-reader limitation (P2)."""
        from openreview_cli.tui.tabs.settings import SettingsTab

        app = OpenReviewApp()
        async with app.run_test(size=(120, 40)) as pilot:
            tab = app.query_one(SettingsTab)
            tab.select_section("about")
            await pilot.pause()
            display = tab.query_one("#section-content-display", Static)
            text = str(display.render())
            assert "Accessibility" in text, text
            assert "Screen reader" in text, text
            assert "Keyboard" in text, text
            assert "Privacy" in text, text

    # ── PII data section: entry point to the stored-PII screen ──────

    async def test_pii_data_section_reports_what_is_stored(
        self, isolated_xdg: dict[str, Path]
    ) -> None:
        """The section states how many documents still have a stored mapping."""
        _seed_stored_pii(isolated_xdg["db_path"], "c0ffee12" + "0" * 56, isolated_xdg["data_dir"])

        app = OpenReviewApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.press("5")
            await pilot.pause()
            await pilot.click("#section-pii-data")
            await pilot.pause()

            text = str(app.query_one("#section-content-display", Static).render())
            assert "Stored PII data" in text, text
            assert "1 document" in text, text
            assert app.query_one("#manage-pii", Button).display is True

    async def test_pii_data_section_handles_an_empty_store(
        self, isolated_xdg: dict[str, Path]
    ) -> None:
        app = OpenReviewApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.press("5")
            await pilot.pause()
            await pilot.click("#section-pii-data")
            await pilot.pause()

            text = str(app.query_one("#section-content-display", Static).render())
            assert "No documents with stored PII data" in text, text

    async def test_manage_pii_button_opens_the_stored_pii_screen(
        self, isolated_xdg: dict[str, Path]
    ) -> None:
        _seed_stored_pii(isolated_xdg["db_path"], "c0ffee12" + "0" * 56, isolated_xdg["data_dir"])

        app = OpenReviewApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.press("5")
            await pilot.pause()
            await pilot.click("#section-pii-data")
            await pilot.pause()
            await pilot.click("#manage-pii")
            await pilot.pause()

            assert isinstance(app.screen, PiiDataScreen)

    async def test_manage_pii_button_is_hidden_outside_its_section(
        self, isolated_xdg: dict[str, Path]
    ) -> None:
        app = OpenReviewApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.press("5")
            await pilot.pause()
            assert app.query_one("#manage-pii", Button).display is False

            await pilot.click("#section-pii-data")
            await pilot.pause()
            assert app.query_one("#manage-pii", Button).display is True

            await pilot.click("#section-about")
            await pilot.pause()
            assert app.query_one("#manage-pii", Button).display is False

    # ── Every section stays reachable at the smallest viewport ──────

    async def test_every_section_is_reachable_at_the_smallest_viewport(
        self, isolated_xdg: dict[str, Path]
    ) -> None:
        """Each section button switches the pane at 80x24 (clipping regression guard)."""
        expected = {
            "section-gateway": "Model Slots",
            "section-configuration": "Config file:",
            "section-pricing-tier": "Pricing Tier",
            "section-pii-data": "Stored PII data",
            "section-about": __version__,
        }

        app = OpenReviewApp()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.press("5")
            await pilot.pause()

            for section_id, phrase in expected.items():
                await pilot.click(f"#{section_id}")
                await pilot.pause()
                text = app.query_one("#section-content-display", Static).content
                assert phrase in text, f"{section_id} did not render {phrase!r}: {text!r}"
