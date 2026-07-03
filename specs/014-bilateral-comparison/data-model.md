# Data Model — Bilateral Comparison (NX-1)

**Feature**: 014-bilateral-comparison | **Date**: 2026-07-03
**Spec Reference**: [`spec.md`](./spec.md) §5 (Key Entities)

---

## Overview

The bilateral comparison data model extends the existing spec 011 review
models (`ClauseAssessment`, `DocMeta`, `ReviewReport`) with comparison-specific
entities. Every paired assessment wraps two single-party `ClauseAssessment`
instances and adds divergence metadata. The model adds no new dependencies and
uses only `@dataclass(slots=True)` for memory efficiency (Constitution §III).

---

## Entity: RCBSFDimension

Enum for the 5-dimension risk taxonomy from P-14, plus "no_divergence".

```python
from enum import StrEnum

class RCBSFDimension(StrEnum):
    """RCBSF 5-dimension risk taxonomy for bilateral divergence."""
    category = "category"        # Clause types differ between parties
    location = "location"        # Same concept in different sub-clauses
    evidence = "evidence"        # Different evidentiary basis/standard
    issue = "issue"             # Risk assessment differs
    suggestion = "suggestion"    # Remedy/action differs
    no_divergence = "no_divergence"  # No material divergence detected
```

**Blueprint references**: [P-14] (RCBSF taxonomy), spec §3 FR-3

---

## Entity: MatchingMethod

Enum describing how two clauses were aligned.

```python
class MatchingMethod(StrEnum):
    """How a clause pair was aligned."""
    exact_heading = "exact_heading"          # Case-insensitive heading match
    fuzzy_heading = "fuzzy_heading"          # difflib.SequenceMatcher >= threshold
    positional = "positional"               # Same positional index fallback
    unmatched_a = "unmatched_a"             # Clause only in Party A's document
    unmatched_b = "unmatched_b"             # Clause only in Party B's document
```

---

## Entity: AlignmentPair

A single matched or unmatched clause pair between two documents.

```python
from dataclasses import dataclass, field

@dataclass(slots=True)
class AlignmentPair:
    """A matched or unmatched clause pair across two documents."""

    heading: str
    """The shared clause heading (best-match heading for fuzzy)."""

    clause_id_a: str | None = None
    """Clause ID in Party A's document. None if unmatched."""

    clause_id_b: str | None = None
    """Clause ID in Party B's document. None if unmatched."""

    alignment_quality: float = 0.0
    """Match quality 0.0–1.0 (1.0 = exact heading, lower = fuzzy/positional).
    Zero for unmatched pairs."""

    match_method: MatchingMethod = MatchingMethod.positional
    """How this pair was aligned."""

    index_a: int = 0
    """Positional index in Party A's clause list."""

    index_b: int = 0
    """Positional index in Party B's clause list."""
```

**Blueprint references**: spec §5 (AlignmentTable), FR-1 (heading-based
alignment with quality metric), Q4/NC-2 (alignment_quality field)

---

## Entity: AlignmentTable

The full output of the clause alignment pass.

```python
@dataclass(slots=True)
class AlignmentTable:
    """Complete clause alignment output for a bilateral comparison."""

    pairs: list[AlignmentPair]
    """All matched pairs, then unmatched-A, then unmatched-B."""

    unmatched_a_ids: list[str]
    """Clause IDs present in Document A only."""

    unmatched_b_ids: list[str]
    """Clause IDs present in Document B only."""

    total_a: int
    """Total clauses found in Document A."""

    total_b: int
    """Total clauses found in Document B."""

    alignment_rate: float
    """Percentage of clauses successfully paired (0.0–1.0).
    Calculated as: matched_pairs * 2 / (total_a + total_b)."""

    @property
    def matched_count(self) -> int:
        """Number of successfully matched clause pairs."""
        return len(self.pairs)
```

**Blueprint references**: spec §5 (AlignmentTable)

---

## Entity: PairedAssessment

The outcome of comparing one aligned clause pair. This is the atomic unit
of comparison output.

