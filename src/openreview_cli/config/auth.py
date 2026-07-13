import json
import logging
import os
import platform
from pathlib import Path

logger = logging.getLogger(__name__)

AUTH_FILENAME = "auth.json"


def ensure_auth(auth_dir: Path) -> Path:
    path = auth_dir / AUTH_FILENAME
    if path.exists():
        _check_permissions(path)
        return path
    auth_dir.mkdir(parents=True, exist_ok=True)
    path.write_text("{}")
    _set_secure_permissions(path)
    logger.info("auth.json created at %s", path)
    return path


def load_auth(path: Path) -> dict[str, str]:
    data: dict[str, str] = json.loads(path.read_text())

    # Filter out :base_url sentinel keys (used by custom providers)
    data = {k: v for k, v in data.items() if not k.endswith(":base_url")}

    # Overlay keyring values (keyring > file per FR-018)
    for key in list(data.keys()):
        kr_val = _load_from_keyring(key)
        if kr_val is not None:
            data[key] = kr_val

    # Overlay env vars (env var > keyring > file per FR-018)
    for key in list(data.keys()):
        env_val = os.environ.get(key_to_env(key))
        if env_val:
            data[key] = env_val

    return data


def _load_from_keyring(provider: str) -> str | None:
    """Try to load a key from the OS keyring.

    Returns ``None`` if keyring is unavailable or no key is stored.
    """
    from openreview_cli.gateway.keyring_store import get_key

    return get_key(provider)


def key_to_env(key: str) -> str:
    mapping = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "cohere": "COHERE_API_KEY",
        "huggingface": "HUGGINGFACE_API_KEY",
        "google": "GOOGLE_API_KEY",
    }
    return mapping.get(key, f"{key.upper()}_API_KEY")


def _set_secure_permissions(path: Path) -> None:
    if platform.system() == "Windows":
        logger.warning("auth.json contains API keys. Ensure the file is stored securely.")
        return
    path.chmod(0o600)


def has_key(auth_path: Path, provider: str) -> bool:
    """Check if a provider has a saved API key."""
    try:
        auth = json.loads(auth_path.read_text())
        return provider in auth and bool(auth[provider])
    except (FileNotFoundError, json.JSONDecodeError):
        return False


def save_key(auth_path: Path, provider: str, key: str) -> None:
    """Save an API key for a provider to auth.json."""
    ensure_auth(auth_path.parent)
    auth = json.loads(auth_path.read_text())
    auth[provider] = key
    auth_path.write_text(json.dumps(auth, indent=2))
    _set_secure_permissions(auth_path)


def _check_permissions(path: Path) -> None:
    if platform.system() == "Windows":
        return
    current = path.stat().st_mode & 0o777
    if current != 0o600:
        logger.warning(
            "auth.json has insecure permissions (%s). Fixing...",
            oct(current),
        )
        path.chmod(0o600)
