"""Playbooks domain wrapper — TUI-facing functions for playbook management."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from openreview_cli.config.paths import get_data_dir
from openreview_cli.review.models import Playbook
from openreview_cli.review.playbook import (
    PlaybookLoadError,
    VersionDiff,
    compute_playbook_diff,
    load_playbook,
)
from openreview_cli.storage.database import (
    diff_playbook_versions,
    export_playbook_version,
    get_current_version,
    get_playbook_history,
    import_playbook_yaml,
    list_playbooks,
    set_current_version,
)

_db_path = get_data_dir() / "openreview.db"


def list_playbooks_via_tui() -> list[dict[str, Any]]:
    """List all playbooks with latest version info."""

    def _cur(pid: str, ver: int) -> int:
        try:
            return get_current_version(_db_path, pid)
        except ValueError:
            return ver

    raw = list_playbooks(_db_path)
    return [
        {
            "id": pid,
            "latest_version": ver,
            "current_version": _cur(pid, ver),
            "created_at": created,
        }
        for pid, ver, created in raw
    ]


def import_playbook_via_tui(yaml_path: Path) -> dict[str, Any]:
    """Import a playbook from YAML file. Returns playbook metadata."""
    playbook = load_playbook(yaml_path)
    content = yaml_path.read_text(encoding="utf-8")
    new_ver, prev_ver = import_playbook_yaml(_db_path, playbook.id, content)
    return {
        "playbook_id": playbook.id,
        "mode": playbook.mode,
        "description": playbook.metadata.description,
        "version": str(playbook.metadata.version),
        "category_count": len(playbook.categories),
        "new_version": new_ver,
        "prev_version": prev_ver,
    }


def get_playbook_detail_via_tui(playbook_id: str) -> Playbook | None:
    """Load playbook detail (latest version) from DB."""
    from openreview_cli.review.playbook import load_playbook_from_db

    try:
        playbook, _version = load_playbook_from_db(playbook_id)
        return playbook
    except (PlaybookLoadError, ValueError):
        return None


def get_playbook_version_content(playbook_id: str, version: int) -> str | None:
    """Get raw content of a specific playbook version."""
    return export_playbook_version(_db_path, playbook_id, version)


def get_playbook_history_via_tui(playbook_id: str) -> dict[str, Any]:
    """Get version history for a playbook. Returns {rows, current_version, is_deleted}."""
    try:
        rows, current_version, is_deleted = get_playbook_history(_db_path, playbook_id)
        return {
            "rows": rows,
            "current_version": current_version,
            "is_deleted": is_deleted,
        }
    except ValueError:
        return {"rows": [], "current_version": 0, "is_deleted": False}


def set_current_version_via_tui(playbook_id: str, version: int) -> tuple[bool, str]:
    """Set effective current version for a playbook."""
    return set_current_version(_db_path, playbook_id, version)


def get_playbook_version_diff(playbook_id: str, v1: int, v2: int) -> VersionDiff:
    """Compute diff between two playbook versions."""
    data1, data2, norm_v1, norm_v2 = diff_playbook_versions(_db_path, playbook_id, v1, v2)
    diff = compute_playbook_diff(data1, data2)
    diff.v1 = norm_v1
    diff.v2 = norm_v2
    return diff
