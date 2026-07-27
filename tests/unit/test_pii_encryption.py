"""HKDF key derivation + Fernet roundtrip for PII mapping files."""

import pytest

from openreview_cli.pii.encryption import (
    InvalidToken,
    decrypt_pii_mapping,
    derive_key,
    encrypt_pii_mapping,
)

HASH = "a" * 64


def test_derive_key_deterministic() -> None:
    assert derive_key(HASH, b"salt")._signing_key == derive_key(HASH, b"salt")._signing_key


def test_derive_key_changes_with_salt_and_hash() -> None:
    k1, k2, k3 = derive_key(HASH, b"s1"), derive_key(HASH, b"s2"), derive_key("b" * 64, b"s1")
    assert k1._signing_key != k2._signing_key
    assert k1._signing_key != k3._signing_key


def test_roundtrip() -> None:
    key = derive_key(HASH, b"salt")
    token = encrypt_pii_mapping(b'{"PARTY_A": "Acme Corp"}', key)
    assert decrypt_pii_mapping(token, key) == b'{"PARTY_A": "Acme Corp"}'


def test_wrong_key_raises_invalid_token() -> None:
    token = encrypt_pii_mapping(b"secret", derive_key(HASH, b"salt"))
    with pytest.raises(InvalidToken):
        decrypt_pii_mapping(token, derive_key(HASH, b"other-salt"))
