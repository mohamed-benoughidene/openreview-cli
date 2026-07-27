"""Playbook versioning — import, export, diff, and version management."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from openreview_cli.storage.database import transaction


def import_playbook_yaml(db_path: Path, playbook_id: str, content: str) -> tuple[int, int | None]:
    """Import a playbook YAML content, returning (new_version, prev_version).

    If this is the first import, prev_version is None.
    """
    with transaction(db_path) as conn:
        cur = conn.execute(
            "SELECT COALESCE(MAX(version), 0) FROM playbook_versions WHERE playbook_id = ?",
            (playbook_id,),
        )
        prev_version = int(cur.fetchone()[0])
        next_ver = prev_version + 1
        conn.execute(
            "INSERT INTO playbook_versions (playbook_id, version, content) VALUES (?, ?, ?)",
            (playbook_id, next_ver, content),
        )
    prev: int | None = prev_version if prev_version > 0 else None
    return next_ver, prev


def get_playbook_version(db_path: Path, playbook_id: str, version: int) -> str | None:
    """Get the content of a specific playbook version, or None."""
    with transaction(db_path) as conn:
        row = conn.execute(
            "SELECT content FROM playbook_versions WHERE playbook_id = ? AND version = ?",
            (playbook_id, version),
        ).fetchone()
    return str(row["content"]) if row else None


def get_latest_playbook_version(db_path: Path, playbook_id: str) -> tuple[str, int] | None:
    """Get the content and version of the latest playbook version, or None."""
    with transaction(db_path) as conn:
        row = conn.execute(
            "SELECT content, version FROM playbook_versions WHERE playbook_id = ? ORDER BY version DESC LIMIT 1",
            (playbook_id,),
        ).fetchone()
    return (str(row["content"]), int(row["version"])) if row else None


def list_playbooks(db_path: Path) -> list[tuple[str, int, str]]:
    """List all playbooks with their latest version and created_at.

    Returns (playbook_id, max_version, created_at) for each playbook,
    ordered by playbook_id.
    """
    with transaction(db_path) as conn:
        rows = conn.execute(
            "SELECT playbook_id, MAX(version) AS version, created_at "
            "FROM playbook_versions GROUP BY playbook_id ORDER BY playbook_id"
        ).fetchall()
    return [(str(r["playbook_id"]), int(r["version"]), str(r["created_at"])) for r in rows]


def list_playbooks_with_meta(
    db_path: Path, include_deleted: bool = False
) -> list[tuple[str, int, str, bool]]:
    """Like list_playbooks, but includes deleted status.

    Returns (playbook_id, max_version, created_at, is_deleted).
    When *include_deleted* is False (default), soft-deleted playbooks are excluded.
    """
    with transaction(db_path) as conn:
        rows = conn.execute(
            "SELECT v.playbook_id, MAX(v.version) AS version, v.created_at, "
            "CASE WHEN m.deleted_at IS NOT NULL THEN 1 ELSE 0 END AS is_deleted "
            "FROM playbook_versions v "
            "LEFT JOIN playbook_meta m ON v.playbook_id = m.playbook_id "
            "GROUP BY v.playbook_id ORDER BY v.playbook_id"
        ).fetchall()
    result = [
        (str(r["playbook_id"]), int(r["version"]), str(r["created_at"]), bool(r["is_deleted"]))
        for r in rows
    ]
    if not include_deleted:
        result = [(pid, ver, ca, _del) for pid, ver, ca, _del in result if not _del]
    return result


def ensure_playbook_meta(db_path: Path, playbook_id: str) -> None:
    """Lazy-create a playbook_meta row if one doesn't exist.

    Sets current_version to the max version from playbook_versions.
    Raises ValueError if playbook_id has no versions.
    """
    with transaction(db_path) as conn:
        row = conn.execute(
            "SELECT "
            "  COALESCE((SELECT 1 FROM playbook_meta WHERE playbook_id = ?), 0) AS meta_exists, "
            "  COALESCE(MAX(version), 0) AS max_ver "
            "FROM playbook_versions WHERE playbook_id = ?",
            (playbook_id, playbook_id),
        ).fetchone()
        if int(row["meta_exists"]):
            return
        max_ver = int(row["max_ver"])
        if max_ver == 0:
            msg = f"Playbook '{playbook_id}' not found."
            raise ValueError(msg)
        conn.execute(
            "INSERT INTO playbook_meta (playbook_id, current_version) VALUES (?, ?)",
            (playbook_id, max_ver),
        )


def get_current_version(db_path: Path, playbook_id: str) -> int:
    """Return effective current version for *playbook_id*.

    Uses meta.current_version if available, otherwise MAX(version).
    Raises ValueError if playbook_id not found.
    """
    with transaction(db_path) as conn:
        row = conn.execute(
            "SELECT "
            "  COALESCE("
            "    (SELECT current_version FROM playbook_meta WHERE playbook_id = ?),"
            "    (SELECT MAX(version) FROM playbook_versions WHERE playbook_id = ?)"
            "  ) AS effective_version, "
            "  (SELECT COUNT(*) FROM playbook_versions WHERE playbook_id = ?) AS count",
            (playbook_id, playbook_id, playbook_id),
        ).fetchone()
        if int(row["count"]) == 0:
            msg = f"Playbook '{playbook_id}' not found."
            raise ValueError(msg)
    return int(row["effective_version"])


def export_playbook_version(
    db_path: Path, playbook_id: str, version: int | None = None
) -> str | None:
    """Get the content string of a specific (or current) version.

    Returns None if the requested version does not exist.
    Raises ValueError if playbook_id has no versions.
    """
    if version is None:
        version = get_current_version(db_path, playbook_id)
    return get_playbook_version(db_path, playbook_id, version)


def diff_playbook_versions(
    db_path: Path, playbook_id: str, v1: int, v2: int
) -> tuple[dict[str, Any], dict[str, Any], int, int]:
    """Fetch two playbook versions and return raw data dicts.

    Returns (data1, data2, normalised_v1, normalised_v2) where v1 < v2.

    Raises ValueError if either version is not found.
    """
    # Normalise: v1 < v2
    if v1 > v2:
        v1, v2 = v2, v1

    raw1 = get_playbook_version(db_path, playbook_id, v1)
    raw2 = get_playbook_version(db_path, playbook_id, v2)

    if raw1 is None:
        raise ValueError(f"Version {v1} not found for playbook '{playbook_id}'.")
    if raw2 is None:
        raise ValueError(f"Version {v2} not found for playbook '{playbook_id}'.")

    data1: dict[str, Any] = json.loads(raw1)
    data2: dict[str, Any] = json.loads(raw2)

    return data1, data2, v1, v2


def set_current_version(db_path: Path, playbook_id: str, version: int) -> tuple[bool, str]:
    """Set effective current version. Re-activates deleted playbooks.

    Returns (was_changed, message).
    Raises ValueError if playbook_id or version not found.
    """
    # Validate version exists
    with transaction(db_path) as conn:
        row = conn.execute(
            "SELECT "
            "  (SELECT content FROM playbook_versions WHERE playbook_id = ? AND version = ?) AS content, "
            "  COALESCE((SELECT MAX(version) FROM playbook_versions WHERE playbook_id = ?), 0) AS max_ver",
            (playbook_id, version, playbook_id),
        ).fetchone()
        if row["content"] is None:
            if int(row["max_ver"]) == 0:
                raise ValueError(f"Playbook '{playbook_id}' not found.")
            raise ValueError(
                f"Version {version} not found for playbook '{playbook_id}' "
                f"(latest: {int(row['max_ver'])})."
            )

    with transaction(db_path) as conn:
        # ensure_playbook_meta inline — INSERT if missing with MAX version
        conn.execute(
            "INSERT OR IGNORE INTO playbook_meta (playbook_id, current_version) "
            "VALUES (?, (SELECT COALESCE(MAX(version), 0) FROM playbook_versions WHERE playbook_id = ?))",
            (playbook_id, playbook_id),
        )
        cur = conn.execute(
            "SELECT current_version, deleted_at FROM playbook_meta WHERE playbook_id = ?",
            (playbook_id,),
        ).fetchone()
        cur_ver = int(cur["current_version"])
        deleted = cur["deleted_at"]

        if cur_ver == version and deleted is None:
            return False, f"Version {version} is already current for '{playbook_id}'."

        conn.execute(
            "UPDATE playbook_meta SET current_version = ?, deleted_at = NULL WHERE playbook_id = ?",
            (version, playbook_id),
        )
    return True, f"Set current version of '{playbook_id}' to {version}."


def delete_playbook(db_path: Path, playbook_id: str) -> tuple[bool, str]:
    """Soft-delete a playbook by setting deleted_at.

    Returns (was_changed, message).
    Raises ValueError if playbook_id not found.
    """
    # Validate playbook exists
    with transaction(db_path) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM playbook_versions WHERE playbook_id = ?",
            (playbook_id,),
        ).fetchone()[0]
        if int(count) == 0:
            raise ValueError(f"Playbook '{playbook_id}' not found.")

    ensure_playbook_meta(db_path, playbook_id)

    with transaction(db_path) as conn:
        cur = conn.execute(
            "SELECT deleted_at FROM playbook_meta WHERE playbook_id = ?",
            (playbook_id,),
        ).fetchone()
        if cur is not None and cur["deleted_at"] is not None:
            return False, f"Playbook '{playbook_id}' is already deleted."

        now = datetime.now().isoformat()
        conn.execute(
            "UPDATE playbook_meta SET deleted_at = ? WHERE playbook_id = ?",
            (now, playbook_id),
        )
    return True, f"Deleted playbook '{playbook_id}'."


def get_playbook_history(
    db_path: Path, playbook_id: str
) -> tuple[list[dict[str, object]], int, bool]:
    """Return version timeline for a playbook.

    Returns (rows, current_version, is_deleted).
    Each row: {version, created_at, is_current, is_latest}.
    Raises ValueError if playbook_id not found.
    """
    with transaction(db_path) as conn:
        version_rows = conn.execute(
            "SELECT v.version, v.created_at, "
            "  COALESCE("
            "    (SELECT current_version FROM playbook_meta WHERE playbook_id = ?),"
            "    (SELECT MAX(version) FROM playbook_versions WHERE playbook_id = ?)"
            "  ) AS effective_version, "
            "  (SELECT deleted_at FROM playbook_meta WHERE playbook_id = ?) AS deleted_at, "
            "  MAX(v.version) OVER () AS max_version "
            "FROM playbook_versions v "
            "WHERE v.playbook_id = ? ORDER BY v.version ASC",
            (playbook_id, playbook_id, playbook_id, playbook_id),
        ).fetchall()

        if not version_rows:
            raise ValueError(f"Playbook '{playbook_id}' not found.")

        current_version = int(version_rows[0]["effective_version"])
        is_deleted = version_rows[0]["deleted_at"] is not None
        max_version = int(version_rows[0]["max_version"])

    rows = [
        {
            "version": int(r["version"]),
            "created_at": str(r["created_at"]),
            "is_current": int(r["version"]) == current_version,
            "is_latest": int(r["version"]) == max_version,
        }
        for r in version_rows
    ]

    return rows, current_version, is_deleted
