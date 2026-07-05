"""Data models for memo export — MemoFormat enum and memo dataclasses."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class MemoFormat(StrEnum):
    """Supported memo export formats."""

    MARKDOWN = "md"
    JSON = "json"
    DOCX = "docx"


@dataclass
class MemoCitation:
    """A record linking a claim to a location in the source document."""

    clause_id: str
    paragraph_index: int


@dataclass
class MemoTierInfo:
    """Privacy tier metadata for the memo."""

    privacy_tier: str
    pii_stripped: bool
    entities_redacted: int


@dataclass
class MemoSummary:
    """Aggregate statistics for the memo."""

    recommendation: str
    clauses_checked: int
    matches: int
    differences: int
    confidence_avg: float


@dataclass
class MemoClause:
    """Per-clause assessment data for memo output."""

    id: str
    title: str
    playbook_requirement: str
    contract_text: str
    assessment: str
    color: str
    confidence: float
    citation: MemoCitation | None = None
    severity: str | None = None
    source_filename: str | None = None


@dataclass
class MemoReport:
    """Top-level memo report wrapping review data with memo-specific fields."""

    memo_version: str
    mode: str
    document_name: str
    playbook_name: str
    playbook_version: str
    review_date: str
    overall: MemoSummary
    clauses: list[MemoClause]
    disclaimer: str
    tier_info: MemoTierInfo | None = None
