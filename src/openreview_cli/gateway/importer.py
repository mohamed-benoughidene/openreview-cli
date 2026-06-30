import contextlib
import json
import os
import re
from pathlib import Path
from typing import Any

import yaml

from openreview_cli.gateway.utils import atomic_write

SUPPORTED_PROVIDERS = {
    "openai",
    "anthropic",
    "google",
    "ollama",
    "openrouter",
    "cohere",
    "huggingface",
    "custom",
}
REQUIRED_SLOTS = {"reasoning", "extraction", "embedding", "graph"}
ENV_VAR_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _validate_slot_config(slot: str, slot_data: Any) -> list[str]:
    """Helper to validate individual slot configurations."""
    errors = []
    if not isinstance(slot_data, dict):
        return [f"Slot '{slot}' must be an object."]

    provider = slot_data.get("provider")
    if not provider or not isinstance(provider, str):
        errors.append(f"Slot '{slot}' must specify a non-empty string 'provider'.")
    elif provider.lower() not in SUPPORTED_PROVIDERS:
        errors.append(
            f"Slot '{slot}' has unrecognized provider '{provider}'. Supported: "
            f"{', '.join(sorted(SUPPORTED_PROVIDERS))}"
        )

    model = slot_data.get("model")
    if not model or not isinstance(model, str):
        errors.append(f"Slot '{slot}' must specify a non-empty string 'model'.")

    fallback = slot_data.get("fallback")
    if fallback is not None:
        if not isinstance(fallback, str):
            errors.append(f"Slot '{slot}' fallback must be a string or null.")
        elif "/" not in fallback and not fallback.startswith("ollama/"):
            errors.append(
                f"Slot '{slot}' fallback model must be in format 'provider/model-id', got '{fallback}'."
            )

    params = slot_data.get("params")
    if params is not None and not isinstance(params, dict):
        errors.append(f"Slot '{slot}' params must be an object.")

    return errors


def _validate_api_key_env(api_key_env: Any) -> list[str]:
    """Helper to validate api_key_env configurations."""
    errors = []
    if not isinstance(api_key_env, dict):
        return ["api_key_env must be an object."]

    for prov, env_var in api_key_env.items():
        if prov.lower() not in SUPPORTED_PROVIDERS:
            errors.append(f"api_key_env has unrecognized provider '{prov}'.")
        if not isinstance(env_var, str):
            errors.append(f"Environment variable name for '{prov}' must be a string.")
            continue

        # Check for inline keys
        if any(env_var.startswith(prefix) for prefix in ["sk-", "AIza", "hf_"]):
            errors.append(
                f"api_key_env for '{prov}' contains an inline API key instead of an environment variable name."
            )
        elif not ENV_VAR_RE.match(env_var):
            errors.append(
                f"api_key_env for '{prov}' specifies an invalid environment variable name '{env_var}'."
            )
    return errors


def validate_import_config(config_dict: dict[str, Any]) -> list[str]:
    """Validate the imported configuration structure, reporting all errors at once."""
    errors = []

    if not isinstance(config_dict, dict):
        return ["Imported configuration must be an object/dictionary."]

    # Check required slots
    for slot in REQUIRED_SLOTS:
        if slot not in config_dict:
            errors.append(f"Missing required slot: '{slot}'")
        else:
            errors.extend(_validate_slot_config(slot, config_dict[slot]))

    # Optional reranking slot
    if "reranking" in config_dict:
        errors.extend(_validate_slot_config("reranking", config_dict["reranking"]))

    # Check api_key_env
    api_key_env = config_dict.get("api_key_env")
    if api_key_env is not None:
        errors.extend(_validate_api_key_env(api_key_env))

    return errors


def _resolve_api_keys(api_key_env: dict[str, str]) -> dict[str, str]:
    """Resolve API keys from environment variables."""
    resolved_keys = {}
    missing_vars = []
    for prov, env_var in api_key_env.items():
        if env_var not in os.environ:
            missing_vars.append(
                f"Environment variable '{env_var}' for provider '{prov}' is not set."
            )
        else:
            resolved_keys[prov.lower()] = os.environ[env_var]
    if missing_vars:
        raise ValueError("\n".join(missing_vars))
    return resolved_keys


def _write_auth_keys(resolved_keys: dict[str, str], config_dir: Path) -> None:
    """Atomic write of resolved API keys to auth.json (chmod 600)."""
    if not resolved_keys:
        return
    auth_path = config_dir / "auth.json"
    auth_data: dict[str, str] = {}
    if auth_path.exists():
        with contextlib.suppress(Exception):
            auth_data = json.loads(auth_path.read_text()) or {}

    for prov, key in resolved_keys.items():
        auth_data[prov] = key

    auth_str = json.dumps(auth_data, indent=2)
    atomic_write(auth_path, auth_str)
    with contextlib.suppress(Exception):
        auth_path.chmod(0o600)


def import_config(config_dict: dict[str, Any], config_dir: Path) -> dict[str, Any]:
    """Validate, resolve env vars, and atomically write gateway configuration."""
    errors = validate_import_config(config_dict)
    if errors:
        raise ValueError("\n".join(errors))

    # Resolve environment variables if api_key_env is present
    api_key_env = config_dict.get("api_key_env")
    resolved_keys = {}
    if api_key_env:
        resolved_keys = _resolve_api_keys(api_key_env)

    # Read existing config.yml
    config_path = config_dir / "config.yml"
    config_data: dict[str, Any] = {}
    if config_path.exists():
        with contextlib.suppress(Exception):
            config_data = yaml.safe_load(config_path.read_text()) or {}

    if "gateway" not in config_data:
        config_data["gateway"] = {}
    if "models" not in config_data["gateway"]:
        config_data["gateway"]["models"] = {}

    # Map and update slot configurations
    for slot in REQUIRED_SLOTS:
        slot_import = config_dict[slot]
        provider = slot_import["provider"]
        model = slot_import["model"]

        slot_conf = {
            "primary": f"{provider}/{model}",
            "fallback": slot_import.get("fallback"),
            "params": slot_import.get("params") or {},
        }
        config_data["gateway"]["models"][slot] = slot_conf

    # Optional reranking slot
    if "reranking" in config_dict:
        ri = config_dict["reranking"]
        config_data["gateway"]["models"]["reranking"] = {
            "primary": f"{ri['provider']}/{ri['model']}",
            "fallback": ri.get("fallback"),
            "params": ri.get("params") or {},
        }

    # Write config.yml atomically
    yaml_str = yaml.safe_dump(config_data, default_flow_style=False)
    atomic_write(config_path, yaml_str)

    # Write resolved API keys to auth.json atomically (chmod 600)
    _write_auth_keys(resolved_keys, config_dir)

    # Return summary of slot assignments
    summary = {}
    for slot in sorted(REQUIRED_SLOTS):
        slot_import = config_dict[slot]
        summary[slot] = f"{slot_import['provider']}/{slot_import['model']}"
    if "reranking" in config_dict:
        summary["reranking"] = f"{config_dict['reranking']['provider']}/{config_dict['reranking']['model']}"
    return summary
