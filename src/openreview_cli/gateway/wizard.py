from __future__ import annotations

import json
from pathlib import Path

import questionary

from openreview_cli.config.auth import _set_secure_permissions, load_auth
from openreview_cli.config.paths import get_config_dir
from openreview_cli.gateway.registry import ModelRegistry

SLOT_NAMES = ["reasoning", "extraction", "embedding", "reranking", "graph"]
PROVIDER_CHOICES = [
    "ollama",
    "openai",
    "anthropic",
    "google",
    "openrouter",
    "cohere",
    "huggingface",
    "custom",
]


def _write_auth(path: Path, data: dict[str, str]) -> None:
    path.write_text(json.dumps(data, indent=2))
    _set_secure_permissions(path)


def gateway_setup() -> None:
    from openreview_cli.config.loader import set_config_value

    config_dir = get_config_dir()
    config_path = config_dir / "config.yml"
    auth_path = config_dir / "auth.json"
    registry_path = Path(__file__).parent / "models.json"
    registry = ModelRegistry(registry_path)
    registry.load()

    auth = load_auth(auth_path)

    for slot in SLOT_NAMES:
        provider = questionary.select(
            f"Provider for '{slot}' slot:",
            choices=PROVIDER_CHOICES,
        ).ask()
        if not provider:
            return

        models = registry.list_models(provider)
        model_ids = [m["model_id"] for m in models]
        if not model_ids:
            model_id = questionary.text(f"Model identifier for '{slot}':").ask()
        else:
            model_id = questionary.select(
                f"Model for '{slot}':",
                choices=[*model_ids, "[custom]"],
            ).ask()
            if model_id == "[custom]":
                model_id = questionary.text(f"Model identifier for '{slot}':").ask()

        if not model_id:
            return

        set_config_value(config_path, f"gateway.models.{slot}.primary", model_id)

        if provider not in ("ollama",):
            info = next(
                (p for p in registry.list_providers() if p["name"].lower() == provider), None
            )
            env_key = info["env_key"] if info else None
            if env_key and provider not in auth:
                key = questionary.password(f"Enter your {provider} API key:").ask()
                if key:
                    auth[provider] = key

    _write_auth(auth_path, auth)
    print("Gateway setup complete. Configuration saved.")
