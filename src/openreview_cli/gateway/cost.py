from __future__ import annotations

from typing import TYPE_CHECKING, Any

from litellm import completion_cost

from openreview_cli.storage.database import (
    get_session_cost as db_get_session_cost,
)
from openreview_cli.storage.database import log_cost as db_log_cost
from openreview_cli.storage.database import transaction

if TYPE_CHECKING:
    from pathlib import Path


def get_costs(
    db_path: Path,
    filter: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Query cost records with optional filters.

    Parameters
    ----------
    db_path:
        Path to the SQLite database.
    filter:
        Optional dict with any of these keys:
        - ``today`` (bool): if True, only today's records
        - ``session_id`` (str): filter by session ID
        - ``since`` (str): ISO date string, only records on or after this date

    Returns
    -------
    list[dict[str, Any]]
        Each dict has keys: id, session_id, slot, model, provider,
        prompt_tokens, completion_tokens, cost_cents, created_at.
    """
    query = (
        "SELECT id, session_id, slot, model, provider, "
        "  prompt_tokens, completion_tokens, cost_cents, created_at "
        "FROM cost_logs WHERE 1=1"
    )
    params: list[Any] = []

    if filter:
        if filter.get("today"):
            query += " AND date(created_at) = date('now')"
        if filter.get("session_id"):
            query += " AND session_id = ?"
            params.append(filter["session_id"])
        if filter.get("since"):
            query += " AND created_at >= ?"
            params.append(filter["since"])

    query += " ORDER BY created_at DESC"

    with transaction(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


class CostTracker:
    def __init__(self, data_path: Path) -> None:
        self._data_path = data_path

    def log_call(
        self,
        session_id: str | None,
        slot: str | None,
        model: str,
        provider: str,
        response: object,
    ) -> str:
        usage = getattr(response, "usage", None)
        prompt_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
        completion_tokens = getattr(usage, "completion_tokens", 0) if usage else 0
        if prompt_tokens or completion_tokens:
            cost_usd = completion_cost(response)
            cost_cents = max(1, round(cost_usd * 100))
        else:
            cost_cents = 0
        return db_log_cost(
            self._data_path,
            session_id,
            model,
            provider,
            prompt_tokens,
            completion_tokens,
            cost_cents,
            slot=slot,
        )

    def get_session_cost(self, session_id: str) -> dict[str, object]:
        return dict(db_get_session_cost(self._data_path, session_id))
