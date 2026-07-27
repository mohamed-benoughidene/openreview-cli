"""Review reports + search — save, load, list, search."""

from pathlib import Path

from openreview_cli.storage.database import init_database, transaction
from openreview_cli.storage.reviews import (
    list_recent_reviews,
    list_reviews_for_client,
    load_review_report,
    save_review_report,
)
from openreview_cli.storage.search import search_all


def test_save_load_roundtrip(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    report_json = '{"ok": true, "score": 42}'
    save_review_report(db, "r1", "test.docx", "precheck", report_json, 3, 1, 0)
    loaded = load_review_report(db, "r1")
    assert loaded == {"ok": True, "score": 42}


def test_save_load_overwrite(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    save_review_report(db, "r1", "test.docx", "precheck", '{"v": 1}')
    save_review_report(db, "r1", "test.docx", "precheck", '{"v": 2}')
    loaded = load_review_report(db, "r1")
    assert loaded == {"v": 2}


def test_load_missing(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    init_database(db)
    assert load_review_report(db, "no-such") is None


def test_list_recent_reviews_ordering_and_limit(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    for i in range(5):
        save_review_report(db, f"r{i}", f"file{i}.docx", "precheck", "{}", 0, 0, 0)
    recent = list_recent_reviews(db, limit=3)
    assert len(recent) == 3
    ids = [r["id"] for r in recent]
    assert ids == ["r4", "r3", "r2"]


def test_list_recent_reviews_default_limit(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    for i in range(10):
        save_review_report(db, f"r{i}", f"file{i}.docx", "precheck", "{}")
    recent = list_recent_reviews(db)
    assert len(recent) == 5


def test_list_recent_reviews_empty(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    init_database(db)
    assert list_recent_reviews(db) == []


def test_list_reviews_for_client(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    save_review_report(db, "r1", "a.docx", "precheck", "{}", client_id="c1")
    save_review_report(db, "r2", "b.docx", "precheck", "{}", client_id="c1")
    save_review_report(db, "r3", "c.docx", "precheck", "{}", client_id="c2")
    c1_reviews = list_reviews_for_client(db, "c1")
    assert len(c1_reviews) == 2
    assert all(r["id"].startswith("r") for r in c1_reviews)
    c2_reviews = list_reviews_for_client(db, "c2")
    assert len(c2_reviews) == 1


def test_list_reviews_for_client_empty(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    init_database(db)
    assert list_reviews_for_client(db, "no-client") == []


def test_search_all_finds_by_name_and_content(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    save_review_report(db, "r1", "my_contract.pdf", "precheck", "{}")
    with transaction(db) as conn:
        conn.execute("INSERT INTO clients (id, name) VALUES (?, ?)", ("acme", "Acme Corp"))
    with transaction(db) as conn:
        conn.execute(
            "INSERT INTO playbook_versions (playbook_id, version, content) VALUES (?, ?, ?)",
            ("standard", 1, "test content"),
        )
    results = search_all(db, "acme")
    assert len(results["clients"]) == 1
    assert results["clients"][0]["id"] == "acme"
    results2 = search_all(db, "contract")
    assert len(results2["reviews"]) == 1
    assert results2["reviews"][0]["id"] == "r1"
    results3 = search_all(db, "standard")
    assert len(results3["playbooks"]) == 1
    assert results3["playbooks"][0]["playbook_id"] == "standard"


def test_search_all_no_match(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    init_database(db)
    results = search_all(db, "nonexistent")
    assert results == {"reviews": [], "clients": [], "playbooks": []}
