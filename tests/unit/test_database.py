import time
from pathlib import Path

from openreview_cli.storage.database import (
    check_daily_limit,
    check_review_limit,
    get_connection,
    init_database,
    log_cost,
    transaction,
)


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


def _seed_review(db_path: Path, review_id: str = "test-review") -> None:
    with transaction(db_path) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO clients (id, name) VALUES (?, ?)", ("seed", "Seed Client")
        )
        conn.execute(
            "INSERT OR IGNORE INTO reviews (id, client_id, contract_path, contract_hash, mode) VALUES (?, ?, ?, ?, ?)",
            (review_id, "seed", "/dev/null", "0000", "precheck"),
        )


def test_log_cost_inserts_row(tmp_path: Path) -> None:
    db_path = tmp_path / "openreview.db"
    init_database(db_path)
    _seed_review(db_path)
    log_cost(db_path, "test-review", "ollama/qwen3:8b", "ollama", 100, 50, 5)
    conn = get_connection(db_path)
    row = conn.execute("SELECT * FROM cost_logs").fetchone()
    assert row is not None
    assert row["review_id"] == "test-review"
    assert row["model"] == "ollama/qwen3:8b"
    assert row["provider"] == "ollama"
    assert row["prompt_tokens"] == 100
    assert row["completion_tokens"] == 50
    assert row["cost_cents"] == 5
    assert row["id"] is not None
    conn.close()


def test_check_daily_limit(tmp_path: Path) -> None:
    db_path = tmp_path / "openreview.db"
    init_database(db_path)
    for i in range(3):
        _seed_review(db_path, f"review-{i}")
        log_cost(db_path, f"review-{i}", "gpt4", "openai", 0, 0, 100)
    assert not check_daily_limit(db_path, 200)
    assert check_daily_limit(db_path, 400)


def test_check_review_limit(tmp_path: Path) -> None:
    db_path = tmp_path / "openreview.db"
    init_database(db_path)
    _seed_review(db_path, "review-1")
    log_cost(db_path, "review-1", "gpt4", "openai", 0, 0, 100)
    log_cost(db_path, "review-1", "gpt4", "openai", 0, 0, 50)
    assert not check_review_limit(db_path, "review-1", 100)
    assert check_review_limit(db_path, "review-1", 200)


def test_log_cost_latency(tmp_path: Path) -> None:
    db_path = tmp_path / "openreview.db"
    init_database(db_path)
    _seed_review(db_path, "latency-test")
    start = time.perf_counter()
    log_cost(db_path, "latency-test", "gpt4", "openai", 0, 0, 1)
    elapsed = time.perf_counter() - start
    assert elapsed < 0.1, f"log_cost took {elapsed:.3f}s, expected <0.1s"
