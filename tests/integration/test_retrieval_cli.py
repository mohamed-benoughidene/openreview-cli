"""CLI behaviour for a physically damaged retrieval index (issue #118).

The commands that read an index must agree that "the file exists but is not
readable SQLite" is its own answer — not a traceback, and not the
"document not indexed" message:

* ``index-status`` reports the damage and exits 3;
* ``retrieve`` exits 3 (its pre-existing corrupt mapping);
* ``ingest`` rebuilds and exits 0, because an ingest is the documented repair.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

from openreview_cli.app import app
from openreview_cli.retrieval.ingest import ingest_from_file
from openreview_cli.retrieval.storage import RetrievalStorage

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "retrieval"
NDAX = FIXTURES_DIR / "sample_contract.ndax"


@pytest.fixture(autouse=True)
def _isolate_xdg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME"):
        monkeypatch.setenv(var, str(tmp_path / var.lower()))
    monkeypatch.delenv("OPENREVIEW_OUTPUT_DIR", raising=False)


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def damaged_index(tmp_path: Path) -> Path:
    db_dir = tmp_path / "indexes"
    db_dir.mkdir(parents=True, exist_ok=True)
    _truncated_index(db_dir)
    return db_dir


def _text(result: Result) -> str:
    raw = (getattr(result, "output", "") or "") + (getattr(result, "stderr", "") or "")
    return " ".join(raw.split())


def _sqlite_refuses(db_path: Path) -> bool:
    try:
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("SELECT * FROM index_meta")
    except sqlite3.DatabaseError:
        return True
    return False


def _truncated_index(db_dir: Path) -> Path:
    """A real index truncated to half its length, in the CLI's own db layout."""
    doc_id = json.loads(NDAX.read_text(encoding="utf-8"))[0]["document_id"]
    db_path = db_dir / f"{doc_id[:32]}.db"
    ingest_from_file(NDAX, db_path)
    raw = db_path.read_bytes()
    db_path.write_bytes(raw[: len(raw) // 2])
    assert _sqlite_refuses(db_path), "premise: a truncated image must not be readable SQLite"
    return db_path


def test_index_status_on_a_truncated_index_reports_damage_and_exits_3(
    runner: CliRunner, damaged_index: Path
) -> None:
    result = runner.invoke(app, ["index-status", str(NDAX), "--db-dir", str(damaged_index)])
    text = _text(result)
    assert result.exit_code == 3, (result.exit_code, text)
    assert "damaged" in text.lower() or "corrupt" in text.lower(), text
    assert "Traceback" not in text, text


def test_retrieve_on_a_truncated_index_exits_3(runner: CliRunner, damaged_index: Path) -> None:
    result = runner.invoke(
        app, ["retrieve", "confidentiality", str(NDAX), "--db-dir", str(damaged_index)]
    )
    text = _text(result)
    assert result.exit_code == 3, (result.exit_code, text)
    assert "Traceback" not in text, text
    assert "damaged" in text.lower() or "corrupt" in text.lower(), text


def test_ingest_rebuilds_a_truncated_index(runner: CliRunner, damaged_index: Path) -> None:
    result = runner.invoke(app, ["ingest", str(NDAX), "--db-dir", str(damaged_index)])
    text = _text(result)
    assert result.exit_code == 0, (result.exit_code, text)
    assert "Indexed" in text, text

    doc_id = json.loads(NDAX.read_text(encoding="utf-8"))[0]["document_id"]
    rebuilt = damaged_index / f"{doc_id[:32]}.db"
    assert not _sqlite_refuses(rebuilt)
    meta = RetrievalStorage(rebuilt).get_index_meta()
    assert meta is not None
    assert meta["index_status"] == "indexed"
