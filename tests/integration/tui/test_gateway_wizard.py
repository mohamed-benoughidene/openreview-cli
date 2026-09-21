"""Integration tests for gateway setup wizard (T027, T027a)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from textual.widgets import Input, ListView, Static

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
        "get_slot_configs",
        "save_slot_fallback",
    ):
        _originals[name] = getattr(gw_mod, name)
    gw_mod.list_providers = lambda: MOCK_PROVIDERS  # type: ignore[method-assign]
    gw_mod.list_models = lambda p: MOCK_MODELS.get(p, [])  # type: ignore[method-assign]
    gw_mod.provider_has_key = lambda p: False  # type: ignore[method-assign]
    gw_mod.save_slot_config = lambda s, p, m: None  # type: ignore[method-assign]
    gw_mod.save_api_key = lambda p, k: None  # type: ignore[method-assign]
    gw_mod.gateway_health_check = lambda: MOCK_HEALTH  # type: ignore[method-assign]
    gw_mod.get_slot_configs = lambda: {}  # type: ignore[method-assign]
    gw_mod.save_slot_fallback = lambda slot, model: None  # type: ignore[method-assign]


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

                # Set internal state and call _do_save directly — avoids
                # ListView selection + button click timing races in CI.
                wizard: gw_mod.GatewayWizard = app.screen  # type: ignore[assignment]
                wizard._slot = "extraction"
                wizard._provider = "openai"
                wizard._model = "gpt-4o"
                wizard._key = "sk-test-key-12345"
                wizard._do_save()
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


class TestGatewayWizardFallback:
    """Gap #1 — optional per-slot backup model on the model step."""

    async def _select_reasoning_and_reach_step3(self, pilot, wizard) -> None:
        """Select the ``reasoning`` chat slot by index, then reach step 3.

        The slot list is ``sorted(VALID_SLOTS)`` so ``embedding`` is item 0; the
        index is set explicitly and ``focus()`` is called before Enter because
        the nav (#wizard-cancel) is composed first and would otherwise receive
        the keypress and dismiss the screen.
        """
        slot_list = wizard.query_one("#slot-list", ListView)
        slot_list.index = sorted(VALID_SLOTS).index("reasoning")
        await pilot.pause()
        slot_list.focus()
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.click("#wizard-next")
        await pilot.pause()
        await pilot.click("#provider-list ListItem")
        await pilot.pause()
        await pilot.click("#wizard-next")
        await pilot.pause()

    async def test_wizard_offers_fallback_for_chat_slot(self) -> None:
        app = OpenReviewApp()
        async with app.run_test(size=(80, 24)) as pilot:
            wizard = gw_mod.GatewayWizard()
            await app.push_screen(wizard)
            await pilot.pause()
            await self._select_reasoning_and_reach_step3(pilot, wizard)

            assert wizard._slot == "reasoning"
            assert wizard.query("#fallback-input")

    async def test_wizard_hides_fallback_for_primary_only_slots(self) -> None:
        """The default path clicks the first slot item, i.e. ``embedding``.

        ``_render_slot_step`` mounts ``sorted(VALID_SLOTS)`` so the first
        ``#slot-list`` item is ``embedding``, a primary-only slot with no
        backup model.
        """
        app = OpenReviewApp()
        async with app.run_test(size=(80, 24)) as pilot:
            wizard = gw_mod.GatewayWizard()
            await app.push_screen(wizard)
            await pilot.pause()
            await pilot.click("#slot-list ListItem")
            await pilot.pause()
            await pilot.click("#wizard-next")
            await pilot.pause()
            await pilot.click("#provider-list ListItem")
            await pilot.pause()
            await pilot.click("#wizard-next")
            await pilot.pause()

            assert wizard._slot == "embedding"
            assert list(wizard.query("#fallback-input")) == []

    async def test_wizard_prefills_existing_fallback(self) -> None:
        gw_mod.get_slot_configs = lambda: {  # type: ignore[method-assign]
            "reasoning": {
                "provider": "anthropic",
                "model": "claude-3-5-haiku",
                "configured": True,
                "fallback": "anthropic/claude-3-5-haiku",
            }
        }
        app = OpenReviewApp()
        async with app.run_test(size=(80, 24)) as pilot:
            wizard = gw_mod.GatewayWizard()
            await app.push_screen(wizard)
            await pilot.pause()
            wizard._slot = "reasoning"
            wizard._provider = "anthropic"
            wizard._show_step(3)
            await pilot.pause()

            assert wizard.query_one("#fallback-input", Input).value == "anthropic/claude-3-5-haiku"

    async def test_wizard_saves_fallback(self) -> None:
        mock_fallback = MagicMock()
        gw_mod.save_slot_fallback = mock_fallback  # type: ignore[method-assign]
        gw_mod.gateway_health_check = lambda: MOCK_HEALTH_OK  # type: ignore[method-assign]
        app = OpenReviewApp()
        async with app.run_test(size=(80, 24)) as pilot:
            wizard = gw_mod.GatewayWizard()
            await app.push_screen(wizard)
            await pilot.pause()
            wizard._slot = "extraction"
            wizard._provider = "openai"
            wizard._model = "gpt-4o"
            wizard._fallback = "anthropic/haiku"
            wizard._do_save()
            await pilot.pause()

        mock_fallback.assert_called_once_with("extraction", "anthropic/haiku")

    async def test_wizard_clears_fallback_when_blank(self) -> None:
        mock_fallback = MagicMock()
        gw_mod.save_slot_fallback = mock_fallback  # type: ignore[method-assign]
        gw_mod.gateway_health_check = lambda: MOCK_HEALTH_OK  # type: ignore[method-assign]
        app = OpenReviewApp()
        async with app.run_test(size=(80, 24)) as pilot:
            wizard = gw_mod.GatewayWizard()
            await app.push_screen(wizard)
            await pilot.pause()
            wizard._slot = "extraction"
            wizard._provider = "openai"
            wizard._model = "gpt-4o"
            wizard._fallback = ""
            wizard._do_save()
            await pilot.pause()

        mock_fallback.assert_called_once_with("extraction", None)

    async def test_wizard_keeps_prefilled_fallback_when_unchanged(self) -> None:
        """Regression guard: an unchanged pre-filled backup must not be cleared."""
        gw_mod.get_slot_configs = lambda: {  # type: ignore[method-assign]
            "extraction": {
                "provider": "anthropic",
                "model": "claude-3-5-haiku",
                "configured": True,
                "fallback": "anthropic/claude-3-5-haiku",
            }
        }
        mock_fallback = MagicMock()
        gw_mod.save_slot_fallback = mock_fallback  # type: ignore[method-assign]
        gw_mod.gateway_health_check = lambda: MOCK_HEALTH_OK  # type: ignore[method-assign]
        app = OpenReviewApp()
        async with app.run_test(size=(80, 24)) as pilot:
            wizard = gw_mod.GatewayWizard()
            await app.push_screen(wizard)
            await pilot.pause()
            wizard._slot = "extraction"
            wizard._provider = "anthropic"
            wizard._model = "claude-3-5-haiku"
            wizard._show_step(3)
            await pilot.pause()
            wizard._do_save()
            await pilot.pause()

        mock_fallback.assert_called_once_with("extraction", "anthropic/claude-3-5-haiku")
