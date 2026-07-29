from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import questionary

from openreview_cli.config.auth import load_auth
from openreview_cli.config.paths import get_config_dir
from openreview_cli.gateway.models import CredentialField
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


def _write_auth(path: Path, data: dict[str, Any]) -> None:
    from openreview_cli.config.auth import write_auth

    write_auth(path, data)


def _collect_provider_credentials(creds: list[CredentialField]) -> dict[str, str] | None:
    """Prompt the user for each declared credential field.

    Returns the collected dict, or None if the user aborts (None answer) or
    supplies an unreadable file path for an is_file_path field.
    """
    collected: dict[str, str] = {}
    for field in creds:
        prompt = (
            questionary.password(f"{field.label}:")
            if field.secret
            else questionary.text(f"{field.label}:")
        )
        value = prompt.ask()
        if value is None or (field.required and value == ""):
            questionary.print(f"{field.label} is required.", style="fg:red")
            return None
        if field.is_file_path and not (
            os.path.isfile(value) and os.access(value, os.R_OK) and os.path.getsize(value) > 0
        ):
            questionary.print(f"File empty or not readable, skipping: {value}", style="fg:red")
            return None
        collected[field.env_key] = value
    return collected or None


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
            creds = info.get("credentials", []) if info else []
            if creds:
                collected = _collect_provider_credentials(creds)
                if collected:
                    auth[provider] = collected
            else:
                env_key = info["env_key"] if info else None
                if env_key and provider not in auth:
                    key = questionary.password(f"Enter your {provider} API key:").ask()
                    if key:
                        auth[provider] = key

    _write_auth(auth_path, auth)
    print("Gateway setup complete. Configuration saved.")
