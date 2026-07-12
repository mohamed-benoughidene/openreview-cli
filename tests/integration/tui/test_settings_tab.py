"""Integration tests for Settings tab (T028)."""

from __future__ import annotations

from typing import Any

import pytest
from textual.widgets import Button, Static

from openreview_cli import __version__
from openreview_cli.tui.app import OpenReviewApp

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
            assert "Keyboard navigation only" in text

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
            assert "github.com" in display.content

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

    async def test_pricing_tier_shows_usage_stats(self) -> None:
        """Pricing tier section shows pricing information."""
        app = OpenReviewApp()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.press("5")
            await pilot.pause()
            await pilot.click("#section-pricing-tier")
            await pilot.pause()
            display = app.query_one("#section-content-display", Static)
            assert "Pricing Tier" in display.content
            assert "—" in display.content

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
        async with app.run_test(size=(80, 24)) as pilot:
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
        async with app.run_test(size=(80, 24)) as pilot:
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
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.press("5")
            await pilot.pause()
            await pilot.click("#section-about")
            await pilot.pause()

            await pilot.click("#copy-doc-url")
            await pilot.pause()

            assert app._clipboard is not None
            assert "github.com" in app._clipboard

    async def test_copy_shows_confirmation(self) -> None:
        """Click copy button, assert 'Copied!' notification appears."""
        notified: list[str] = []
        app = OpenReviewApp()
        async with app.run_test(size=(80, 24)) as pilot:
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
            assert "Keyboard navigation only" in display.content
