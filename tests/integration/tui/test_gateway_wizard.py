"""Integration tests for gateway setup wizard (T027, T027a)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from openreview_cli.gateway.router import VALID_SLOTS
from openreview_cli.tui.app import OpenReviewApp
from openreview_cli.tui.screens import gateway_wizard as gw_mod

MOCK_PROVIDERS: list[dict[str, Any]] = [
    {"name": "openai", "auth_required": True, "model_count": 3},
    {"name": "anthropic", "auth_required": True, "model_count": 2},
    {"name": "ollama", "auth_required": False, "model_count": 5},
]

MOCK_MODELS: dict[str, list[dict[str, Any]]] = {
    "openai": [
        {"model_id": "gpt-4o", "slots": ["reasoning", "extraction"], "context": 128000},
        {"model_id": "gpt-4o-mini", "slots": ["reasoning"], "context": 128000},
        {"model_id": "text-embedding-3-small", "slots": ["embedding"], "context": 8191},
    ],
    "anthropic": [
        {
            "model_id": "claude-3-opus-20240229",
            "slots": ["reasoning", "extraction"],
            "context": 200000,
        },
    ],
}

MOCK_HEALTH = {s: {"status": "not_configured"} for s in sorted(VALID_SLOTS)}
MOCK_HEALTH_OK = {s: {"status": "configured"} for s in sorted(VALID_SLOTS)}

# Store originals for restoration
_originals: dict[str, Any] = {}


def _patch_all() -> None:
    """Patch all gateway_wizard module imports."""
    global _originals
    for name in (
        "list_providers",
        "list_models",
        "provider_has_key",
        "save_slot_config",
        "save_api_key",
        "gateway_health_check",
    ):
        _originals[name] = getattr(gw_mod, name)
    gw_mod.list_providers = lambda: MOCK_PROVIDERS  # type: ignore[method-assign]
    gw_mod.list_models = lambda p: MOCK_MODELS.get(p, [])  # type: ignore[method-assign]
    gw_mod.provider_has_key = lambda p: False  # type: ignore[method-assign]
    gw_mod.save_slot_config = lambda s, p, m: None  # type: ignore[method-assign]
    gw_mod.save_api_key = lambda p, k: None  # type: ignore[method-assign]
    gw_mod.gateway_health_check = lambda: MOCK_HEALTH  # type: ignore[method-assign]


def _restore_all() -> None:
    """Restore original gateway_wizard module imports."""
    for name, orig in _originals.items():
        setattr(gw_mod, name, orig)


@pytest.fixture(autouse=True)
def patch_gateway_wizard():
    _patch_all()
    yield
    _restore_all()


class TestGatewayWizard:
    """T027 — Gateway wizard integration tests."""

    async def _go_to_step(self, pilot, app, step: int) -> None:
        """Navigate through wizard steps 1-4."""
        if step >= 2:
            await pilot.click("#slot-list ListItem")
            await pilot.pause()
            await pilot.click("#wizard-next")
            await pilot.pause()
        if step >= 3:
            await pilot.click("#provider-list ListItem")
            await pilot.pause()
            await pilot.click("#wizard-next")
            await pilot.pause()
        if step >= 4:
            await pilot.click("#model-list ListItem")
            await pilot.pause()
            await pilot.click("#wizard-next")
            await pilot.pause()

    async def test_wizard_step1_slot_picker(self) -> None:
        """Open wizard, assert 6 slot options visible."""
        app = OpenReviewApp()
        async with app.run_test(size=(80, 24)) as pilot:
            await app.push_screen(gw_mod.GatewayWizard())
            await pilot.pause()

            slot_list = app.screen.query_one("#slot-list")
            assert len(slot_list.children) == 6

            slot_names = set()
            for child in slot_list.children:
                c = child.children[0] if child.children else None
                name = str(c.content) if hasattr(c, "content") else ""
                slot_names.add(name)
            for name in ("Reasoning", "Extraction", "Embedding", "Reranking", "Graph", "Grounding"):
                assert name in slot_names, f"Missing slot: {name}"

    async def test_wizard_step2_provider_filter(self) -> None:
        """Select slot, go to step 2, type filter, assert filter works."""
        app = OpenReviewApp()
        async with app.run_test(size=(80, 24)) as pilot:
            await app.push_screen(gw_mod.GatewayWizard())
            await pilot.pause()

            # Step 1 → Select slot → Next
            await pilot.click("#slot-list ListItem")
            await pilot.pause()
            await pilot.click("#wizard-next")
            await pilot.pause()

            provider_list = app.screen.query_one("#provider-list")
            assert len(provider_list.children) == 3

            # Type filter
            app.screen.query_one("#provider-filter").value = "anth"
            await pilot.pause()

            for child in provider_list.children:
                c = child.children[0] if child.children else None
                txt = str(c.content).lower() if hasattr(c, "content") else ""
                should_show = "anthropic" in txt
                assert child.display == should_show

    async def test_wizard_step3_model_picker(self) -> None:
        """Pick provider, assert models list appears."""
        app = OpenReviewApp()
        async with app.run_test(size=(80, 24)) as pilot:
            await app.push_screen(gw_mod.GatewayWizard())
            await pilot.pause()
            await self._go_to_step(pilot, app, 3)

            model_list = app.screen.query_one("#model-list")
            assert len(model_list.children) > 0

            model_ids = []
            for child in model_list.children:
                c = child.children[0] if child.children else None
                name = str(c.content) if hasattr(c, "content") else ""
                model_ids.append(name)
            assert any("gpt-4o" in m for m in model_ids)

    async def test_wizard_step4_key_entry_masked(self) -> None:
        """Pick model, assert Input(password=True) field visible."""
        app = OpenReviewApp()
        async with app.run_test(size=(80, 24)) as pilot:
            await app.push_screen(gw_mod.GatewayWizard())
            await pilot.pause()
            await self._go_to_step(pilot, app, 4)

            key_input = app.screen.query_one("#api-key-input")
            assert key_input.password is True

    async def test_wizard_skips_key_when_saved(self) -> None:
        """Mock has_key True, assert step 4 shows 'Using saved key'."""
        # Override patch for this test
        gw_mod.provider_has_key = lambda p: True  # type: ignore[method-assign]
        try:
            app = OpenReviewApp()
            async with app.run_test(size=(80, 24)) as pilot:
                await app.push_screen(gw_mod.GatewayWizard())
                await pilot.pause()
                await self._go_to_step(pilot, app, 4)

                body = app.screen.query_one("#wizard-body")
                texts = [str(c.content) for c in body.children if isinstance(c, Static)]
                combined = " ".join(texts).lower()
                assert "saved" in combined
        finally:
            gw_mod.provider_has_key = lambda p: False  # type: ignore[method-assign]

    async def test_wizard_saves_slot_config(self) -> None:
        """Complete wizard, assert save_slot_config was called."""
        mock_save = MagicMock()
        orig_save = gw_mod.save_slot_config
        orig_health = gw_mod.gateway_health_check
        gw_mod.save_slot_config = mock_save  # type: ignore[method-assign]
        gw_mod.gateway_health_check = lambda: MOCK_HEALTH_OK  # type: ignore[method-assign]
        try:
            app = OpenReviewApp()
            async with app.run_test(size=(80, 24)) as pilot:
                await app.push_screen(gw_mod.GatewayWizard())
                await pilot.pause()
                await self._go_to_step(pilot, app, 4)

                app.screen.query_one("#api-key-input").value = "sk-test-key-12345"
                await pilot.pause()

                await pilot.click("#wizard-next")
                await pilot.pause()

                mock_save.assert_called_once()
                args = mock_save.call_args
                slot, provider, model = args[0]
                assert slot in VALID_SLOTS
                assert provider == "openai"
        finally:
            gw_mod.save_slot_config = orig_save  # type: ignore[method-assign]
            gw_mod.gateway_health_check = orig_health  # type: ignore[method-assign]

    async def test_wizard_step2_shows_per_field_status(self) -> None:
        """T036 — FR-4 (TUI half): provider list renders per-field status.

        A multi-field provider's list item must expose each credential
        field's resolved flag (✓/✗), not just the provider name.
        """
        bedrock = {
            "name": "AWS Bedrock",
            "auth_required": True,
            "model_count": 0,
            "credentials": [
                {
                    "env_key": "AWS_REGION_NAME",
                    "label": "Region",
                    "resolved": True,
                    "secret": False,
                    "required": True,
                },
                {
                    "env_key": "AWS_ACCESS_KEY_ID",
                    "label": "Access Key ID",
                    "resolved": False,
                    "secret": True,
                    "required": True,
                },
                {
                    "env_key": "AWS_SECRET_ACCESS_KEY",
                    "label": "Secret Access Key",
                    "resolved": False,
                    "secret": True,
                    "required": True,
                },
            ],
        }
        gw_mod.list_providers = lambda: [bedrock]  # type: ignore[method-assign]

        app = OpenReviewApp()
        async with app.run_test(size=(80, 24)) as pilot:
            await app.push_screen(gw_mod.GatewayWizard())
            await pilot.pause()
            await pilot.click("#slot-list ListItem")
            await pilot.pause()
            await pilot.click("#wizard-next")
            await pilot.pause()

            provider_list = app.screen.query_one("#provider-list")
            labels: dict[str, str] = {}
            for child in provider_list.children:
                c = child.children[0] if child.children else None
                txt = str(c.content) if hasattr(c, "content") else ""
                labels[child.name or ""] = txt

            assert "AWS Bedrock" in labels
            assert "✓" in labels["AWS Bedrock"], labels["AWS Bedrock"]
            assert "✗" in labels["AWS Bedrock"], labels["AWS Bedrock"]


class TestGatewayWizardExtended:
    """T027a — Paste into masked field test."""

    async def test_wizard_paste_into_masked_field(self) -> None:
        """Set masked Input value via Pilot, assert field accepts value."""
        app = OpenReviewApp()
        async with app.run_test(size=(80, 24)) as pilot:
            await app.push_screen(gw_mod.GatewayWizard())
            await pilot.pause()

            # Navigate to step 4
            await pilot.click("#slot-list ListItem")
            await pilot.pause()
            await pilot.click("#wizard-next")
            await pilot.pause()
            await pilot.click("#provider-list ListItem")
            await pilot.pause()
            await pilot.click("#wizard-next")
            await pilot.pause()
            await pilot.click("#model-list ListItem")
            await pilot.pause()
            await pilot.click("#wizard-next")
            await pilot.pause()

            key_input = app.screen.query_one("#api-key-input")
            pasted = "sk-pasted-key-abcdef123456"
            key_input.value = pasted
            await pilot.pause()

            assert key_input.value == pasted


# Need Static for type checks in test_wizard_skips_key_when_saved
from textual.widgets import Static
