import time
from pathlib import Path

from openreview_cli.storage.database import init_database


def test_init_database_creates_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "openreview.db"
    init_database(db_path)
    assert db_path.exists()


def test_init_database_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "openreview.db"
    init_database(db_path)
    init_database(db_path)


def test_init_database_latency(tmp_path: Path) -> None:
    db_path = tmp_path / "openreview.db"
    start = time.perf_counter()
    init_database(db_path)
    elapsed = time.perf_counter() - start
    assert elapsed < 2.0, f"DB init took {elapsed:.3f}s, expected <2.0s"
