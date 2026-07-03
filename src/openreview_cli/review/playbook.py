"""Playbook loader — YAML parsing, validation, bundled load."""

from __future__ import annotations

import hashlib
import logging
import sqlite3
import sys
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

logger = logging.getLogger(__name__)

BUNDLED_PLAYBOOK_PATH = Path(__file__).parent / "playbooks" / "precheck-nda-v1.yaml"


class PlaybookLoadError(ValueError):
    """Raised when a playbook cannot be loaded or validated."""


def content_hash(data: bytes) -> str:
    """Compute SHA-256 hex digest of raw byte content."""
    return hashlib.sha256(data).hexdigest()


def load_bundled(
    db_path: Path | None = None,
    pin_version: str | None = None,
) -> Playbook:
    """Load the bundled NDA playbook shipped with PreCheck mode."""
    return load_playbook(BUNDLED_PLAYBOOK_PATH, db_path=db_path, pin_version=pin_version)


def load_playbook(
    path: Path,
    db_path: Path | None = None,
    pin_version: str | None = None,
) -> Playbook:
    """Load and validate a YAML playbook from *path*.

    When *db_path* is provided, the playbook is cached in SQLite:
    - Computes SHA-256 of raw YAML bytes
    - Queries ``playbook_version`` for existing record
    - Inserts new version row if not found
    - Detects content changes and applies ``+N`` suffix
    - Auto-assigns ``0.1.0`` when no version is set

    When *pin_version* is set, the loader:
    1. Queries DB for ``(id, pin_version)``
    2. If found — reuses existing content without re-parsing YAML
    3. If not found — validates loaded version matches pin, errors on mismatch
    """
    if not path.exists():
        raise PlaybookLoadError(f"Playbook not found: {path}")

    raw_bytes = path.read_bytes()
    raw_hash = content_hash(raw_bytes)

    try:
        text = raw_bytes.decode("utf-8")
        raw = yaml.safe_load(text)
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        raise PlaybookLoadError(f"Invalid YAML in playbook: {exc}") from exc

    if not isinstance(raw, dict):
        raise PlaybookLoadError("Playbook must be a YAML mapping")

    playbook_id = str(raw.get("id", ""))
    meta_raw = raw.get("metadata")
    embedded_version: str | None = None
    if isinstance(meta_raw, dict):
        embedded_version = str(meta_raw.get("version", "")) if meta_raw.get("version") else None

    if pin_version is not None and db_path is not None:
        try:
            from openreview_cli.storage.database import find_version

            cached = find_version(db_path, playbook_id, pin_version)
            if cached is not None:
                cached_raw = yaml.safe_load(cached["content"])
                if isinstance(cached_raw, dict):
                    playbook = _parse_playbook(cached_raw)
                    playbook.version_id = f"{playbook.id}@{pin_version}"
                    playbook.content_hash = cached["content_hash"]
                    return playbook
        except (sqlite3.Error, OSError):
            logger.warning("DB lookup failed for version pin, falling back to YAML", exc_info=True)

    if embedded_version is None or not embedded_version:
        assigned_version = "0.1.0"
        if isinstance(meta_raw, dict):
            meta_raw["version"] = assigned_version
        msg = f'Warning: Playbook "{playbook_id}" has no version — assigned {assigned_version}'
        print(msg, file=sys.stderr)
        logger.warning(msg)
        embedded_version = assigned_version

    playbook = _parse_playbook(raw)

    if db_path is not None:
        _cache_playbook_version(db_path, playbook, raw_bytes, raw_hash, pin_version)

    if pin_version is not None and pin_version != playbook.metadata.version:
        raise PlaybookLoadError(
            f"Requested version {pin_version} does not match "
            f'playbook "{playbook.id}" version {playbook.metadata.version}'
        )

    playbook.version_id = f"{playbook.id}@{playbook.metadata.version}"
    playbook.content_hash = raw_hash
    return playbook


def _cache_playbook_version(
    db_path: Path,
    playbook: Playbook,
    raw_bytes: bytes,
    raw_hash: str,
    pin_version: str | None,
) -> None:
    """Store or reuse playbook version in SQLite."""
    from openreview_cli.storage.database import (
        ensure_playbook_record,
        find_version,
        get_max_plus_suffix,
        insert_version,
    )

    try:
        ensure_playbook_record(
            db_path,
            playbook.id,
            mode=playbook.mode,
            description=playbook.metadata.description,
            author=playbook.metadata.author,
        )

        existing = find_version(db_path, playbook.id, playbook.metadata.version)

        if existing is not None:
            if existing["content_hash"] != raw_hash:
                # Content changed without version bump → +N suffix
                next_suffix = (
                    get_max_plus_suffix(db_path, playbook.id, playbook.metadata.version) + 1
                )
                suffixed = f"{playbook.metadata.version}+{next_suffix}"
                msg = (
                    f'Warning: Playbook "{playbook.id}" content changed but version '
                    f'"{playbook.metadata.version}" unchanged — storing as {suffixed}'
                )
                print(msg, file=sys.stderr)
                logger.warning(msg)
                insert_version(
                    db_path,
                    playbook.id,
                    suffixed,
                    raw_hash,
                    raw_bytes.decode("utf-8"),
                )
                playbook.metadata.version = suffixed
            # else: existing record matches — reuse silently
        else:
            insert_version(
                db_path,
                playbook.id,
                playbook.metadata.version,
                raw_hash,
                raw_bytes.decode("utf-8"),
            )
    except (sqlite3.Error, OSError):
        msg = "Warning: Playbook version storage unavailable — running without persistence"
        print(msg, file=sys.stderr)
        logger.warning(msg, exc_info=True)


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


_NEW_TO_OLD_POSITION = {
    "preferred": "favorable",
    "acceptable": "neutral",
    "walkaway": "unfavorable",
}


def _parse_category(raw: dict[str, Any]) -> Category:
    """Parse a single category dict into a Category model."""
    position_keys = {
        "favorable",
        "neutral",
        "unfavorable",
        "preferred",
        "acceptable",
        "walkaway",
    }
    present = [k for k in position_keys if k in raw]
    if len(present) < 3:
        raise PlaybookLoadError(
            f"Category '{raw.get('id', '?')}' missing position definitions — "
            "need favorable/neutral/unfavorable or preferred/acceptable/walkaway"
        )

    if "favorable" in raw:
        key_fav, key_neu, key_unf = "favorable", "neutral", "unfavorable"
    else:
        key_fav, key_neu, key_unf = "preferred", "acceptable", "walkaway"

    for req in ("id", "name", "description", "default_position", key_fav, key_neu, key_unf):
        if req not in raw:
            raise PlaybookLoadError(f"Category missing required field: {req}")

    default_raw = str(raw["default_position"])
    default_str = _NEW_TO_OLD_POSITION.get(default_raw, default_raw)
    try:
        default = Position(default_str)
    except ValueError as exc:
        raise PlaybookLoadError(
            f"Invalid default_position '{raw['default_position']}' in category '{raw.get('id', '?')}'"
        ) from exc

    return Category(
        id=str(raw["id"]),
        name=str(raw["name"]),
        description=str(raw["description"]),
        favorable=_parse_position_def(raw[key_fav]),
        neutral=_parse_position_def(raw[key_neu]),
        unfavorable=_parse_position_def(raw[key_unf]),
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
