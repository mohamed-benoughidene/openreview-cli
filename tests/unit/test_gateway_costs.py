import time
from pathlib import Path

import pytest

from openreview_cli.gateway.costs import CostStore
from openreview_cli.gateway.models import CostRecord


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    return tmp_path / "gateway_test.db"


def test_session_lifecycle(temp_db_path: Path) -> None:
    store = CostStore(db_path=temp_db_path)
    session_id = "550e8400-e29b-41d4-a716-446655440000"

    # Create session
    sess = store.create_session(session_id)
    assert sess.session_id == session_id
    assert sess.started_at > 0.0
    assert sess.ended_at is None
    assert sess.total_cost_usd == 0.0

    # Get session
    retrieved = store.get_session(session_id)
    assert retrieved is not None
    assert retrieved.session_id == session_id
    assert retrieved.ended_at is None

    # Complete session
    store.complete_session(session_id)
    retrieved_completed = store.get_session(session_id)
    assert retrieved_completed is not None
    assert retrieved_completed.ended_at is not None
    assert retrieved_completed.ended_at >= retrieved_completed.started_at


def test_insert_record_updates_session_totals(temp_db_path: Path) -> None:
    store = CostStore(db_path=temp_db_path)
    session_id = "550e8400-e29b-41d4-a716-446655440000"

    store.create_session(session_id)

    record = CostRecord(
        session_id=session_id,
        slot="reasoning",
        model="gpt-4o",
        provider="openai",
        input_tokens=100,
        output_tokens=200,
        cost_usd=0.005,
        timestamp=time.time(),
        fallback_used=False,
        latency_ms=500,
    )

    store.insert_record(record)

    # Verify session totals
    sess = store.get_session(session_id)
    assert sess is not None
    assert sess.total_cost_usd == 0.005
    assert sess.total_input_tokens == 100
    assert sess.total_output_tokens == 200

    # Get session cost directly
    assert store.get_session_cost(session_id) == 0.005


def test_daily_cost_aggregation(temp_db_path: Path) -> None:
    store = CostStore(db_path=temp_db_path)
    session_id_1 = "550e8400-e29b-41d4-a716-446655440001"
    session_id_2 = "550e8400-e29b-41d4-a716-446655440002"

    store.create_session(session_id_1)
    store.create_session(session_id_2)

    # Insert record for today
    store.insert_record(
        CostRecord(
            session_id=session_id_1,
            slot="reasoning",
            model="gpt-4o",
            provider="openai",
            input_tokens=100,
            output_tokens=200,
            cost_usd=0.005,
            timestamp=time.time(),
            fallback_used=False,
            latency_ms=500,
        )
    )

    # Insert another record for today
    store.insert_record(
        CostRecord(
            session_id=session_id_2,
            slot="embedding",
            model="nomic-embed-text",
            provider="ollama",
            input_tokens=50,
            output_tokens=0,
            cost_usd=0.002,
            timestamp=time.time(),
            fallback_used=False,
            latency_ms=100,
        )
    )

    # Insert one record for "yesterday" (timestamp - 86400)
    store.insert_record(
        CostRecord(
            session_id=session_id_1,
            slot="extraction",
            model="gpt-4o",
            provider="openai",
            input_tokens=50,
            output_tokens=50,
            cost_usd=0.010,
            timestamp=time.time() - 90000,
            fallback_used=False,
            latency_ms=500,
        )
    )

    # Daily cost should only sum today's records (0.005 + 0.002 = 0.007)
    assert abs(store.get_daily_cost() - 0.007) < 1e-6


def test_cost_store_clear_and_summary(temp_db_path: Path) -> None:
    store = CostStore(db_path=temp_db_path)
    session_id = "550e8400-e29b-41d4-a716-446655440003"
    store.create_session(session_id)

    store.insert_record(
        CostRecord(
            session_id=session_id,
            slot="reasoning",
            model="gpt-4o",
            provider="openai",
            input_tokens=100,
            output_tokens=200,
            cost_usd=0.005,
            timestamp=time.time(),
            fallback_used=False,
            latency_ms=500,
        )
    )

    assert store.session_exists(session_id) is True
    assert store.session_exists("non-existent") is False

    summary = store.get_summary(days=1)
    assert summary["total_cost"] == 0.005
    assert summary["total_calls"] == 1
    assert summary["slots"]["reasoning"]["cost"] == 0.005
    assert summary["providers"]["openai"]["cost"] == 0.005

    # Clear
    store.clear()
    assert store.session_exists(session_id) is False
    summary_empty = store.get_summary(days=1)
    assert summary_empty["total_cost"] == 0.0
    assert summary_empty["total_calls"] == 0
