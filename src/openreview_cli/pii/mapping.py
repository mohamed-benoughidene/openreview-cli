"""Encrypted PII mapping I/O.

Uses Fernet (AES-128-CBC + HMAC-SHA256) for authenticated encryption.
Key derived from document hash via HKDF (SHA-256, 32-byte key).

File format (pii_map.enc):
  First 16 bytes: HKDF salt (used to derive the Fernet key)
  Remaining bytes: Fernet token (encrypted JSON)
"""

import json
import secrets
from pathlib import Path
from typing import Any

from openreview_cli.pii.encryption import (
    InvalidToken,
    decrypt_pii_mapping,
    derive_key,
    encrypt_pii_mapping,
)

SALT_LENGTH = 16


def write_pii_mapping(
    mapping: dict[str, str],
    review_dir: Path,
    encryption_key: str,
) -> Path:
    review_dir.mkdir(parents=True, exist_ok=True)

    salt = secrets.token_bytes(SALT_LENGTH)
    fernet = derive_key(encryption_key, salt)

    payload = {"version": 2, "entries": mapping}
    plaintext = json.dumps(payload, sort_keys=True).encode("utf-8")
    token = encrypt_pii_mapping(plaintext, fernet)

    path = review_dir / "pii_map.enc"
    path.write_bytes(salt + token)
    path.chmod(0o600)
    return path


def read_pii_mapping(
    review_dir: Path,
    encryption_key: str,
) -> dict[str, str]:
    path = review_dir / "pii_map.enc"
    if not path.exists():
        raise FileNotFoundError(f"PII mapping not found: {path}")

    data = path.read_bytes()
    salt = data[:SALT_LENGTH]
    token = data[SALT_LENGTH:]

    fernet = derive_key(encryption_key, salt)
    decrypted = decrypt_pii_mapping(token, fernet)
    payload: dict[str, Any] = json.loads(decrypted.decode("utf-8"))
    return payload["entries"]


def ensure_encryption_key(config: dict[str, Any], config_path: Path) -> str:
    if "privacy" in config and "pii_encryption_key" in config["privacy"]:
        return str(config["privacy"]["pii_encryption_key"])
    key = secrets.token_urlsafe(32)[:32]
    from openreview_cli.config.loader import set_config_value

    set_config_value(config_path, "privacy.pii_encryption_key", key)
    return key


def delete_pii_mapping(review_dir: Path) -> None:
    for name in ("pii_map.enc", "pii_audit.json"):
        path = review_dir / name
        if path.exists():
            path.unlink()


__all__ = [
    "InvalidToken",
    "delete_pii_mapping",
    "ensure_encryption_key",
    "read_pii_mapping",
    "write_pii_mapping",
]
