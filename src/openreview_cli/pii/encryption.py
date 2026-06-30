"""Fernet encryption for PII mapping files.

Key derivation: HKDF (SHA-256, 32-byte key) from document hash + salt.
The derived key is base64-encoded as required by Fernet.
Encryption: Fernet (AES-128-CBC + HMAC-SHA256, authenticated, tamper-evident).
"""

from base64 import urlsafe_b64encode

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


def derive_key(document_hash: str, salt: bytes) -> Fernet:
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=b"openreview-pii-mapping",
    )
    key_bytes = hkdf.derive(document_hash.encode("utf-8"))
    key_b64 = urlsafe_b64encode(key_bytes)
    return Fernet(key_b64)


def encrypt_pii_mapping(data: bytes, key: Fernet) -> bytes:
    return key.encrypt(data)


def decrypt_pii_mapping(token: bytes, key: Fernet) -> bytes:
    return key.decrypt(token)


__all__ = ["InvalidToken", "decrypt_pii_mapping", "derive_key", "encrypt_pii_mapping"]
