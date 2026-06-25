"""Encrypted PII mapping I/O."""

import json
from pathlib import Path

from openreview_cli.pii.models import PiiError


def write_pii_mapping(
    mapping: dict[str, str],
    review_dir: Path,
    encryption_key: str,
) -> Path:
    _validate_key(encryption_key)
    review_dir.mkdir(parents=True, exist_ok=True)

    entries = {}
    for key, value in mapping.items():
        entries[key] = _encrypt_value(value, encryption_key)

    payload = {
        "version": 1,
        "encrypted": True,
        "entries": entries,
    }

    path = review_dir / "pii_map.json"
    path.write_text(json.dumps(payload, indent=2))
    path.chmod(0o600)
    return path


def read_pii_mapping(
    review_dir: Path,
    encryption_key: str,
) -> dict[str, str]:
    _validate_key(encryption_key)
    path = review_dir / "pii_map.json"
    if not path.exists():
        raise FileNotFoundError(f"PII mapping not found: {path}")

    payload = json.loads(path.read_text())
    result = {}
    for key, encrypted_value in payload["entries"].items():
        result[key] = _decrypt_value(encrypted_value, encryption_key)
    return result


def _validate_key(key: str) -> None:
    key_bytes = key.encode("utf-8")
    if len(key_bytes) not in (16, 24, 32):
        raise PiiError(
            exit_code=9,
            category="invalid_key",
            clause_heading=None,
            phase=None,
            message="Config error: privacy.pii_encryption_key must be 16, 24, or 32 characters.",
            action="Generate a new key with: python -c 'import secrets; print(secrets.token_urlsafe(32)[:32])'",
        )


def _encrypt_value(value: str, key: str) -> str:
    from presidio_anonymizer import AnonymizerEngine
    from presidio_anonymizer.entities import OperatorConfig, RecognizerResult

    engine = AnonymizerEngine()  # type: ignore[no-untyped-call]
    result = engine.anonymize(
        text=value,
        analyzer_results=[RecognizerResult(entity_type="PII", start=0, end=len(value), score=1.0)],
        operators={"DEFAULT": OperatorConfig("encrypt", {"key": key})},
    )
    return result.text


def _decrypt_value(encrypted: str, key: str) -> str:
    from presidio_anonymizer import DeanonymizeEngine
    from presidio_anonymizer.entities import OperatorConfig, RecognizerResult

    try:
        engine = DeanonymizeEngine()  # type: ignore[no-untyped-call]
        result = engine.deanonymize(
            text=encrypted,
            entities=[RecognizerResult(entity_type="PII", start=0, end=len(encrypted), score=1.0)],  # type: ignore[list-item]
            operators={"DEFAULT": OperatorConfig("decrypt", {"key": key})},
        )
    except Exception as exc:
        raise PiiError(
            exit_code=9,
            category="invalid_key",
            clause_heading=None,
            phase="anonymizer phase",
            message=(
                "Config error: privacy.pii_encryption_key is invalid or the "
                "mapping file was created with a different key."
            ),
            action="Check your config key or regenerate: python -c 'import secrets; print(secrets.token_urlsafe(32)[:32])'",
        ) from exc
    else:
        return result.text


__all__ = ["read_pii_mapping", "write_pii_mapping"]
