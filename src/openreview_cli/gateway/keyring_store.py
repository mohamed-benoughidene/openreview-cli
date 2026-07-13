"""OS keyring integration with file fallback for API key storage.

Provides get/set/delete/list operations for provider API keys.
When the ``keyring`` library is installed and the system keyring is
accessible, keys are stored in the OS keyring. Otherwise they fall back
to ``auth.json`` with chmod 600.

The ``auth.json`` file is always used as a lightweight index. When a key
is stored in the OS keyring, ``auth.json`` contains a ``kr:{last4}``
sentinel instead of the full key value.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from openreview_cli.config.auth import AUTH_FILENAME, _set_secure_permissions
from openreview_cli.config.paths import get_config_dir

logger = logging.getLogger(__name__)

_KEYRING_AVAILABLE: bool | None = None
_KEYRING_MODULE = None  # Cache the keyring module reference
_WARNING_ISSUED: bool = False

KEYRING_PREFIX = "kr:"
BASE_URL_SUFFIX = ":base_url"


def _is_keyring_available() -> bool:
    """Check whether the ``keyring`` library is importable.

    Result is cached at module level. Call ``_reset_keyring_cache()``
    to force a re-check (useful in tests).
    """
    global _KEYRING_AVAILABLE, _KEYRING_MODULE  # noqa: PLW0603
    if _KEYRING_AVAILABLE is not None:
        return _KEYRING_AVAILABLE
    try:
        import keyring  # type: ignore[import-not-found]

        _KEYRING_MODULE = keyring
        _KEYRING_AVAILABLE = True
    except ImportError:
        _KEYRING_AVAILABLE = False
    return _KEYRING_AVAILABLE


def _reset_keyring_cache() -> None:
    """Reset the keyring-availability cache.

    Intended for testing — forces a fresh import check on the next call.
    """
    global _KEYRING_AVAILABLE, _KEYRING_MODULE  # noqa: PLW0603
    _KEYRING_AVAILABLE = None
    _KEYRING_MODULE = None


def _warn_fallback() -> None:
    """Print a one-time warning about keyring fallback to stderr."""
    global _WARNING_ISSUED  # noqa: PLW0603
    if _WARNING_ISSUED:
        return
    _WARNING_ISSUED = True
    print(
        "OS keyring unavailable. Falling back to auth.json (chmod 600). "
        "Install `pip install openreview-cli[auth]` for secure key storage.",
        file=sys.stderr,
    )


def _auth_path() -> Path:
    return get_config_dir() / AUTH_FILENAME


def _load_auth_json() -> dict[str, str]:
    path = _auth_path()
    if not path.exists():
        return {}
    return dict(json.loads(path.read_text()))


def _save_auth_json(data: dict[str, str]) -> None:
    path = _auth_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")
    _set_secure_permissions(path)


def get_key(provider: str) -> str | None:
    """Retrieve the API key for *provider*.

    If the key was stored in the OS keyring and the keyring is available,
    the actual key value is fetched from the keyring. Otherwise the
    ``auth.json`` value is returned directly.
    """
    auth = _load_auth_json()
    entry = auth.get(provider)
    if entry is None:
        return None

    # Key stored in OS keyring — fetch the real value
    if entry.startswith(KEYRING_PREFIX):
        if _is_keyring_available() and _KEYRING_MODULE is not None:
            try:
                return _KEYRING_MODULE.get_password("openreview", provider)  # type: ignore[no-any-return]
            except Exception:
                logger.debug(
                    "keyring.get_password(%s) failed",
                    provider,
                    exc_info=True,
                )
                return None
        # Keyring was available when stored but isn't now — key lost
        return None

    return entry


def set_key(provider: str, key: str) -> None:
    """Store an API key for *provider*.

    When the OS keyring is available the key is stored there and a
    ``kr:`` sentinel (with last-4) is written to ``auth.json``. When
    the keyring is unavailable the full key goes into ``auth.json``
    and a one-time warning is printed.
    """
    auth = _load_auth_json()

    if _is_keyring_available() and _KEYRING_MODULE is not None:
        _KEYRING_MODULE.set_password("openreview", provider, key)
        auth[provider] = f"{KEYRING_PREFIX}{key[-4:]}"
    else:
        _warn_fallback()
        auth[provider] = key

    _save_auth_json(auth)


def delete_key(provider: str) -> None:
    """Delete the API key for *provider* from whichever store it lives in.

    Also removes any stored base URL for this provider.
    """
    auth = _load_auth_json()
    entry = auth.pop(provider, None)
    auth.pop(f"{provider}{BASE_URL_SUFFIX}", None)  # remove base_url if present

    if (
        entry
        and entry.startswith(KEYRING_PREFIX)
        and _is_keyring_available()
        and _KEYRING_MODULE is not None
    ):
        try:
            _KEYRING_MODULE.delete_password("openreview", provider)
        except Exception:
            logger.debug(
                "keyring.delete_password(%s) failed (may not exist)",
                provider,
                exc_info=True,
            )

    _save_auth_json(auth)


def list_providers() -> list[dict[str, str]]:
    """List all configured providers with key metadata and optional base URL.

    Returns a list of dicts, each with keys:
      - ``provider``: provider name
      - ``last_4``: last 4 characters of the API key
      - ``source``: ``"keyring"`` or ``"file"``
      - ``base_url``: custom base URL (only present if configured)
    """
    auth = _load_auth_json()
    result: list[dict[str, str]] = []

    for provider, entry in auth.items():
        if provider.endswith(BASE_URL_SUFFIX):
            continue  # skip base_url entries, handled below
        base_url_key = f"{provider}{BASE_URL_SUFFIX}"

        if entry.startswith(KEYRING_PREFIX):
            item: dict[str, str] = {
                "provider": provider,
                "last_4": entry[len(KEYRING_PREFIX) :],
                "source": "keyring",
            }
        else:
            item = {
                "provider": provider,
                "last_4": entry[-4:] if len(entry) >= 4 else entry,
                "source": "file",
            }
        if base_url_key in auth:
            item["base_url"] = auth[base_url_key]
        result.append(item)

    return result


def save_base_url(provider: str, base_url: str) -> None:
    """Store a custom base URL for *provider* in auth.json.

    The URL is stored as a ``{provider}:base_url`` sentinel key alongside
    the provider's key entry.
    """
    auth = _load_auth_json()
    auth[f"{provider}{BASE_URL_SUFFIX}"] = base_url
    _save_auth_json(auth)


def get_base_url(provider: str) -> str | None:
    """Retrieve the custom base URL for *provider*, or ``None``."""
    auth = _load_auth_json()
    return auth.get(f"{provider}{BASE_URL_SUFFIX}")