```python
@dataclass(slots=True)
class PairedAssessment:
    """Comparison result for one aligned clause pair."""

    pair_id: str
    """Unique identifier for this clause pair (e.g., 'pair-001')."""

    clause_heading: str
    """The shared clause heading."""

    party_a_assessment: ClauseAssessment
    """Single-party assessment for Party A's version (spec 011)."""

    party_b_assessment: ClauseAssessment
    """Single-party assessment for Party B's version (spec 011)."""

    divergence: RCBSFDimension = RCBSFDimension.no_divergence
    """Detected divergence dimension or no_divergence."""

    confidence: float = 0.0
    """Confidence score 0.0–1.0 for the divergence detection."""

    alignment_quality: float = 1.0
    """Match quality of the clause alignment 0.0–1.0.
    Always included in JSON; terminal only under --verbose per Q4/NC-2."""

    color: AssessmentColor | None = None
    """Paired three-color status: Green (no divergence), Amber (uncertain),
    Red (material divergence found). Set at output time per spec 013."""

    citations: list[str] = field(default_factory=list)
    """Text excerpts from both sides supporting the divergence detection."""

    rationale: str = ""
    """Comparison agent's reasoning for the divergence classification."""

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in range 0.0-1.0")
        if not 0.0 <= self.alignment_quality <= 1.0:
            raise ValueError("alignment_quality must be in range 0.0-1.0")

    @property
    def has_divergence(self) -> bool:
        """True if a material divergence was detected."""
        return self.divergence != RCBSFDimension.no_divergence

    @property
    def is_amber(self) -> bool:
        """True if the paired status is Amber (uncertain)."""
        return self.color == AssessmentColor.amber if self.color else False
```

**Blueprint references**: spec §5 (PairedAssessment), §3 FR-2 (paired
assessment model), FR-3 (RCBSF divergence), FR-4 (three-color), Q4
(alignment_quality), Q5 (divergence always in model)

---

## Entity: ComparisonSummary

Aggregate statistics for a comparison run.

```python
@dataclass(slots=True)
class ComparisonSummary:
    """Aggregate statistics for a bilateral comparison run."""

    total_pairs: int = 0
    """Number of aligned clause pairs processed."""

    divergences: int = 0
    """Number of pairs with a detected divergence."""

    divergences_by_dimension: dict[str, int] = field(default_factory=dict)
    """Count per RCBSF dimension, e.g. {'category': 2, 'evidence': 1}."""

    unmatched_a: int = 0
    """Clauses in Party A's document only."""

    unmatched_b: int = 0
    """Clauses in Party B's document only."""

    agreement_rate: float = 0.0
    """Percentage of pairs with no divergence (0.0–1.0)."""

    green_count: int = 0
    """Pairs with Green (no material divergence) status."""

    amber_count: int = 0
    """Pairs with Amber (uncertain) status."""

    red_count: int = 0
    """Pairs with Red (material divergence) status."""

    avg_alignment_quality: float = 0.0
    """Average alignment quality across all pairs."""

    confidence_threshold: float = 0.7
    """The confidence threshold used for this run."""
```

**Blueprint references**: spec §5 (ComparisonSummary), §3 FR-8 (confidence
threshold), §4 (success criteria)

---

## Entity: ComparisonReport

Top-level output of a bilateral comparison run. The main return type from
the comparison pipeline.

```python
@dataclass(slots=True)
class ComparisonReport:
    """Complete output of a bilateral comparison run."""

    experimental: bool = True
    """Always True — marks this output as experimental NX-1."""

    disclaimer: str = ""
    """Accuracy caveat and legal disclaimer text."""

    document_a: DocMeta
    """Document A metadata (filename, page count, parse timestamp)."""

    document_b: DocMeta
    """Document B metadata."""

    alignment: AlignmentTable
    """Clause alignment results."""

    assessments: list[PairedAssessment]
    """Per-pair comparison results."""

    summary: ComparisonSummary
    """Aggregate statistics."""

    schema_version: str = "1.0.0"
    """Output schema version for downstream compatibility."""
```

