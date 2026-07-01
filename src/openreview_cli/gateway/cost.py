from __future__ import annotations

from typing import TYPE_CHECKING

from litellm import completion_cost

from openreview_cli.storage.database import get_session_cost as db_get_session_cost
from openreview_cli.storage.database import log_cost as db_log_cost

if TYPE_CHECKING:
    from pathlib import Path


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
            session_id or "",
            model,
            provider,
            prompt_tokens,
            completion_tokens,
            cost_cents,
            slot=slot,
        )

    def get_session_cost(self, session_id: str) -> dict[str, object]:
        return dict(db_get_session_cost(self._data_path, session_id))
