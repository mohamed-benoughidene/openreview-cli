"""Unit tests for short-name model resolver (T026-T028)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from openreview_cli.gateway.errors import ProviderNotConfiguredError, UnknownModelError
from openreview_cli.gateway.resolver import resolve


class TestShortNameResolution:
    """T026-T028: short-name model resolution."""

    def _make_registry(self, tmp_path: Path, data: dict[str, Any] | None = None) -> Path:
        """Write a test models.json and return its path."""
        if data is None:
            data = {
                "providers": {
                    "openai": {
                        "name": "OpenAI",
                        "env_key": "OPENAI_API_KEY",
                        "auth_required": True,
                        "models": {
                            "gpt-4o": {
                                "slots": ["reasoning", "extraction"],
                                "context": 128000,
                                "recommended": True,
                                "status": "active",
                            },
                        },
                    },
                    "openrouter": {
                        "name": "OpenRouter",
                        "env_key": "OPENROUTER_API_KEY",
                        "auth_required": True,
                        "models": {
                            "openai/gpt-4o": {
                                "slots": ["reasoning", "extraction"],
                                "context": 128000,
                                "recommended": True,
                                "status": "active",
                                "note": "Routed through OpenRouter",
                            },
                        },
                    },
                },
            }
        reg_path = tmp_path / "models.json"
        reg_path.write_text(json.dumps(data))
        return reg_path

    def test_resolve_short_name_to_proxy_provider(self, tmp_path: Path) -> None:
        """T026: short name resolves to proxy when direct not configured."""
        reg_path = self._make_registry(tmp_path)

        result = resolve("gpt-4o", ["openrouter"], registry_path=reg_path)
        assert result.provider == "openrouter"
        assert result.model == "openai/gpt-4o"
        assert result.full == "openrouter/openai/gpt-4o"

    def test_resolve_direct_over_proxy(self, tmp_path: Path) -> None:
        """T027: when both direct and proxy configured, prefer direct."""
        reg_path = self._make_registry(tmp_path)

        result = resolve("gpt-4o", ["openai", "openrouter"], registry_path=reg_path)
        assert result.provider == "openai"
        assert result.model == "gpt-4o"
        assert result.full == "openai/gpt-4o"

    def test_explicit_provider_model_bypasses_resolution(self) -> None:
        """T028: explicit 'provider/model' returned as-is without resolution."""
        result = resolve("openai/gpt-4o", ["openrouter"])
        assert result.provider == "openai"
        assert result.model == "gpt-4o"
        assert result.full == "openai/gpt-4o"

    def test_unknown_model_raises_error(self, tmp_path: Path) -> None:
        """Unknown short name raises UnknownModelError."""
        reg_path = tmp_path / "models.json"
        reg_path.write_text(json.dumps({"providers": {}}))

        with pytest.raises(UnknownModelError):
            resolve("unknown-model", ["openai"], registry_path=reg_path)

    def test_model_found_but_not_configured(self, tmp_path: Path) -> None:
        """Model exists in registry but no configured provider serves it."""
        reg_path = self._make_registry(tmp_path)

        with pytest.raises(ProviderNotConfiguredError):
            resolve("gpt-4o", ["anthropic"], registry_path=reg_path)

    def test_alias_resolves_correctly(self, tmp_path: Path) -> None:
        """Short aliases like 'sonnet' resolve to canonical model."""
        data = {
            "providers": {
                "anthropic": {
                    "name": "Anthropic",
                    "env_key": "ANTHROPIC_API_KEY",
                    "auth_required": True,
                    "models": {
                        "claude-sonnet-latest": {
                            "slots": ["reasoning"],
                            "context": 200000,
                            "recommended": True,
                            "status": "active",
                        },
                    },
                },
            },
        }
        reg_path = self._make_registry(tmp_path, data)

        result = resolve("sonnet", ["anthropic"], registry_path=reg_path)
        assert result.provider == "anthropic"
        assert result.model == "claude-sonnet-latest"
        assert result.full == "anthropic/claude-sonnet-latest"

    def test_priority_order(self, tmp_path: Path) -> None:
        """Priority: openai > anthropic > google > groq > openrouter."""
        data = {
            "providers": {
                "openai": {
                    "name": "OpenAI",
                    "env_key": "OPENAI_API_KEY",
                    "auth_required": True,
                    "models": {
                        "gpt-4o": {
                            "slots": ["reasoning"],
                            "context": 128000,
                            "recommended": True,
                            "status": "active",
                        }
                    },
                },
                "anthropic": {
                    "name": "Anthropic",
                    "env_key": "ANTHROPIC_API_KEY",
                    "auth_required": True,
                    "models": {
                        "gpt-4o": {
                            "slots": ["reasoning"],
                            "context": 128000,
                            "recommended": True,
                            "status": "active",
                        }
                    },
                },
                "openrouter": {
                    "name": "OpenRouter",
                    "env_key": "OPENROUTER_API_KEY",
                    "auth_required": True,
                    "models": {
                        "openai/gpt-4o": {
                            "slots": ["reasoning"],
                            "context": 128000,
                            "recommended": True,
                            "status": "active",
                            "note": "",
                        }
                    },
                },
            },
        }
        reg_path = self._make_registry(tmp_path, data)

        # When both openai and anthropic have gpt-4o, prefer openai
        result = resolve("gpt-4o", ["anthropic", "openai"], registry_path=reg_path)
        assert result.provider == "openai"
