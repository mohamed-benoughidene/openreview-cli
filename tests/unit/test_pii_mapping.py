"""Unit tests for PII mapping I/O."""

from pathlib import Path

import pytest

from openreview_cli.pii.encryption import InvalidToken
from openreview_cli.pii.mapping import read_pii_mapping, write_pii_mapping

_ENCRYPTION_KEY = "document-hash-abc123def456"


def test_write_mapping_creates_file(tmp_path: Path) -> None:
    mapping = {"PARTY_A": "ABC Corp."}
    path = write_pii_mapping(mapping, tmp_path, _ENCRYPTION_KEY)
    assert path.exists()
    assert path.name == "pii_map.enc"
    assert path.stat().st_size > 0


def test_write_mapping_chmod_600(tmp_path: Path) -> None:
    mapping = {"PARTY_A": "ABC Corp."}
    path = write_pii_mapping(mapping, tmp_path, _ENCRYPTION_KEY)
    assert path.stat().st_mode & 0o777 == 0o600


def test_read_mapping_round_trip(tmp_path: Path) -> None:
    original = {"PARTY_A": "ABC Corp.", "NAME_1": "John"}
    write_pii_mapping(original, tmp_path, _ENCRYPTION_KEY)
    result = read_pii_mapping(tmp_path, _ENCRYPTION_KEY)
    assert result == original


def test_wrong_key_raises_error(tmp_path: Path) -> None:
    mapping = {"PARTY_A": "ABC Corp."}
    write_pii_mapping(mapping, tmp_path, _ENCRYPTION_KEY)
    wrong_key = "wrong-hash-key-123456789"
    with pytest.raises(InvalidToken):
        read_pii_mapping(tmp_path, wrong_key)


def test_missing_file_raises_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match=r"pii_map\.enc"):
        read_pii_mapping(tmp_path / "nonexistent", _ENCRYPTION_KEY)
