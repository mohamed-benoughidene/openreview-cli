"""Recovery state — persist and load pipeline recovery context."""

import json
from pathlib import Path
from typing import Any

from openreview_cli.storage.database import init_database, transaction


def save_recovery_state(db_path: Path, pipeline_id: str, stage_name: str, context: Any) -> None:
    """Persist a RecoveryContext to the recovery_state table.

    Uses INSERT OR REPLACE so repeated saves for the same pipeline_id
    update the existing row.
    """
    from openreview_cli.recovery.models import RecoveryContext

    assert isinstance(context, RecoveryContext), "context must be a RecoveryContext"
    init_database(db_path)
    with transaction(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO recovery_state "
            "(id, pipeline_id, stage_name, context_json, status) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                pipeline_id,
                pipeline_id,
                stage_name,
                json.dumps(context.to_dict()),
                "active",
            ),
        )


def load_recovery_state(db_path: Path, pipeline_id: str) -> Any | None:
    """Load a RecoveryContext from the recovery_state table.

    Returns None if pipeline_id not found.
    """
    from openreview_cli.recovery.models import RecoveryContext

    init_database(db_path)
    with transaction(db_path) as conn:
        row = conn.execute(
            "SELECT context_json FROM recovery_state WHERE id = ?",
            (pipeline_id,),
        ).fetchone()
    if row is None:
        return None
    return RecoveryContext.from_dict(json.loads(row["context_json"]))


def delete_recovery_state(db_path: Path, pipeline_id: str) -> bool:
    """Remove a recovery state row for the given pipeline_id.

    Returns True if a row was deleted, False if pipeline_id was not found.
    """
    init_database(db_path)
    with transaction(db_path) as conn:
        cursor = conn.execute(
            "DELETE FROM recovery_state WHERE id = ?",
            (pipeline_id,),
        )
        return cursor.rowcount > 0
