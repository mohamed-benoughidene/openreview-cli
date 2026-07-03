# Data Model: Citation Grounding Discriminator (N-5)

**Date**: 2026-07-03 | **Spec**: `specs/012-citation-grounding/spec.md`

---

## GroundingVerdict (enum)

```python
from enum import StrEnum

class GroundingVerdict(StrEnum):
    """Verdict for a single claim's citation grounding."""
    GROUNDED = "grounded"        # Provenance verified — claim is supported by the cited clause
    UNGROUNDED = "ungrounded"    # No valid provenance — claim is not supported by the source
    UNCERTAIN = "uncertain"      # Provenance ambiguous or below confidence threshold
```

- Stored as string in JSON/DB for readability.
- `UNCERTAIN` is the safe default when confidence is at the boundary (strict mode treats as ungrounded).

---

## CitationProvenance (dataclass)

```python
from dataclasses import dataclass


@dataclass(slots=True)
class CitationProvenance:
    """A record linking a single claim to a specific location in the source document.

    A claim may have zero (ungrounded), one (grounded), or multiple (multi-clause) provenances.
    """
    clause_id: str          # Identifier of the source clause (e.g., "4.3", "confidentiality")
    paragraph_index: int    # Position within the clause (0-based)
    confidence: float       # Discriminator confidence in this provenance (0.0-1.0)
```

- `clause_id` must match an existing clause in the parsed `Document`.
- `paragraph_index` must be < the number of paragraphs in the cited clause.
- `confidence` is the LLM's reported confidence (extracted from response).
- Multiple provenances are assigned in lenient mode for multi-clause claims.

---

## GroundingResult (dataclass)

```python
from dataclasses import dataclass


@dataclass(slots=True)
class GroundingResult:
    """Per-claim grounding result."""
    claim_index: int                       # Index into ReviewReport's assessments list
    verdict: GroundingVerdict              # Grounded / Ungrounded / Uncertain
    provenances: list[CitationProvenance]  # May be empty (ungrounded) or multiple (multi-clause)
    reason: str | None = None             # Explanation if ungrounded or uncertain
```

- `claim_index` links back to the original `ClauseAssessment` in the `ReviewReport`.
- `reason` is populated when verdict is UNGROUNDED or UNCERTAIN (e.g., "paragraph index 12 does not exist in clause 4.3").

---

## CGMetrics (dataclass)

```python
from dataclasses import dataclass


@dataclass(slots=True)
class CGMetrics:
    """Structural citation grounding metrics — computed deterministically, no LLM required."""
    citation_precision: float   # CP: % of grounded claims whose clause_id exists in source (0.0-1.0)
    citation_relevance: float   # CR: % of grounded claims whose text appears in cited clause (0.0-1.0)
    citation_locality: float    # CL: avg paragraph index validity (0.0-1.0)
```

- All three metrics are floats between 0.0 and 1.0.
- Computed via `compute_cg_metrics()` in `metrics.py`.
- `citation_precision`: pure existence check — does the cited `clause_id` exist in `Document.clauses`?
- `citation_relevance`: substring match — does the claim text appear (case-insensitive) in the cited clause's full text?
- `citation_locality`: paragraph index validity — is the claim's `paragraph_index` < the cited clause's total paragraph count?

---

## CGReport (dataclass)

```python
from dataclasses import dataclass
from typing import Literal


@dataclass
class CGReport:
    """Aggregate output of a discriminator run."""
    verdicts: list[GroundingResult]           # Per-claim results
    mode: Literal["strict", "lenient"]        # Mode used for this run
    metrics: CGMetrics                        # CP, CR, CL scores
    total_claims: int                         # Total claims received
    grounded_count: int                       # Count of GROUNDED verdicts
    ungrounded_count: int                     # Count of UNGROUNDED verdicts
    uncertain_count: int                      # Count of UNCERTAIN verdicts

    def merge_into(self, report: ReviewReport) -> ReviewReport:
        """Merge grounding results into a ReviewReport.

        For each GroundingResult, sets the corresponding ClauseAssessment's
        grounding_verdict, grounding_provenances, and grounding_confidence fields.
        In strict mode, skips UNGROUNDED and UNCERTAIN claims.
        """
        ...
```

- `merge_into()` is the primary integration method — it populates the three new optional fields on each `ClauseAssessment`.
- In strict mode, the method removes claims where verdict is UNGROUNDED or UNCERTAIN from the report's `assessments` list and logs a warning for each removed claim.
- In lenient mode, all claims are retained; ungrounded/uncertain claims have their verdict set on the assessment.

---

## DiscriminationAuditEntry (dataclass)

```python
from dataclasses import dataclass
from datetime import datetime


@dataclass
class DiscriminationAuditEntry:
    """Single audit record for one discrimination decision."""
    claim_hash: str                    # SHA-256 of claim text (avoids storing raw PII-containing text)
    verdict: GroundingVerdict          # The verdict assigned
    confidence: float                  # Discriminator confidence (0.0-1.0)
    provenances: list[CitationProvenance]  # Provenances found (may be empty for ungrounded)
    reason: str | None = None          # Explanation if ungrounded or uncertain
    timestamp: datetime = None         # When the decision was made (defaults to now)
```

- `claim_hash` uses `hashlib.sha256()` of the claim text encoded as UTF-8. This avoids storing raw PII-containing text in the audit log (Constitution §I).
- `reason` documents why the verdict was assigned, particularly for UNGROUNDED and UNCERTAIN verdicts.

---

## GroundingAuditLog (class)

```python
class GroundingAuditLog:
    """Local file audit trail for grounding discrimination decisions."""

    def __init__(self, output_dir: str | Path) -> None: ...

    def append(self, entry: DiscriminationAuditEntry) -> None: ...

    def flush(self) -> None: ...
```

- Writes entries as JSON lines (`.jsonl`) to `{output_dir}/grounding-audit.jsonl`.
- `append()` writes immediately (no buffering) to survive crash.
- `flush()` is a no-op if unbuffered; exists for interface completeness.

---

## ClauseAssessment additions (3 optional fields)

```python
# In src/openreview_cli/review/models.py

@dataclass
class ClauseAssessment:
    # ... existing fields ...

    # NEW: Citation grounding discriminator fields (all optional, default None)
    grounding_verdict: GroundingVerdict | None = None
    grounding_provenances: list[CitationProvenance] | None = None
    grounding_confidence: float | None = None
```

- All three fields default to `None` — fully backwards compatible.
- Existing `ClauseAssessment` instances without grounding data remain valid and serializable.
- `grounding_provenances` is `None` when not processed, `[]` when processed but ungrounded, or populated when grounded.

---

## ReviewReport additions (no new fields)

The `ReviewReport` class itself gets no new fields. Grounding data is carried on individual `ClauseAssessment` objects. The `CGReport.merge_into()` method handles populating them.

---

## Serialization format (JSON)

```json
{
  "assessments": [
    {
      "clause_id": "4.3",
      "confidence": 0.92,
      "citation_valid": true,
      "extracted_text": "The receiving party shall...",
      "grounding_verdict": "grounded",
      "grounding_provenances": [
        {
          "clause_id": "4.3",
          "paragraph_index": 2,
          "confidence": 0.95
        }
      ],
      "grounding_confidence": 0.95
    }
  ],
  "metrics": {
    "citation_precision": 1.0,
    "citation_relevance": 0.92,
    "citation_locality": 0.98
  }
}
```

- Grounding fields are `null` when the discriminator did not run.
- `grounding_provenances` is an empty list `[]` when processed and ungrounded.
