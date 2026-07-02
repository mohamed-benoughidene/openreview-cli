"""Playbook loader — YAML parsing, validation, bundled load."""

from __future__ import annotations

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


def _parse_category(raw: dict[str, Any]) -> Category:
    """Parse a single category dict into a Category model."""
    for req in (
        "id",
        "name",
        "description",
        "favorable",
        "neutral",
        "unfavorable",
        "default_position",
    ):
        if req not in raw:
            raise PlaybookLoadError(f"Category missing required field: {req}")

    try:
        default = Position(raw["default_position"])
    except ValueError as exc:
        raise PlaybookLoadError(
            f"Invalid default_position '{raw['default_position']}' in category '{raw.get('id', '?')}'"
        ) from exc

    return Category(
        id=str(raw["id"]),
        name=str(raw["name"]),
        description=str(raw["description"]),
        favorable=_parse_position_def(raw["favorable"]),
        neutral=_parse_position_def(raw["neutral"]),
        unfavorable=_parse_position_def(raw["unfavorable"]),
        default_position=default,
    )


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
