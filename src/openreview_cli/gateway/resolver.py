"""Short-name model resolver for the AI Gateway.

Resolves short model names (e.g. ``gpt-4o``, ``sonnet``) to full
``provider/model`` strings using the static ``models.json`` registry
and the user's configured providers.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openreview_cli.gateway.errors import ProviderNotConfiguredError, UnknownModelError

__all__ = [
    "ProviderNotConfiguredError",
    "ResolvedModel",
    "UnknownModelError",
    "resolve",
]

# ── Public model ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ResolvedModel:
    """Result of a successful model resolution."""

    provider: str
    model: str

    @property
    def full(self) -> str:
        """Full ``provider/model`` string (e.g. ``openai/gpt-4o``)."""
        return f"{self.provider}/{self.model}"


# ── Provider priority (direct first, then proxies) ──────────────────────────

_PROVIDER_PRIORITY: list[str] = [
    "openai",
    "anthropic",
    "google",
    "cohere",
    "huggingface",
    "voyage",
    "ollama",
    "openrouter",
    "custom",
]


def _get_priority(provider: str) -> int:
    try:
        return _PROVIDER_PRIORITY.index(provider.lower())
    except ValueError:
        return len(_PROVIDER_PRIORITY)


# ── Alias map ────────────────────────────────────────────────────────────────

_ALIASES: dict[str, str] = {
    "sonnet": "claude-sonnet-latest",
    "haiku": "claude-haiku-latest",
    "gpt4": "gpt-4o",
    "gpt4o": "gpt-4o",
    "claude-sonnet": "claude-sonnet-latest",
    "claude-haiku": "claude-haiku-latest",
    "gemini-flash": "gemini-2.0-flash",
    "embed-small": "text-embedding-3-small",
}


# ── Registry loader ──────────────────────────────────────────────────────────


def _load_registry(
    registry_path: Path | None = None,
) -> dict[str, dict[str, dict[str, Any]]]:
    """Load ``models.json`` and return ``{provider: {model_id: entry}}``."""
    if registry_path is None:
        registry_path = Path(__file__).parent / "models.json"

    if not registry_path.exists():
        return {}

    with open(registry_path) as f:
        raw = json.load(f)

    providers_raw = raw.get("providers", {})
    result: dict[str, dict[str, dict[str, Any]]] = {}
    for name, info in providers_raw.items():
        result[name] = dict(info.get("models", {}))
    return result


# ── Reverse index ────────────────────────────────────────────────────────────


def _build_shortname_index(
    registry: dict[str, dict[str, dict[str, Any]]],
) -> dict[str, list[tuple[str, str]]]:
    """Build ``short_name → [(provider, model_id), ...]`` index.

    For direct providers the model ID *is* the short name.
    For proxy providers (e.g. OpenRouter) the model ID is
    ``openai/gpt-4o`` — both the full ID and its suffix (``gpt-4o``)
    are registered in the index so that short-name lookup works.
    """
    index: dict[str, list[tuple[str, str]]] = {}
    for prov_name, models in registry.items():
        for model_id in models:
            # Direct match
            index.setdefault(model_id, []).append((prov_name, model_id))
            # Suffix match for proxy providers
            if "/" in model_id:
                suffix = model_id.split("/", 1)[1]
                if suffix != model_id:
                    # Avoid duplicating if suffix is already registered
                    existing = index.setdefault(suffix, [])
                    if (prov_name, model_id) not in existing:
                        existing.append((prov_name, model_id))
    return index


# ── Main resolve function ────────────────────────────────────────────────────


def resolve(
    short_or_full: str,
    configured_providers: list[str],
    registry_path: Path | None = None,
) -> ResolvedModel:
    """Resolve a short or explicit model string to a ``ResolvedModel``.

    Args:
        short_or_full:
            Model short name (e.g. ``"gpt-4o"``) or explicit
            ``"provider/model"``.
        configured_providers:
            List of provider names that the user has API keys for.
        registry_path:
            Path to ``models.json``.  Defaults to the bundled registry.

    Returns:
        A ``ResolvedModel`` with *provider* and *model* fields.

    Raises:
        UnknownModelError:
            The short name was not found in any provider's model list.
        ProviderNotConfiguredError:
            The model exists in the registry but none of the providers
            that serve it are in *configured_providers*.
    """
    # 1. Explicit ``provider/model`` — return as-is, no validation
    if "/" in short_or_full and not short_or_full.startswith("/"):
        parts = short_or_full.split("/", 1)
        return ResolvedModel(provider=parts[0], model=parts[1])

    # 2. Apply alias map
    short_name = _ALIASES.get(short_or_full, short_or_full)

    # 3. Build reverse index from registry
    registry = _load_registry(registry_path)
    index = _build_shortname_index(registry)

    # 4. Find all candidates
    candidates = index.get(short_name, [])
    if not candidates:
        raise UnknownModelError(
            f"Unknown model '{short_or_full}'. "
            f"Check ``openreview models available`` for a list of "
            f"reachable models."
        )

    # 5. Filter to configured providers
    configured_lower = {p.lower() for p in configured_providers}
    available = [
        (prov, model_id) for prov, model_id in candidates if prov.lower() in configured_lower
    ]

    if not available:
        # Build a helpful error message with the providers that offer it
        offering = sorted({p for p, _ in candidates})
        raise ProviderNotConfiguredError(
            f"No configured provider has model '{short_or_full}'. "
            f"Providers that offer this model: {', '.join(offering)}. "
            f"Add an API key for one of these providers, or use "
            f"``openreview models available`` to see reachable models."
        )

    # 6. Prefer highest-priority provider
    available.sort(key=lambda x: _get_priority(x[0]))
    best_provider, best_model_id = available[0]

    return ResolvedModel(provider=best_provider, model=best_model_id)
