"""Playbook loader — YAML parsing, validation, bundled load."""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

import yaml

from openreview_cli.review.models import (
    Category,
    Playbook,
    PlaybookMetadata,
    Position,
    PositionDef,
)

BUNDLED_PLAYBOOK_PATH = Path(__file__).parent / "playbooks" / "precheck-nda-v1.yaml"


class PlaybookLoadError(ValueError):
    """Raised when a playbook cannot be loaded or validated."""


def load_bundled() -> Playbook:
    """Load the bundled NDA playbook shipped with PreCheck mode."""
    return load_playbook(BUNDLED_PLAYBOOK_PATH)


def load_playbook(path: Path) -> Playbook:
    """Load and validate a YAML playbook from *path*."""
    if not path.exists():
        raise PlaybookLoadError(f"Playbook not found: {path}")

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise PlaybookLoadError(f"Invalid YAML in playbook: {exc}") from exc

    if not isinstance(raw, dict):
        raise PlaybookLoadError("Playbook must be a YAML mapping")

    return _parse_playbook(raw)


def _parse_playbook(raw: dict[str, Any]) -> Playbook:
    """Parse a validated YAML dict into a Playbook model."""
    required = {"id", "mode", "metadata", "categories"}
    missing = required - set(raw)
    if missing:
        raise PlaybookLoadError(f"Missing required fields: {', '.join(sorted(missing))}")

    meta_raw = raw["metadata"]
    if not isinstance(meta_raw, dict):
        raise PlaybookLoadError("'metadata' must be a mapping")
    for req in ("version", "description", "author"):
        if req not in meta_raw:
            raise PlaybookLoadError(f"metadata.{req} is required")

    metadata = PlaybookMetadata(
        version=str(meta_raw["version"]),
        description=str(meta_raw["description"]),
        author=str(meta_raw["author"]),
    )

    cats_raw = raw["categories"]
    if not isinstance(cats_raw, list):
        raise PlaybookLoadError("'categories' must be a list")
    if not cats_raw:
        raise PlaybookLoadError("'categories' must contain at least one entry")

    categories = [_parse_category(c) for c in cats_raw]

    return Playbook(
        id=str(raw["id"]),
        mode=str(raw["mode"]),
        categories=categories,
        metadata=metadata,
    )


LEGACY_POSITION_KEYS: dict[str, str] = {
    "favorable": "preferred",
    "neutral": "acceptable",
    "unfavorable": "walkaway",
}


def _parse_category(raw: dict[str, Any]) -> Category:
    """Parse a single category dict into a Category model.

    Supports legacy position keys (favorable/neutral/unfavorable) with a
    DeprecationWarning. New keys (preferred/acceptable/walkaway) take
    precedence when both are present.
    """
    resolved = dict(raw)
    used_legacy = False

    for old_key, new_key in LEGACY_POSITION_KEYS.items():
        if old_key in raw and new_key not in raw:
            resolved[new_key] = raw[old_key]
            used_legacy = True

    for req in (
        "id",
        "name",
        "description",
        "preferred",
        "acceptable",
        "walkaway",
        "default_position",
    ):
        if req not in resolved:
            raise PlaybookLoadError(f"Category missing required field: {req}")

    if used_legacy:
        warnings.warn(
            "Legacy position keys 'favorable'/'neutral'/'unfavorable' used. "
            "Rename to 'preferred'/'acceptable'/'walkaway'. This will be removed in a future version.",
            DeprecationWarning,
            stacklevel=2,
        )

    # Also map legacy default_position values
    default_val = str(resolved["default_position"])
    if default_val in LEGACY_POSITION_KEYS:
        if not used_legacy:
            warnings.warn(
                f"Legacy default_position value '{default_val}' used. "
                f"Use '{LEGACY_POSITION_KEYS[default_val]}' instead.",
                DeprecationWarning,
                stacklevel=2,
            )
        default_val = LEGACY_POSITION_KEYS[default_val]

    try:
        default = Position(default_val)
    except ValueError as exc:
        raise PlaybookLoadError(
            f"Invalid default_position '{default_val}' in category '{resolved.get('id', '?')}'"
        ) from exc

    return Category(
        id=str(resolved["id"]),
        name=str(resolved["name"]),
        description=str(resolved["description"]),
        preferred=_parse_position_def(resolved["preferred"]),
        acceptable=_parse_position_def(resolved["acceptable"]),
        walkaway=_parse_position_def(resolved["walkaway"]),
        default_position=default,
    )


def load_playbook_from_db(playbook_id: str) -> tuple[Playbook, int]:
    """Load the latest version of a playbook from the database.

    Returns (Playbook, version_number).

    Raises PlaybookLoadError if the playbook_id is not found.
    """
    import json

    from openreview_cli.config.paths import get_data_dir
    from openreview_cli.storage.database import get_latest_playbook_version

    db_path = get_data_dir() / "openreview.db"
    result = get_latest_playbook_version(db_path, playbook_id)
    if result is None:
        raise PlaybookLoadError(f"Playbook '{playbook_id}' not found in database.")
    content, version = result
    try:
        raw = json.loads(content)
    except json.JSONDecodeError as exc:
        raise PlaybookLoadError(f"Corrupt playbook data: {exc}") from exc
    return _parse_playbook(raw), version


def _parse_position_def(raw: dict[str, Any]) -> PositionDef:
    """Parse a position definition from a YAML dict."""
    if not isinstance(raw, dict):
        raise PlaybookLoadError("Position definition must be a mapping")
    for req in ("description", "exemplars"):
        if req not in raw:
            raise PlaybookLoadError(f"Position def missing required field: {req}")
    exemplars = raw["exemplars"]
    if not isinstance(exemplars, list) or not exemplars:
        raise PlaybookLoadError("Position def 'exemplars' must be a non-empty list")
    return PositionDef(
        description=str(raw["description"]),
        exemplars=[str(e) for e in exemplars],
    )
