"""Data models for memo export — MemoFormat enum and memo dataclasses."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


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
    citation_relevance: float | None = None
    citation_locality: float | None = None
    # What strict-mode grounding removed before the memo was built (display-only): the
    # per-finding lines are unreachable in strict mode, so these two counts stand in for them.
    grounding_excluded_unsupported: int = 0
    grounding_excluded_unsure: int = 0


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
    # Claim-wording presence — display-only: it drives one memo note (below),
    # never a verdict, a colour, or which clauses are kept.
    grounding_presence: float | None = None
    # True only for a GROUNDED claim whose wording is absent from the cited clause.
    accepted_despite_absent_wording: bool = False
    # Display-only per-finding risky patterns: the checker was not sure, or the two grounding
    # passes disagreed. Neither is read by any verdict decision, and strict mode removes the
    # findings that carry them before the memo is built.
    not_sure: bool = False
    pass_disagreement: bool = False
    # The "real but wrongly cited" pointer: the clause id the checker named as the section
    # that supports the finding. Display-only — it names that section (the document is never
    # edited) and is never read by a verdict, a colour, or the strict/lenient filtering.
    miscited_to_clause_id: str | None = None


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

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoReport:
        """Reconstruct a MemoReport from memo-JSON produced by render_json()."""
        doc = dict(data.get("document") or {})
        playbook = dict(data.get("playbook") or {})

        overall_raw = dict(data.get("overall") or {})
        overall = MemoSummary(
            recommendation=str(overall_raw.get("recommendation", "")),
            clauses_checked=int(overall_raw.get("clauses_checked", 0)),
            matches=int(overall_raw.get("matches", 0)),
            differences=int(overall_raw.get("differences", 0)),
            confidence_avg=float(overall_raw.get("confidence_avg") or 0.0),
            citation_relevance=overall_raw.get("citation_relevance"),
            citation_locality=overall_raw.get("citation_locality"),
            grounding_excluded_unsupported=int(
                overall_raw.get("grounding_excluded_unsupported", 0)
            ),
            grounding_excluded_unsure=int(overall_raw.get("grounding_excluded_unsure", 0)),
        )

        clauses: list[MemoClause] = []
        for c_raw in data.get("clauses", []):
            c = dict(c_raw)
            citation_raw = c.get("citation")
            citation = None
            if isinstance(citation_raw, dict):
                citation = MemoCitation(
                    clause_id=str(citation_raw.get("clause_id", "")),
                    paragraph_index=int(citation_raw.get("paragraph_index", 0)),
                )
            clauses.append(
                MemoClause(
                    id=str(c.get("id", "")),
                    title=str(c.get("title", "")),
                    playbook_requirement=str(c.get("playbook_requirement", "")),
                    contract_text=str(c.get("contract_text", "")),
                    assessment=str(c.get("assessment", "")),
                    color=str(c.get("color", "")),
                    confidence=float(c.get("confidence") or 0.0),
                    citation=citation,
                    severity=c.get("severity"),
                    source_filename=c.get("source_filename"),
                    grounding_presence=(
                        float(c["grounding_presence"])
                        if c.get("grounding_presence") is not None
                        else None
                    ),
                    accepted_despite_absent_wording=bool(
                        c.get("accepted_despite_absent_wording", False)
                    ),
                    not_sure=bool(c.get("not_sure", False)),
                    pass_disagreement=bool(c.get("pass_disagreement", False)),
                    miscited_to_clause_id=(
                        str(c["miscited_to_clause_id"])
                        if c.get("miscited_to_clause_id") is not None
                        else None
                    ),
                )
            )

        tier_raw = data.get("tier_info")
        tier_info = None
        if isinstance(tier_raw, dict):
            tier_info = MemoTierInfo(
                privacy_tier=str(tier_raw.get("privacy_tier", "")),
                pii_stripped=bool(tier_raw.get("pii_stripped", False)),
                entities_redacted=int(tier_raw.get("entities_redacted", 0)),
            )

        return cls(
            memo_version=str(data.get("memo_version", "1.0")),
            mode=str(data.get("mode", "precheck")),
            document_name=str(doc.get("name", "")),
            playbook_name=str(playbook.get("name", "")),
            playbook_version=str(playbook.get("version", "")),
            review_date=str(data.get("review_date", "")),
            overall=overall,
            clauses=clauses,
            disclaimer=str(data.get("disclaimer", "")),
            tier_info=tier_info,
        )
