from __future__ import annotations

import re
from dataclasses import dataclass

# Regex for validation of placeholders like [PARTY_A], [AMOUNT_1]
PLACEHOLDER_REGEX = re.compile(r"^\[[A-Z]+_[A-Z0-9]+\]$")


@dataclass(slots=True)
class PiiEntity:
    entity_type: str
    original_value: str
    start: int
    end: int
    score: float
    placeholder: str
    source: str  # "nlp", "regex", or "metadata"

    def __post_init__(self) -> None:
        if not self.entity_type:
            raise ValueError("entity_type must be non-empty")
        if not self.original_value:
            raise ValueError("original_value must be non-empty")
        if self.start < 0:
            raise ValueError(f"start must be >= 0, got {self.start}")
        if self.end <= self.start:
            raise ValueError(f"end must be > start, got end={self.end}, start={self.start}")
        if not (0.0 <= self.score <= 1.0):
            raise ValueError(f"score must be between 0.0 and 1.0, got {self.score}")
        if not PLACEHOLDER_REGEX.match(self.placeholder):
            raise ValueError(f"placeholder must match pattern [TYPE_N], got '{self.placeholder}'")
        if self.source not in ("nlp", "regex", "metadata"):
            raise ValueError(f"invalid source: {self.source}")


@dataclass(slots=True)
class PiiResult:
    stripped_text: str
    mapping: dict[str, str]  # {placeholder_key: original_value} without brackets
    entities: list[PiiEntity]
    page_count: int
    duration_seconds: float
    warnings: list[str]
    failed_pages: list[int] | None = None

    def __post_init__(self) -> None:
        if self.page_count < 1:
            raise ValueError(f"page_count must be >= 1, got {self.page_count}")
        if self.duration_seconds < 0:
            raise ValueError(f"duration_seconds must be >= 0, got {self.duration_seconds}")

        # Verify mapping and placeholder consistency
        # mapping keys do not have brackets (e.g. 'PARTY_A') but in text they are '[PARTY_A]'
        for key in self.mapping:
            placeholder = f"[{key}]"
            if placeholder not in self.stripped_text:
                raise ValueError(
                    f"Mapping key '{key}' has no corresponding placeholder in stripped text"
                )

        # Also check that every placeholder in the stripped text is in mapping
        # We can find all patterns matching [WORD_ALPHANUM] in stripped_text
        found_placeholders = re.findall(r"\[([A-Z]+_[A-Z0-9]+)\]", self.stripped_text)
        for placeholder in found_placeholders:
            if placeholder not in self.mapping:
                raise ValueError(
                    f"Placeholder '{placeholder}' in stripped text is missing from mapping"
                )


@dataclass(slots=True)
class EntityTypeStats:
    count: int
    min_score: float
    max_score: float

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError(f"count must be >= 1, got {self.count}")
        if self.min_score > self.max_score:
            raise ValueError(
                f"min_score must be <= max_score, got min={self.min_score}, max={self.max_score}"
            )
        if not (0.0 <= self.min_score <= 1.0):
            raise ValueError(f"min_score must be between 0.0 and 1.0, got {self.min_score}")
        if not (0.0 <= self.max_score <= 1.0):
            raise ValueError(f"max_score must be between 0.0 and 1.0, got {self.max_score}")


@dataclass
class PiiAudit:
    version: int
    threshold: float
    duration_seconds: float
    page_count: int
    non_english_sections: int
    entity_counts: dict[str, EntityTypeStats]
    metadata_fields_redacted: int

    def __post_init__(self) -> None:
        if self.version != 1:
            raise ValueError(f"version must be 1, got {self.version}")
        if not (0.0 <= self.threshold <= 1.0):
            raise ValueError(f"threshold must be between 0.0 and 1.0, got {self.threshold}")
        if self.duration_seconds < 0:
            raise ValueError(f"duration_seconds must be >= 0, got {self.duration_seconds}")
        if self.page_count < 1:
            raise ValueError(f"page_count must be >= 1, got {self.page_count}")
        if self.non_english_sections < 0:
            raise ValueError(f"non_english_sections must be >= 0, got {self.non_english_sections}")
        if self.metadata_fields_redacted < 0:
            raise ValueError(
                f"metadata_fields_redacted must be >= 0, got {self.metadata_fields_redacted}"
            )


@dataclass
class PiiError(Exception):
    exit_code: int
    category: str
    clause_heading: str | None
    phase: str | None
    message: str
    action: str

    def __post_init__(self) -> None:
        if self.exit_code != 9:
            raise ValueError(f"exit_code must be 9, got {self.exit_code}")
        if self.category not in ("engine_crash", "model_not_found", "invalid_key"):
            raise ValueError(f"invalid category: {self.category}")
        if not self.message:
            raise ValueError("message must be non-empty")
        if not self.action:
            raise ValueError("action must be non-empty")
        if re.search(r"\b(offset|index|position|at character|char)\b", self.message, re.IGNORECASE):
            raise ValueError("message contains forbidden offset details")

    def __str__(self) -> str:
        return self.message

    def __repr__(self) -> str:
        return f"PiiError({self.category}: {self.message})"


class PartialProcessingError(Exception):
    """Raised when PII stripping succeeds on some pages but fails on others."""

    def __init__(
        self,
        failed_pages: list[int],
        successful_pages: list[int],
        error_messages: dict[int, str],
    ) -> None:
        self.failed_pages = failed_pages
        self.successful_pages = successful_pages
        self.error_messages = error_messages
        super().__init__(
            f"PII processing failed on {len(failed_pages)} page(s): "
            f"{', '.join(str(p) for p in failed_pages)}"
        )
