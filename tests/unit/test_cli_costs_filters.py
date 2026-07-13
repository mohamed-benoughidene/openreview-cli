"""T056: Test gateway costs CLI filters.

These tests will FAIL until T057-T058 implement the filters.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from openreview_cli.app import app
from openreview_cli.storage.database import get_connection, init_database, log_cost

runner = CliRunner()


def _seed_cost_records(db_path: Path) -> None:
    """Insert test cost records and a session.

    Uses ``openreview.db`` as the filename so the CLI's default path
    ``get_data_dir() / "openreview.db"`` matches after monkeypatching
    ``get_data_dir``.
    """
    cost_db = db_path / "openreview.db"
    init_database(cost_db)
    conn = get_connection(cost_db)
    conn.execute("INSERT INTO sessions (id) VALUES (?)", ("session-alpha",))
    conn.commit()
    conn.close()

    log_cost(
        cost_db,
        "session-alpha",
        "openai/gpt-4o",
        "openai",
        100,
        50,
        5,
        slot="reasoning",
    )
    log_cost(
        cost_db,
        "session-alpha",
        "openai/text-embedding-3-small",
        "openai",
        200,
        0,
        1,
        slot="embedding",
    )
    log_cost(
        cost_db,
        None,
        "anthropic/claude-sonnet",
        "anthropic",
        150,
        75,
        8,
        slot="extraction",
    )


@pytest.mark.integration
def test_costs_format_json(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """--format json returns valid JSON with records."""
    _seed_cost_records(tmp_path)
    monkeypatch.setattr("openreview_cli.app.get_data_dir", lambda: tmp_path)

    result = runner.invoke(app, ["gateway", "costs", "--format", "json"])
    assert result.exit_code == 0, result.stdout
    data = json.loads(result.stdout)
    assert "records" in data
    assert len(data["records"]) == 3
    assert "total_cost_cents" in data
    assert "record_count" in data


@pytest.mark.integration
def test_costs_session_filter(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """--session <id> filters to matching session only."""
    _seed_cost_records(tmp_path)
    monkeypatch.setattr("openreview_cli.app.get_data_dir", lambda: tmp_path)

    result = runner.invoke(
        app,
        ["gateway", "costs", "--session", "session-alpha", "--format", "json"],
    )
    assert result.exit_code == 0, result.stdout
    data = json.loads(result.stdout)
    assert len(data["records"]) == 2
    for r in data["records"]:
        assert r["session_id"] == "session-alpha"
    assert data["record_count"] == 2


@pytest.mark.integration
def test_costs_today_filter(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """--today shows only today's records."""
    _seed_cost_records(tmp_path)
    monkeypatch.setattr("openreview_cli.app.get_data_dir", lambda: tmp_path)

    result = runner.invoke(app, ["gateway", "costs", "--today", "--format", "json"])
    assert result.exit_code == 0, result.stdout
    data = json.loads(result.stdout)
    assert len(data["records"]) >= 1  # At least records inserted today


@pytest.mark.integration
def test_costs_since_filter(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """--since shows records after the given date."""
    _seed_cost_records(tmp_path)
    monkeypatch.setattr("openreview_cli.app.get_data_dir", lambda: tmp_path)

    result = runner.invoke(
        app,
        ["gateway", "costs", "--since", "2026-01-01", "--format", "json"],
    )
    assert result.exit_code == 0, result.stdout
    data = json.loads(result.stdout)
    assert len(data["records"]) == 3  # All inserted records are after 2026-01-01


@pytest.mark.integration
def test_costs_since_filter_old_date(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """--since with date before all records returns all records."""
    _seed_cost_records(tmp_path)
    monkeypatch.setattr("openreview_cli.app.get_data_dir", lambda: tmp_path)

    result = runner.invoke(
        app,
        ["gateway", "costs", "--since", "2025-01-01", "--format", "json"],
    )
    assert result.exit_code == 0, result.stdout
    data = json.loads(result.stdout)
    assert len(data["records"]) == 3


@pytest.mark.integration
def test_costs_no_records(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Empty cost database returns empty records list."""
    init_database(tmp_path / "openreview.db")
    monkeypatch.setattr("openreview_cli.app.get_data_dir", lambda: tmp_path)

    result = runner.invoke(app, ["gateway", "costs", "--format", "json"])
    assert result.exit_code == 0, result.stdout
    data = json.loads(result.stdout)
    assert len(data["records"]) == 0
    assert data["total_cost_cents"] == 0
    assert data["record_count"] == 0
