"""Unit tests for the TUI retrieval domain adapter.

No Textual, no ``run_test`` — the adapter is the whole surface under test, and
every test redirects the index directory (``db_dir``) *and* the XDG roots
(``isolated_xdg``) so nothing reaches the developer's real
``~/.local/share/openreview/indexes/`` or writes a real ``config.yml``.
"""

from __future__ import annotations

import hashlib
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from openreview_cli.retrieval.errors import IndexCorruptError, IndexNotFoundError
from openreview_cli.tui.domain.retrieval import (
    chunk_document,
    clear_index,
    index_meta,
    ingest_chunks,
    resolve_document,
    search,
)

# Every key ``retrieval.ingest._normalize_chunk`` reads out of a chunk dict.
_NORMALIZE_CHUNK_KEYS = (
    "id",
    "text",
    "source_clause_title",
    "source_clause_level",
    "char_offset_start",
    "char_offset_end",
    "parent_chunk_id",
    "structural_location",
)

_FIXTURE_NAME = "nda_with_pii.pdf"
# A phrase that exists verbatim in the fixture.
_PHRASE = "This Confidentiality Agreement is entered into by"


def _fixture(fixtures_dir: Path) -> Path:
    return fixtures_dir / _FIXTURE_NAME


def _sqlite_refuses(db_path: Path) -> bool:
    """True when SQLite cannot read the image at all."""
    try:
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("SELECT * FROM index_meta")
    except sqlite3.DatabaseError:
        return True
    return False


