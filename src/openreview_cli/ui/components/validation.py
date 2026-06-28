"""Validation helpers returning ``(is_valid: bool, error: str | None)`` tuples.

All functions follow the same contract:
  - ``(True, None)`` when the input passes validation
  - ``(False, error_message)`` when it does not
"""

from __future__ import annotations

from pathlib import Path


def validate_path(path_str: str) -> tuple[bool, str | None]:
    """Check that *path_str* exists on the filesystem."""
    if not path_str:
        return False, "Path must not be empty"
    p = Path(path_str)
    if not p.exists():
        return False, f"Path does not exist: {path_str}"
    return True, None


def validate_config_key(key: str, known_keys: set[str]) -> tuple[bool, str | None]:
    """Check that *key* is one of the *known_keys*."""
    if key not in known_keys:
        return False, f"Unknown config key: {key}"
    return True, None


def validate_range(
    value: int | float, min_val: int | float, max_val: int | float
) -> tuple[bool, str | None]:
    """Check that *value* falls within [*min_val*, *max_val*] (inclusive)."""
    if value < min_val or value > max_val:
        return False, f"Value must be between {min_val} and {max_val}"
    return True, None


def validate_not_empty(value: str) -> tuple[bool, str | None]:
    """Check that *value* is non-empty and not whitespace-only."""
    if not value or not value.strip():
        return False, "Value must not be empty"
    return True, None


def validate_enum(value: str, allowed: list[str]) -> tuple[bool, str | None]:
    """Check that *value* matches one of the *allowed* strings
    (case-insensitive)."""
    for allowed_val in allowed:
        if value.lower() == allowed_val.lower():
            return True, None
    return False, f"Value must be one of: {', '.join(allowed)}"
