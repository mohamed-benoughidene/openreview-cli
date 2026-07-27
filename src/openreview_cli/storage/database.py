import logging
import sqlite3
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
                _exec_migration_safely(conn, sql_file)
                conn.execute(f"PRAGMA user_version = {num}")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _exec_migration_safely(conn: sqlite3.Connection, sql_file: Path) -> None:
    """Execute a migration script, tolerating idempotent re-runs.

    Some migration scripts (e.g. 011) use `ALTER TABLE ADD COLUMN` which is not
    idempotent in SQLite. If a previous run partially applied the migration
    (e.g. test fixture left the column but user_version wasn't bumped), a
    plain re-run would fail with "duplicate column name". Split the script on
    `;` and execute statements individually, skipping those that fail with a
    "duplicate column" / "already exists" / "no such column" OperationalError.
    """
    import sqlite3 as _sqlite3

    _logger = logging.getLogger(__name__)
    text = sql_file.read_text()
    for stmt in [s.strip() for s in text.split(";") if s.strip()]:
        try:
            conn.executescript(stmt + ";")
        except _sqlite3.OperationalError as exc:
            msg = str(exc).lower()
            if "duplicate column" in msg or "already exists" in msg or "no such column" in msg:
                _logger.warning(
                    "Migration %s: skipped statement (schema already matches): %.80s",
                    sql_file.name,
                    stmt,
                )
                continue
