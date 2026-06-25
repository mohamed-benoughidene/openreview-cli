"""Unit tests for PII mapping I/O."""

import json
from pathlib import Path

import pytest

from openreview_cli.pii.mapping import read_pii_mapping, write_pii_mapping
from openreview_cli.pii.models import PiiError

_ENCRYPTION_KEY = "12345678901234561234567890123456"  # 32 chars (256-bit)


def test_write_mapping_creates_file(tmp_path: Path) -> None:
    mapping = {"PARTY_A": "ABC Corp."}
    path = write_pii_mapping(mapping, tmp_path, _ENCRYPTION_KEY)
    assert path.exists()
    assert path.name == "pii_map.json"


def test_write_mapping_chmod_600(tmp_path: Path) -> None:
    mapping = {"PARTY_A": "ABC Corp."}
    path = write_pii_mapping(mapping, tmp_path, _ENCRYPTION_KEY)
    perms = path.stat().st_mode & 0o777
    assert perms == 0o600 or perms == 0o600


def test_write_mapping_contains_version_key(tmp_path: Path) -> None:
    mapping = {"PARTY_A": "ABC Corp."}
    path = write_pii_mapping(mapping, tmp_path, _ENCRYPTION_KEY)
    payload = json.loads(path.read_text())
    assert payload["version"] == 1
    assert payload["encrypted"] is True


def test_read_mapping_round_trip(tmp_path: Path) -> None:
    original = {"PARTY_A": "ABC Corp.", "NAME_1": "John"}
    write_pii_mapping(original, tmp_path, _ENCRYPTION_KEY)
    result = read_pii_mapping(tmp_path, _ENCRYPTION_KEY)
    assert result == original


def test_wrong_key_raises_error(tmp_path: Path) -> None:
    mapping = {"PARTY_A": "ABC Corp."}
    write_pii_mapping(mapping, tmp_path, _ENCRYPTION_KEY)
    wrong_key = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"  # 32 chars, wrong
    with pytest.raises(PiiError, match=r"decrypt|invalid"):
        read_pii_mapping(tmp_path, wrong_key)


def test_missing_file_raises_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match=r"pii_map\.json"):
        read_pii_mapping(tmp_path / "nonexistent", _ENCRYPTION_KEY)


def test_invalid_key_length(tmp_path: Path) -> None:
    with pytest.raises(PiiError, match="Config error"):
        write_pii_mapping({"a": "b"}, tmp_path, "short")