def _malformed_index(db_dir: Path, fixtures_dir: Path) -> Path:
    """A real index truncated to half its length, as the reproducer builds one.

    This is the file an ingest killed mid-write, a second process, or a full
    disk leaves behind: it exists, it is not a valid SQLite image, and no
    metadata row can be read out of it. The premise is asserted, so the test
    cannot silently stop testing damage.
    """
    document_id, db_path = resolve_document(_fixture(fixtures_dir), db_dir=db_dir)
    ingest_chunks(chunk_document(_fixture(fixtures_dir)), db_path, document_id=document_id)
    raw = db_path.read_bytes()
    db_path.write_bytes(raw[: len(raw) // 2])

    assert _sqlite_refuses(db_path), "premise: a truncated image must not be readable SQLite"
    return db_path


# --------------------------------------------------------------------------
# Identity
# --------------------------------------------------------------------------


def test_identity_is_a_stable_sha256_of_the_file_bytes(
    tmp_path: Path, isolated_xdg: dict[str, Path]
) -> None:
    doc = tmp_path / "a.pdf"
    doc.write_bytes(b"%PDF-1.4 first document")

    document_id, db_path = resolve_document(doc, db_dir=tmp_path / "indexes")

    assert document_id == hashlib.sha256(b"%PDF-1.4 first document").hexdigest()
    assert len(document_id) == 64
    assert all(c in "0123456789abcdef" for c in document_id)
    assert db_path.name == f"{document_id[:32]}.db"
    assert resolve_document(doc, db_dir=tmp_path / "indexes") == (document_id, db_path)


def test_identity_changes_when_the_bytes_change(
    tmp_path: Path, isolated_xdg: dict[str, Path]
) -> None:
    first = tmp_path / "a.pdf"
    first.write_bytes(b"%PDF-1.4 first document")
    second = tmp_path / "b.pdf"
    second.write_bytes(b"%PDF-1.4 first document, edited")

    first_id, first_db = resolve_document(first, db_dir=tmp_path / "indexes")
    second_id, second_db = resolve_document(second, db_dir=tmp_path / "indexes")

    assert first_id != second_id
    assert first_db != second_db


def test_missing_document_raises_file_not_found(
    tmp_path: Path, isolated_xdg: dict[str, Path]
) -> None:
    with pytest.raises(FileNotFoundError):
        resolve_document(tmp_path / "absent.pdf", db_dir=tmp_path / "indexes")


def test_directory_raises_before_any_parsing(tmp_path: Path, isolated_xdg: dict[str, Path]) -> None:
    directory = tmp_path / "a-directory"
    directory.mkdir()

    with pytest.raises(IsADirectoryError):
        resolve_document(directory, db_dir=tmp_path / "indexes")


# --------------------------------------------------------------------------
# Chunking
# --------------------------------------------------------------------------


def test_chunk_document_yields_dicts_the_ingest_schema_can_read(
    fixtures_dir: Path, isolated_xdg: dict[str, Path]
) -> None:
    chunks = chunk_document(_fixture(fixtures_dir))

    assert chunks, "the NDA fixture must chunk to at least one chunk"
    for chunk in chunks:
        for key in _NORMALIZE_CHUNK_KEYS:
            assert key in chunk, f"chunk is missing {key!r}"
    assert any(_PHRASE in str(chunk["text"]) for chunk in chunks)


# --------------------------------------------------------------------------
# Status reads must not fabricate an index (fact 4)
# --------------------------------------------------------------------------


def test_index_meta_on_a_missing_path_returns_none_and_creates_no_file(
    tmp_path: Path, isolated_xdg: dict[str, Path]
) -> None:
    """``sqlite3.connect`` creates the file it is given — the guard must fire first."""
    db_dir = tmp_path / "indexes"
    db_dir.mkdir()
    before = sorted(p.name for p in db_dir.iterdir())

    assert index_meta(db_dir / "never-indexed.db") is None

    assert sorted(p.name for p in db_dir.iterdir()) == before
    assert before == []


def test_index_meta_reports_the_index_after_ingest(
    fixtures_dir: Path, tmp_path: Path, isolated_xdg: dict[str, Path]
) -> None:
    document_id, db_path = resolve_document(_fixture(fixtures_dir), db_dir=tmp_path / "indexes")
    chunks = chunk_document(_fixture(fixtures_dir))
    ingest_chunks(chunks, db_path, document_id=document_id)

    meta = index_meta(db_path)

    assert meta is not None
    assert meta["index_status"] == "indexed"
    assert meta["chunk_count"] == len(chunks)
    assert meta["document_id"] == document_id


# --------------------------------------------------------------------------
# Search
# --------------------------------------------------------------------------


def test_search_on_an_un_indexed_path_raises_index_not_found(
    tmp_path: Path, isolated_xdg: dict[str, Path]
) -> None:
    with pytest.raises(IndexNotFoundError):
        search(tmp_path / "indexes" / "absent.db", "confidentiality")


def test_search_after_ingest_returns_the_matching_chunk(
    fixtures_dir: Path, tmp_path: Path, isolated_xdg: dict[str, Path]
) -> None:
    document_id, db_path = resolve_document(_fixture(fixtures_dir), db_dir=tmp_path / "indexes")
    ingest_chunks(chunk_document(_fixture(fixtures_dir)), db_path, document_id=document_id)

    results = search(db_path, _PHRASE)

    assert results
    assert any(_PHRASE in result.text for result in results)
    assert all(isinstance(result.score, float) for result in results)
    assert all(result.method == "sparse" for result in results)


def test_search_honours_an_explicit_top_k(
    fixtures_dir: Path, tmp_path: Path, isolated_xdg: dict[str, Path]
) -> None:
    document_id, db_path = resolve_document(_fixture(fixtures_dir), db_dir=tmp_path / "indexes")
    ingest_chunks(chunk_document(_fixture(fixtures_dir)), db_path, document_id=document_id)

    assert len(search(db_path, "agreement", top_k=1)) <= 1


def test_search_returns_nothing_for_a_query_with_no_terms_in_the_document(
    fixtures_dir: Path, tmp_path: Path, isolated_xdg: dict[str, Path]
) -> None:
    document_id, db_path = resolve_document(_fixture(fixtures_dir), db_dir=tmp_path / "indexes")
    ingest_chunks(chunk_document(_fixture(fixtures_dir)), db_path, document_id=document_id)

    assert search(db_path, "zzqqxnonexistentterm") == []


# --------------------------------------------------------------------------
# A physically malformed index file
# --------------------------------------------------------------------------
#
# ``RetrievalStorage.get_index_meta`` catches only ``sqlite3.OperationalError``,
# and a malformed image fails earlier, as a plain ``sqlite3.DatabaseError``
# raised by ``PRAGMA journal_mode=WAL`` in ``RetrievalStorage.conn`` - so
# nothing downstream stops it. Uncaught it reaches Textual's
# ``_handle_exception``, whose documented behaviour is app exit with a
# traceback; and the file *exists*, so it is not the "not indexed" state either.


def test_index_meta_reports_a_malformed_file_as_a_damaged_index(
    fixtures_dir: Path, tmp_path: Path, isolated_xdg: dict[str, Path]
) -> None:
    db_path = _malformed_index(tmp_path / "indexes", fixtures_dir)

    with pytest.raises(IndexCorruptError):
        index_meta(db_path)

    assert db_path.exists(), "a metadata read must never delete the damaged file"


def test_search_reports_a_malformed_file_as_a_damaged_index(
    fixtures_dir: Path, tmp_path: Path, isolated_xdg: dict[str, Path]
) -> None:
    db_path = _malformed_index(tmp_path / "indexes", fixtures_dir)

    with pytest.raises(IndexCorruptError):
        search(db_path, "confidentiality")

    assert db_path.exists()


# --------------------------------------------------------------------------
# Clear
# --------------------------------------------------------------------------


def test_clear_index_removes_the_database_and_leaves_other_indexes_alone(
    fixtures_dir: Path, tmp_path: Path, isolated_xdg: dict[str, Path]
) -> None:
    document_id, db_path = resolve_document(_fixture(fixtures_dir), db_dir=tmp_path / "indexes")
    ingest_chunks(chunk_document(_fixture(fixtures_dir)), db_path, document_id=document_id)
    neighbour = tmp_path / "indexes" / "neighbour.db"
    neighbour.write_bytes(b"keep me")

    clear_index(db_path)

    assert not db_path.exists()
    assert neighbour.exists()
    assert index_meta(db_path) is None


def test_clear_index_on_a_missing_path_is_a_no_op(
    tmp_path: Path, isolated_xdg: dict[str, Path]
) -> None:
    clear_index(tmp_path / "indexes" / "absent.db")


# --------------------------------------------------------------------------
# Import-graph constraints (D5, Global Constraints)
# --------------------------------------------------------------------------


def test_adapter_import_pulls_neither_the_gateway_router_nor_the_cli_app() -> None:
    """``gateway.router`` drags litellm in (measured 3.17 s); ``app`` is the CLI.

    Checked in a fresh interpreter so an earlier import in this pytest process
    cannot mask a regression.
    """
    code = (
        "import sys\n"
        "import openreview_cli.tui.domain.retrieval\n"
        "banned = [m for m in ('openreview_cli.gateway.router', 'litellm',"
        " 'openreview_cli.app') if m in sys.modules]\n"
        "assert not banned, f'imported {banned}'\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
