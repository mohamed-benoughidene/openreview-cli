import pytest

from openreview_cli.pii.models import (
    EntityTypeStats,
    PiiAudit,
    PiiEntity,
    PiiError,
    PiiResult,
)


def test_pii_entity_valid() -> None:
    entity = PiiEntity(
        entity_type="PERSON",
        original_value="John Doe",
        start=10,
        end=18,
        score=0.95,
        placeholder="[PERSON_1]",
        source="nlp",
    )
    assert entity.entity_type == "PERSON"
    assert entity.original_value == "John Doe"
    assert entity.start == 10
    assert entity.end == 18
    assert entity.score == 0.95
    assert entity.placeholder == "[PERSON_1]"
    assert entity.source == "nlp"


def test_pii_entity_invalid() -> None:
    # Empty type
    with pytest.raises(ValueError, match="entity_type must be non-empty"):
        PiiEntity("", "John Doe", 10, 18, 0.95, "[PERSON_1]", "nlp")

    # Empty value
    with pytest.raises(ValueError, match="original_value must be non-empty"):
        PiiEntity("PERSON", "", 10, 18, 0.95, "[PERSON_1]", "nlp")

    # Start < 0
    with pytest.raises(ValueError, match="start must be >= 0"):
        PiiEntity("PERSON", "John Doe", -1, 8, 0.95, "[PERSON_1]", "nlp")

    # End <= start
    with pytest.raises(ValueError, match="end must be > start"):
        PiiEntity("PERSON", "John Doe", 10, 10, 0.95, "[PERSON_1]", "nlp")

    # Score out of bounds
    with pytest.raises(ValueError, match=r"score must be between 0\.0 and 1\.0"):
        PiiEntity("PERSON", "John Doe", 10, 18, 1.05, "[PERSON_1]", "nlp")

    # Invalid placeholder format
    with pytest.raises(ValueError, match="placeholder must match pattern"):
        PiiEntity("PERSON", "John Doe", 10, 18, 0.95, "PERSON_1", "nlp")

    # Invalid source
    with pytest.raises(ValueError, match="invalid source"):
        PiiEntity("PERSON", "John Doe", 10, 18, 0.95, "[PERSON_1]", "invalid")


def test_pii_result_valid() -> None:
    entity = PiiEntity(
        entity_type="PERSON",
        original_value="John Doe",
        start=10,
        end=20,
        score=0.95,
        placeholder="[PERSON_1]",
        source="nlp",
    )
    result = PiiResult(
        stripped_text="Hello, my name is [PERSON_1].",
        mapping={"PERSON_1": "John Doe"},
        entities=[entity],
        page_count=1,
        duration_seconds=0.1,
        warnings=[],
    )
    assert result.page_count == 1
    assert result.duration_seconds == 0.1


def test_pii_result_invalid() -> None:
    entity = PiiEntity(
        entity_type="PERSON",
        original_value="John Doe",
        start=10,
        end=20,
        score=0.95,
        placeholder="[PERSON_1]",
        source="nlp",
    )

    # Invalid page_count
    with pytest.raises(ValueError, match="page_count must be >= 1"):
        PiiResult("Hello, [PERSON_1]", {"PERSON_1": "John Doe"}, [entity], 0, 0.1, [])

    # Invalid duration_seconds
    with pytest.raises(ValueError, match="duration_seconds must be >= 0"):
        PiiResult("Hello, [PERSON_1]", {"PERSON_1": "John Doe"}, [entity], 1, -0.1, [])

    # Mapping key missing from text
    with pytest.raises(ValueError, match="has no corresponding placeholder in stripped text"):
        PiiResult("Hello", {"PERSON_1": "John Doe"}, [entity], 1, 0.1, [])

    # Text placeholder missing from mapping
    with pytest.raises(ValueError, match="is missing from mapping"):
        PiiResult("Hello [PERSON_1] and [PERSON_2]", {"PERSON_1": "John Doe"}, [entity], 1, 0.1, [])


def test_entity_type_stats() -> None:
    stats = EntityTypeStats(count=5, min_score=0.7, max_score=0.9)
    assert stats.count == 5
    assert stats.min_score == 0.7
    assert stats.max_score == 0.9

    with pytest.raises(ValueError, match="count must be >= 1"):
        EntityTypeStats(count=0, min_score=0.7, max_score=0.9)

    with pytest.raises(ValueError, match="min_score must be <= max_score"):
        EntityTypeStats(count=2, min_score=0.9, max_score=0.7)


def test_pii_audit_valid() -> None:
    stats = EntityTypeStats(count=2, min_score=0.8, max_score=0.9)
    audit = PiiAudit(
        version=1,
        threshold=0.7,
        duration_seconds=1.2,
        page_count=3,
        non_english_sections=0,
        entity_counts={"PERSON": stats},
        metadata_fields_redacted=2,
    )
    assert audit.version == 1
    assert audit.threshold == 0.7


def test_pii_audit_invalid() -> None:
    stats = EntityTypeStats(count=2, min_score=0.8, max_score=0.9)

    with pytest.raises(ValueError, match="version must be 1"):
        PiiAudit(0, 0.7, 1.2, 3, 0, {"PERSON": stats}, 2)

    with pytest.raises(ValueError, match="threshold must be between"):
        PiiAudit(1, 1.2, 1.2, 3, 0, {"PERSON": stats}, 2)


def test_pii_error_valid() -> None:
    err = PiiError(
        exit_code=9,
        category="engine_crash",
        clause_heading="Payment Terms",
        phase="regex phase",
        message="PII detection failed while processing clause 'Payment Terms' (regex phase).",
        action="Run with --no-pii to skip stripping. Report this bug.",
    )
    assert err.exit_code == 9
    assert err.category == "engine_crash"
    assert str(err) == "PII detection failed while processing clause 'Payment Terms' (regex phase)."


def test_pii_error_invalid() -> None:
    with pytest.raises(ValueError, match="exit_code must be 9"):
        PiiError(8, "engine_crash", None, None, "error", "action")

    with pytest.raises(ValueError, match="invalid category"):
        PiiError(9, "invalid_category", None, None, "error", "action")

    with pytest.raises(ValueError, match="message contains forbidden offset details"):
        PiiError(9, "engine_crash", None, None, "failed at character 50", "action")
