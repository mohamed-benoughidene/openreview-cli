"""T055: Test cost write succeeds with nullable session_id.

Verifies:
- session_id=None produces a valid record (FK must be nullable)
- session_id with a matching session produces a valid record
- No FK errors or exceptions
"""

from pathlib import Path

from openreview_cli.storage.database import get_connection, init_database, log_cost


def test_log_cost_null_session_id_succeeds(tmp_path: Path) -> None:
    """session_id=None should not raise FK or other errors."""
    db_path = tmp_path / "test.db"
    init_database(db_path)

    entry_id = log_cost(
        db_path,
        session_id=None,
        model="openai/gpt-4o",
        provider="openai",
        prompt_tokens=100,
        completion_tokens=50,
        cost_cents=5,
        slot="reasoning",
    )
    assert isinstance(entry_id, str)
    assert len(entry_id) > 0


def test_log_cost_with_session_id_succeeds(tmp_path: Path) -> None:
    """session_id with an existing session should succeed."""
    db_path = tmp_path / "test.db"
    init_database(db_path)

    conn = get_connection(db_path)
    conn.execute("INSERT INTO sessions (id) VALUES (?)", ("session-abc-123",))
    conn.commit()
    conn.close()

    entry_id = log_cost(
        db_path,
        session_id="session-abc-123",
        model="openai/gpt-4o",
        provider="openai",
        prompt_tokens=100,
        completion_tokens=50,
        cost_cents=5,
        slot="reasoning",
    )
    assert isinstance(entry_id, str)
    assert len(entry_id) > 0


def test_log_cost_null_and_with_session_both_work(tmp_path: Path) -> None:
    """Multiple records with mixed session_id values all succeed."""
    db_path = tmp_path / "test.db"
    init_database(db_path)

    conn = get_connection(db_path)
    conn.execute("INSERT INTO sessions (id) VALUES (?)", ("session-xyz",))
    conn.commit()
    conn.close()

    id1 = log_cost(db_path, None, "m1", "p1", 10, 5, 1, slot="s1")
    id2 = log_cost(db_path, "session-xyz", "m2", "p2", 20, 10, 2, slot="s2")
    id3 = log_cost(db_path, None, "m3", "p3", 30, 15, 3, slot="s3")

    assert all(isinstance(eid, str) and len(eid) > 0 for eid in (id1, id2, id3))
