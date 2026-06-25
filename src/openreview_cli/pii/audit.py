"""PII audit file generation."""

import json
from pathlib import Path
from typing import Any

from openreview_cli.pii.models import EntityTypeStats, PiiAudit


def write_pii_audit(
    audit: PiiAudit,
    review_dir: Path,
) -> Path:
    review_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "version": audit.version,
        "threshold": audit.threshold,
        "duration_seconds": audit.duration_seconds,
        "page_count": audit.page_count,
        "non_english_sections": audit.non_english_sections,
        "entities": {
            entity_type: {
                "count": stats.count,
                "min_score": stats.min_score,
                "max_score": stats.max_score,
            }
            for entity_type, stats in audit.entity_counts.items()
        },
        "metadata_fields_redacted": audit.metadata_fields_redacted,
    }

    path = review_dir / "pii_audit.json"
    path.write_text(json.dumps(payload, indent=2))
    return path


def build_audit(
    entities: list[Any],
    threshold: float,
    duration_seconds: float,
    page_count: int,
    metadata_fields_redacted: int = 0,
    non_english_sections: int = 0,
) -> PiiAudit:
    counts: dict[str, Any] = {}
    for entity in entities:
        t = entity.entity_type
        if t not in counts:
            counts[t] = {"count": 0, "min_score": 1.0, "max_score": 0.0}
        counts[t]["count"] += 1
        counts[t]["min_score"] = min(counts[t]["min_score"], entity.score)
        counts[t]["max_score"] = max(counts[t]["max_score"], entity.score)

    entity_counts = {
        t: EntityTypeStats(
            count=v["count"],
            min_score=v["min_score"],
            max_score=v["max_score"],
        )
        for t, v in counts.items()
    }

    return PiiAudit(
        version=1,
        threshold=threshold,
        duration_seconds=duration_seconds,
        page_count=page_count,
        non_english_sections=non_english_sections,
        entity_counts=entity_counts,
        metadata_fields_redacted=metadata_fields_redacted,
    )


__all__ = ["build_audit", "write_pii_audit"]
