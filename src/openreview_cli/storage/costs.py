"""Cost tracking — log and query LLM usage costs."""

import uuid
from pathlib import Path
from typing import Any

from openreview_cli.storage.database import transaction


def log_cost(
    db_path: Path,
    session_id: str,
    model: str,
    provider: str,
    prompt_tokens: int,
    completion_tokens: int,
    cost_cents: int,
    slot: str | None = None,
) -> str:
    entry_id = str(uuid.uuid4())
    with transaction(db_path) as conn:
        conn.execute(
            "INSERT INTO cost_logs (id, session_id, model, provider, prompt_tokens, completion_tokens, cost_cents, slot) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                entry_id,
                session_id,
                model,
                provider,
                prompt_tokens,
                completion_tokens,
                cost_cents,
                slot,
            ),
        )
    return entry_id


def check_daily_limit(db_path: Path, max_cents: int) -> bool:
    with transaction(db_path) as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(cost_cents), 0) FROM cost_logs WHERE date(created_at) = date('now')"
        ).fetchone()
        return int(row[0]) < max_cents


def check_session_limit(db_path: Path, session_id: str, max_cents: int) -> bool:
    with transaction(db_path) as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(cost_cents), 0) FROM cost_logs WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        return int(row[0]) < max_cents


def get_session_cost(db_path: Path, session_id: str) -> dict[str, Any]:
    with transaction(db_path) as conn:
        rows = conn.execute(
            "SELECT slot, COALESCE(SUM(prompt_tokens), 0), COALESCE(SUM(completion_tokens), 0), COALESCE(SUM(cost_cents), 0) FROM cost_logs WHERE session_id = ? GROUP BY slot",
            (session_id,),
        ).fetchall()
        total_prompt = 0
        total_completion = 0
        total_cost = 0
        slots: dict[str, dict[str, int]] = {}
        for r in rows:
            slot_name = str(r[0]) if r[0] else ""
            slots[slot_name] = {
                "prompt_tokens": int(r[1]),
                "completion_tokens": int(r[2]),
                "cost_cents": int(r[3]),
            }
            total_prompt += int(r[1])
            total_completion += int(r[2])
            total_cost += int(r[3])
        return {
            "prompt_tokens": total_prompt,
            "completion_tokens": total_completion,
            "cost_cents": total_cost,
            "slots": slots,
        }
