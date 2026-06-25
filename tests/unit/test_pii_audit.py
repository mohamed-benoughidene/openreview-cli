"""Unit tests for PII audit file generation."""

import json
from pathlib import Path

from openreview_cli.pii.audit import build_audit, write_pii_audit
from openreview_cli.pii.models import EntityTypeStats, PiiAudit, PiiEntity


def _entity(entity_type: str, score: float = 0.9) -> PiiEntity:
    return PiiEntity(
        entity_type=entity_type,
        original_value="test",
        start=0,
        end=4,
        score=score,
        placeholder="[TEMP_0]",
        source="nlp",
    )


def test_build_audit_aggregates_counts() -> None:
    entities = [
        _entity("PERSON", 0.9),
        _entity("PERSON", 0.85),
        _entity("EMAIL_ADDRESS", 1.0),
    ]
    audit = build_audit(entities, threshold=0.7, duration_seconds=1.0, page_count=3)
    assert audit.entity_counts["PERSON"].count == 2
    assert audit.entity_counts["EMAIL_ADDRESS"].count == 1
    assert audit.entity_counts["PERSON"].min_score == 0.85
    assert audit.entity_counts["PERSON"].max_score == 0.9


def test_build_audit_metadata_counts() -> None:
    audit = build_audit(
        [], threshold=0.7, duration_seconds=0.5, page_count=1, metadata_fields_redacted=2
    )
    assert audit.metadata_fields_redacted == 2


def test_write_audit_creates_file(tmp_path: Path) -> None:
    audit = PiiAudit(
        version=1,
        threshold=0.7,
        duration_seconds=1.0,
        page_count=3,
        non_english_sections=0,
        entity_counts={"PERSON": EntityTypeStats(count=2, min_score=0.8, max_score=0.9)},
        metadata_fields_redacted=0,
    )
    path = write_pii_audit(audit, tmp_path)
    assert path.exists()
    assert path.name == "pii_audit.json"


def test_write_audit_no_pii_values(tmp_path: Path) -> None:
    audit = PiiAudit(
        version=1,
        threshold=0.7,
        duration_seconds=1.0,
        page_count=3,
        non_english_sections=0,
        entity_counts={"PERSON": EntityTypeStats(count=2, min_score=0.8, max_score=0.9)},
        metadata_fields_redacted=0,
    )
    path = write_pii_audit(audit, tmp_path)
    payload = json.loads(path.read_text())
    assert "version" in payload
    assert "entities" in payload
    assert "PERSON" in payload["entities"]
    assert payload["entities"]["PERSON"]["count"] == 2
    # No actual PII values
    assert "original_value" not in str(payload["entities"])


def test_write_audit_metadata_fields(tmp_path: Path) -> None:
    audit = PiiAudit(
        version=1,
        threshold=0.7,
        duration_seconds=2.0,
        page_count=5,
        non_english_sections=2,
        entity_counts={},
        metadata_fields_redacted=4,
    )
    path = write_pii_audit(audit, tmp_path)
    payload = json.loads(path.read_text())
    assert payload["metadata_fields_redacted"] == 4
    assert payload["non_english_sections"] == 2
