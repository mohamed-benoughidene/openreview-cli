"""PiiCache — config-change detection over the pii_cache table."""

from pathlib import Path

from openreview_cli.pii.cache import PiiCache
from openreview_cli.storage import init_database


def _cache(tmp_path: Path) -> PiiCache:
    db = tmp_path / "t.db"
    init_database(db)
    return PiiCache(db)


def test_get_missing_returns_none(tmp_path: Path) -> None:
    assert _cache(tmp_path).get("nope") is None


def test_put_get_roundtrip(tmp_path: Path) -> None:
    c = _cache(tmp_path)
    c.put("h" * 64, "cfghash", "/r.json", "/m.json")
    row = c.get("h" * 64)
    assert row is not None
    assert row["config_hash"] == "cfghash"
    assert row["mapping_path"] == "/m.json"


def test_is_valid_only_when_config_matches(tmp_path: Path) -> None:
    c = _cache(tmp_path)
    c.put("h" * 64, "cfg-v1", "/r.json", "/m.json")
    assert c.is_valid("h" * 64, "cfg-v1") is True
    assert c.is_valid("h" * 64, "cfg-v2") is False
    assert c.is_valid("other", "cfg-v1") is False
