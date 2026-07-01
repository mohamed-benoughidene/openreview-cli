import sqlite3
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def get_connection(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def transaction(db_path: Path) -> Generator[sqlite3.Connection, None, None]:
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_database(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    run_migrations(db_path)


def run_migrations(db_path: Path) -> None:
    conn = get_connection(db_path)
    try:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
            num = int(sql_file.stem.split("_")[0])
            if num > version:
                conn.executescript(sql_file.read_text())
                conn.execute(f"PRAGMA user_version = {num}")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


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


def add_client(db_path: Path, client_id: str, name: str) -> None:
    with transaction(db_path) as conn:
        conn.execute(
            "INSERT INTO clients (id, name) VALUES (?, ?)",
            (client_id, name),
        )


def delete_client(db_path: Path, client_id: str, force: bool = False) -> bool:
    with transaction(db_path) as conn:
        if force:
            conn.execute(
                "DELETE FROM cost_logs WHERE session_id IN (SELECT id FROM reviews WHERE client_id = ?)",
                (client_id,),
            )
            conn.execute(
                "DELETE FROM review_diffs WHERE review_id IN (SELECT id FROM reviews WHERE client_id = ?)",
                (client_id,),
            )
            conn.execute("DELETE FROM reviews WHERE client_id = ?", (client_id,))
        cursor = conn.execute("DELETE FROM clients WHERE id = ?", (client_id,))
        return cursor.rowcount > 0


def client_has_reviews(db_path: Path, client_id: str) -> bool:
    with transaction(db_path) as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM reviews WHERE client_id = ?", (client_id,)
        ).fetchone()
        return int(row[0]) > 0


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
