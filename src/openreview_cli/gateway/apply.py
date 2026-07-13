from __future__ import annotations

import contextlib
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from openreview_cli.gateway.v2_config import ApiKeySource, V2Config

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _atomic_write(path: Path, content: str) -> None:
    """Write *content* to *path* atomically (temp-file + rename)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def apply_config(
    json_str: str,
    config_path: str | Path,
    auth_path: str | Path,
) -> dict[str, Any]:
    """Parse, validate and atomically apply a JSON gateway configuration.

    Args:
        json_str: Raw JSON string from stdin.
        config_path: Path for *config.yml*.
        auth_path: Path for *auth.json*.

    Returns:
        ``{"status": "ok", "providers": […], "slots": […]}`` on success.

    Raises:
        ValueError: Empty / whitespace-only input or Pydantic validation
            failure.
        json.JSONDecodeError: Malformed JSON.
    """
    # --- Empty / whitespace guard -------------------------------------------------
    if not json_str or not json_str.strip():
        raise ValueError(
            "No config provided on stdin. Run `openreview gateway setup --help` for usage."
        )

    config_path = Path(config_path)
    auth_path = Path(auth_path)

    # --- JSON parse ---------------------------------------------------------------
    try:
        raw: dict[str, Any] = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(
            f"Parse error at line {e.lineno}, column {e.colno}: {e.msg}",
            e.doc,
            e.pos,
        ) from e

    # --- Validate against V2Config ------------------------------------------------
    try:
        config = V2Config(**raw)
    except ValidationError as e:
        lines = ["Config validation failed."]
        for err in e.errors():
            loc = ".".join(str(p) for p in err["loc"])
            lines.append(f"  - {loc}: {err['msg']}")
        raise ValueError("\n".join(lines)) from e

    # --- Extract file-sourced API keys from convenience ``api_key`` field ---------
    auth_entries: dict[str, str] = {}
    providers_raw: dict[str, Any] = raw.get("providers", {})
    for pname in config.providers:
        prov = config.providers[pname]
        if prov.api_key_source == ApiKeySource.FILE:
            api_key: str | None = providers_raw.get(pname, {}).get("api_key")
            if api_key:
                auth_entries[pname] = api_key

    # --- Atomic write: config.yml (YAML) -----------------------------------------
    config_dict = config.model_dump(mode="json", exclude_none=False)
    yaml_out = yaml.safe_dump(
        config_dict,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
    )
    _atomic_write(config_path, yaml_out)

    # --- Atomic write: auth.json (merge with existing) ----------------------------
    if auth_entries:
        existing: dict[str, str] = {}
        if auth_path.exists():
            existing = json.loads(auth_path.read_text())
        existing.update(auth_entries)
        _atomic_write(auth_path, json.dumps(existing, indent=2))
        if os.name != "nt":
            os.chmod(auth_path, 0o600)

    return {
        "status": "ok",
        "providers": list(config.providers.keys()),
        "slots": list(config.slots.keys()),
    }


def apply_config_with_dry_run(json_str: str) -> dict[str, Any]:
    """Validate JSON and report what *would* be written (no file I/O).

    Args:
        json_str: Raw JSON string from stdin.

    Returns:
        ``{"status": "ok", "providers": […], "slots": […], "dry_run": True}``

    Raises:
        ValueError: Empty / whitespace-only input or Pydantic validation
            failure.
        json.JSONDecodeError: Malformed JSON.
    """
    if not json_str or not json_str.strip():
        raise ValueError(
            "No config provided on stdin. Run `openreview gateway setup --help` for usage."
        )

    raw: dict[str, Any] = json.loads(json_str)

    try:
        config = V2Config(**raw)
    except ValidationError as e:
        lines = ["Config validation failed."]
        for err in e.errors():
            loc = ".".join(str(p) for p in err["loc"])
            lines.append(f"  - {loc}: {err['msg']}")
        raise ValueError("\n".join(lines)) from e

    return {
        "status": "ok",
        "providers": list(config.providers.keys()),
        "slots": list(config.slots.keys()),
        "dry_run": True,
    }
