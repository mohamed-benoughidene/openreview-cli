from pathlib import Path

import pytest
from typer.testing import CliRunner

from openreview_cli.app import app
from openreview_cli.storage.database import get_connection, init_database, transaction

runner = CliRunner()


def _setup_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    from openreview_cli.config.paths import get_data_dir

    db_path = get_data_dir() / "openreview.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    init_database(db_path)
    return db_path


def test_client_add_creates_row(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db_path = _setup_env(monkeypatch, tmp_path)

    result = runner.invoke(app, ["client", "add", "acme", "Acme Corp"])

    assert result.exit_code == 0
    conn = get_connection(db_path)
    row = conn.execute("SELECT * FROM clients WHERE id = ?", ("acme",)).fetchone()
    assert row is not None
    assert row["name"] == "Acme Corp"
    conn.close()


def test_client_list_shows_rows(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db_path = _setup_env(monkeypatch, tmp_path)
    with transaction(db_path) as conn:
        conn.execute("INSERT INTO clients (id, name) VALUES (?, ?)", ("acme", "Acme Corp"))

    result = runner.invoke(app, ["client", "list"])

    assert result.exit_code == 0
    assert "acme" in result.stdout
    assert "Acme Corp" in result.stdout


def test_client_delete_removes_row(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db_path = _setup_env(monkeypatch, tmp_path)
    with transaction(db_path) as conn:
        conn.execute("INSERT INTO clients (id, name) VALUES (?, ?)", ("acme", "Acme Corp"))

    result = runner.invoke(app, ["client", "delete", "acme"])

    assert result.exit_code == 0
    conn = get_connection(db_path)
    row = conn.execute("SELECT * FROM clients WHERE id = ?", ("acme",)).fetchone()
    assert row is None
    conn.close()


def test_client_delete_refuses_with_reviews(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_path = _setup_env(monkeypatch, tmp_path)
    with transaction(db_path) as conn:
        conn.execute("INSERT INTO clients (id, name) VALUES (?, ?)", ("acme", "Acme Corp"))
        conn.execute(
            "INSERT INTO reviews (id, client_id, contract_path, contract_hash, mode) "
            "VALUES (?, ?, ?, ?, ?)",
            ("rev-1", "acme", "/dev/null", "0000", "precheck"),
        )

    result = runner.invoke(app, ["client", "delete", "acme"])

    assert result.exit_code == 5
    assert "reviews" in result.output.lower()


def test_client_delete_force_with_reviews(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_path = _setup_env(monkeypatch, tmp_path)
    with transaction(db_path) as conn:
        conn.execute("INSERT INTO clients (id, name) VALUES (?, ?)", ("acme", "Acme Corp"))
        conn.execute(
            "INSERT INTO reviews (id, client_id, contract_path, contract_hash, mode) "
            "VALUES (?, ?, ?, ?, ?)",
            ("rev-1", "acme", "/dev/null", "0000", "precheck"),
        )

    result = runner.invoke(app, ["client", "delete", "acme", "--force"])

    assert result.exit_code == 0
    conn = get_connection(db_path)
    row = conn.execute("SELECT * FROM clients WHERE id = ?", ("acme",)).fetchone()
    assert row is None
    conn.close()
