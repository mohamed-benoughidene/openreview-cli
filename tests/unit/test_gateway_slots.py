"""Spec 035 T1.3 — the three-slot surface (plan T1.3).

Six slots shipped; three of them (``embedding``, ``reranking``, ``graph``) had
no caller. These tests pin the reduced contract so a removed socket cannot come
back unnoticed, in the slot sets, the wizard, the settings tab, the router
transport surface and the bundled model registry.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openreview_cli.slots import VALID_SLOTS

REMOVED_SLOTS = {"embedding", "reranking", "graph"}
REMAINING_SLOTS = {"extraction", "reasoning", "grounding"}
MODELS_JSON = Path(__file__).parent.parent.parent / "src/openreview_cli/gateway/models.json"


def test_valid_slots_are_the_three_remaining() -> None:
    assert set(VALID_SLOTS) == REMAINING_SLOTS


def test_removed_slots_are_absent() -> None:
    assert REMOVED_SLOTS.isdisjoint(VALID_SLOTS)


def test_wizard_offers_the_three_slots() -> None:
    from openreview_cli.gateway.wizard import SLOT_NAMES

    assert set(SLOT_NAMES) == REMAINING_SLOTS
    assert len(SLOT_NAMES) == 3


def test_settings_tab_renders_the_three_slots() -> None:
    from openreview_cli.tui.tabs.settings import SLOT_ORDER

    assert set(SLOT_ORDER) == REMAINING_SLOTS


def test_router_exposes_no_removed_transport() -> None:
    from openreview_cli.gateway.router import Gateway

    assert not hasattr(Gateway, "embed")
    assert not hasattr(Gateway, "rerank")


def test_router_has_no_slot_method_map() -> None:
    from openreview_cli.gateway import router

    assert not hasattr(router, "_SLOT_METHOD_MAP")


def test_registry_declares_only_remaining_slots() -> None:
    from openreview_cli.gateway.registry import load_registry

    registry = load_registry()
    assert registry, "bundled registry failed to load"
    for provider_name, provider in registry.items():
        for model_id, entry in provider.models.items():
            unknown = set(entry.slots) - REMAINING_SLOTS
            assert not unknown, f"{provider_name}/{model_id} declares removed slots {unknown}"


def test_models_json_drops_removed_slots_and_capability_flags() -> None:
    raw = MODELS_JSON.read_text()
    data = json.loads(raw)
    assert "qwen3-reranker-0.6b" not in raw, "bundled reranker entry still present"
    for provider_name, provider in data["providers"].items():
        capabilities = provider["capabilities"]
        assert "embedding" not in capabilities, (
            f"{provider_name} still declares an embedding capability flag"
        )
        assert "rerank" not in capabilities, (
            f"{provider_name} still declares a rerank capability flag"
        )
        for model_id, entry in provider["models"].items():
            assert set(entry["slots"]) <= REMAINING_SLOTS, (
                f"{provider_name}/{model_id} slots {entry['slots']} name a removed slot"
            )


def test_discovered_ollama_models_declare_only_remaining_slots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``discover_ollama`` synthesises entries too, and must not name a dead socket.

    ``app.gateway_models`` copies each discovered entry's ``slots`` straight into
    the displayed ``ModelEntry``, so a hard-coded removed socket here would leak
    back onto the ``gateway models ollama`` surface.
    """
    from openreview_cli.gateway import registry

    class _Resp:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict[str, object]:
            return {"models": [{"name": "granite4:3b", "details": {"parameter_size": "3B"}}]}

    import httpx

    monkeypatch.setattr(httpx, "get", lambda *a, **k: _Resp())

    entries = registry.discover_ollama(base_url="http://localhost:11434")
    assert entries, "expected the stub Ollama server to yield one model"
    for entry in entries:
        unknown = set(entry["slots"]) - REMAINING_SLOTS
        assert not unknown, f"{entry['model_id']} declares removed slots {unknown}"
