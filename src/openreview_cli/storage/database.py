import sqlite3
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

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
    review_id: str,
    model: str,
    provider: str,
    prompt_tokens: int,
    completion_tokens: int,
    cost_cents: int,
) -> str:
    entry_id = str(uuid.uuid4())
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO cost_logs (id, review_id, model, provider, prompt_tokens, completion_tokens, cost_cents) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (entry_id, review_id, model, provider, prompt_tokens, completion_tokens, cost_cents),
        )
        conn.commit()
    finally:
        conn.close()
    return entry_id


def check_daily_limit(db_path: Path, max_cents: int) -> bool:
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT COALESCE(SUM(cost_cents), 0) FROM cost_logs WHERE date(created_at) = date('now')"
        ).fetchone()
        return int(row[0]) < max_cents
    finally:
        conn.close()


def check_review_limit(db_path: Path, review_id: str, max_cents: int) -> bool:
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT COALESCE(SUM(cost_cents), 0) FROM cost_logs WHERE review_id = ?",
            (review_id,),
        ).fetchone()
        return int(row[0]) < max_cents
    finally:
        conn.close()