**Blueprint references**: spec §5 (ComparisonReport), FR-6 (terminal and
JSON output), FR-5 (experimental disclaimer)

---

## ComparisonRules: JSON Schema

The JSON output SHALL conform to this schema:

```json
{
  "schema_version": "1.0.0",
  "experimental": true,
  "disclaimer": "...",
  "document_a": {
    "filename": "my-nda.pdf",
    "page_count": 12,
    "clause_count": 28,
    "pii_stripped": true,
    "parsed_at": "2026-07-03T12:00:00Z"
  },
  "document_b": {
    "filename": "their-nda.pdf",
    "page_count": 15,
    "clause_count": 30,
    "pii_stripped": true,
    "parsed_at": "2026-07-03T12:00:05Z"
  },
  "alignment": {
    "pairs": [...],
    "unmatched_a_ids": ["clause-014"],
    "unmatched_b_ids": ["clause-017", "clause-023"],
    "total_a": 28,
    "total_b": 30,
    "alignment_rate": 0.93
  },
  "assessments": [
    {
      "pair_id": "pair-001",
      "clause_heading": "Confidentiality",
      "party_a_assessment": { "...": "..." },
      "party_b_assessment": { "...": "..." },
      "divergence": "evidence",
      "confidence": 0.82,
      "alignment_quality": 1.0,
      "color": "red",
      "citations": [
        "Party A: 'shall use reasonable efforts'",
        "Party B: 'shall use best efforts'"
      ],
      "rationale": "The evidentiary standard differs: reasonable vs best efforts"
    }
  ],
  "summary": {
    "total_pairs": 25,
    "divergences": 3,
    "divergences_by_dimension": {
      "evidence": 1,
      "suggestion": 2
    },
    "unmatched_a": 1,
    "unmatched_b": 2,
    "agreement_rate": 0.88,
    "green_count": 20,
    "amber_count": 2,
    "red_count": 3,
    "avg_alignment_quality": 0.94,
    "confidence_threshold": 0.7
  }
}
```

---

## Entity Relationship Diagram

```
ComparisonReport
├── document_a: DocMeta           (spec 011 — reused as-is)
├── document_b: DocMeta           (spec 011 — reused as-is)
├── alignment: AlignmentTable
│   └── pairs[]: AlignmentPair
│       ├── clause_id_a → Clause (spec 011)
│       ├── clause_id_b → Clause (spec 011)
│       ├── match_method: MatchingMethod
│       └── alignment_quality: float
├── assessments[]: PairedAssessment
│   ├── party_a_assessment: ClauseAssessment  (spec 011 — reused as-is)
│   ├── party_b_assessment: ClauseAssessment  (spec 011 — reused as-is)
│   ├── divergence: RCBSFDimension
│   ├── confidence: float
│   ├── alignment_quality: float
│   └── color: AssessmentColor    (spec 013 — reused as-is)
└── summary: ComparisonSummary
    ├── divergences_by_dimension: dict[RCBSFDimension, int]
    └── green/amber/red_count (spec 013 pattern)
```

**No new base classes are introduced.** The model reuses `ClauseAssessment`,
`DocMeta`, and `AssessmentColor` from existing specs. All new entities are
comparison-specific wrappers and containers.

---

## Model Validation Rules

1. **PairedAssessment.confidence** MUST be 0.0–1.0 (validated in
   `__post_init__`)
2. **PairedAssessment.alignment_quality** MUST be 0.0–1.0 (validated in
   `__post_init__`)
3. **AlignmentTable.alignment_rate** = matched_pairs * 2 / (total_a + total_b)
4. **AlignmentTable.pairs** SHALL always list matched pairs first, then
   unmatched A, then unmatched B
5. **ComparisonSummary.agreement_rate** = pairs with no_divergence / total_pairs
6. **RCBSFDimension.no_divergence** is NOT counted in
   `divergences_by_dimension` — it represents absence of divergence, not
   a dimension

**Blueprint references**: Constitution §III (dataclass slots), §3 FR-2–FR-8
