# Data Model: Single-Party Review

**Spec**: specs/011-single-party-review/spec.md
**Date**: 2026-07-02

## Entity Overview

```
Playbook (1) ──→ Category (1..*) ──→ PositionDef (1 per position)
                                                      
ReviewReport (1) ──→ ClauseAssessment (0..*)         
                           │                         
                    AssessmentSource (1 per agent stage)
```

## Entities

### ClauseAssessment

The outcome of running a single clause through the extraction + QA + comparison pipeline.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `clause_id` | `str` | Yes | — | Unique clause identifier from `stream_clauses()` |
| `clause_text` | `str` | Yes | — | The full clause text (truncated in terminal output to 200 chars) |
| `playbook_category` | `str` | Yes | — | Matching playbook category ID, or `"no-match"` if none matched |
| `position` | `Position` | Yes | — | Final position after QA verification: favorable, neutral, unfavorable, uncertain |
| `confidence` | `float` | Yes | — | Extraction agent's confidence (0.0–1.0). QA may flag disagreement but does not modify this value. |
| `citation` | `str` | Yes | — | Direct quote from clause text supporting the assessment |
| `qa_verdict` | `QAVerdict` | Yes | — | agree, disagree, uncertain |
| `qa_revised_position` | `Position` | No | — | If QA disagreed, the position QA would assign. `None` if QA agreed. |
| `qa_revised_rationale` | `str` | No | — | If QA disagreed, the rationale for the revision. `None` if QA agreed. |
| `is_amber` | `bool` | Yes | `False` | `True` if QA disagreed, or confidence < 0.5, or any stage failed |
| `extraction_model` | `str` | Yes | — | Model slot used for extraction |
| `qa_model` | `str` | Yes | — | Model slot used for QA verification |
| `error` | `str` | No | — | Error message if any stage failed. `None` on success. |

**Validation Rules**:
- `confidence` MUST be in range 0.0–1.0.
- `position` is the **final** position after QA. If QA disagrees and supplies a revised position, `position` is still what the extraction agent assigned; `qa_revised_position` holds the QA revision. The `is_amber` flag signals the disagreement to the user. (This preserves both opinions for downstream analysis.)
- `citation` MUST be a substring of `clause_text` (validated by QA agent).
- If `error` is non-`None`, `is_amber` is automatically `True`.
- `playbook_category` = `"no-match"` means no playbook category matched; position will be `"uncertain"` unless overridden.

### Position

Enum: `favorable`, `neutral`, `unfavorable`, `uncertain`

### QAVerdict

Enum: `agree`, `disagree`, `uncertain`

### AssessmentSource

Captures which model slot was used for each stage of a single clause assessment.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `extraction_model` | `str` | Yes | Model slot used for extraction |
| `qa_model` | `str` | Yes | Model slot used for QA verification |
| `processing_time_ms` | `int` | Yes | Total wall-clock time for this clause (both stages) |

### Playbook

A collection of clause categories with position definitions, authored in YAML.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `id` | `str` | Yes | — | Playbook identifier (e.g., `"precheck-nda-v1"`) |
| `mode` | `str` | Yes | — | Product mode this playbook is for (e.g., `"precheck"`) |
| `categories` | `list[Category]` | Yes | — | Array of clause category entries (≥1) |
| `metadata` | `PlaybookMetadata` | Yes | — | Version, description, author |

**Validation Rules**:
- `categories` MUST contain at least 1 entry.
- Each `Category.id` MUST be unique within the playbook.
- `mode` MUST match a known product mode (validated against mode registry).

### PlaybookMetadata

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `version` | `str` | Yes | — | Semantic version string (e.g., `"1.0.0"`) |
| `description` | `str` | Yes | — | Plain English description of the playbook's scope |
| `author` | `str` | Yes | — | Author or organisation name |

### Category

A single clause category within a playbook.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `id` | `str` | Yes | — | Unique category identifier (e.g., `"confidentiality-term"`) |
| `name` | `str` | Yes | — | Human-readable category name (e.g., `"Confidentiality Term"`) |
| `description` | `str` | Yes | — | Plain English description of the clause type |
| `favorable` | `PositionDef` | Yes | — | Definition and exemplars for favorable position |
| `neutral` | `PositionDef` | Yes | — | Definition and exemplars for neutral position |
| `unfavorable` | `PositionDef` | Yes | — | Definition and exemplars for unfavorable position |
| `default_position` | `Position` | Yes | — | Default position when clause matches category but no specific indicators found. Must be favorable, neutral, or unfavorable (never uncertain). |

### PositionDef

Definition of a single position within a category.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `description` | `str` | Yes | — | Plain English description of what makes a clause this position |
| `exemplars` | `list[str]` | Yes | — | Example language patterns (≥1). Used for heading matching and semantic retrieval. |

**Validation Rules**:
- `exemplars` MUST contain at least 1 string.
- Each exemplar SHOULD be a realistic phrase from an NDA.

### ReviewReport

The top-level output of a single review run.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `document` | `DocMeta` | Yes | — | Document metadata |
| `assessments` | `list[ClauseAssessment]` | Yes | — | Per-clause assessments (one per clause) |
| `summary` | `ReviewSummary` | Yes | — | Aggregate statistics |
| `schema_version` | `str` | Yes | `"1.0.0"` | Output schema version for downstream compatibility |
| `playbook_id` | `str` | Yes | — | ID of the playbook used for this review |
| `generated_at` | `datetime` | Yes | — | ISO 8601 timestamp of report generation |

### DocMeta

Document metadata from the parsing phase.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `filename` | `str` | Yes | — | Original filename |
| `page_count` | `int` | Yes | — | Number of pages |
| `clause_count` | `int` | Yes | — | Number of clauses detected |
| `parsed_at` | `datetime` | No | — | ISO 8601 timestamp of parse time |
| `pii_stripped` | `bool` | Yes | `False` | Whether PII was stripped before processing |

### ReviewSummary

Aggregate statistics across all assessments.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `favorable_count` | `int` | Yes | — | Count of favorable assessments |
| `neutral_count` | `int` | Yes | — | Count of neutral assessments |
| `unfavorable_count` | `int` | Yes | — | Count of unfavorable assessments |
| `uncertain_count` | `int` | Yes | — | Count of uncertain assessments |
| `no_match_count` | `int` | Yes | — | Count of no-match clauses |
| `amber_count` | `int` | Yes | — | Count of clauses flagged Amber (QA disagreement or low confidence) |
| `avg_confidence` | `float` | Yes | — | Mean confidence across all non-no-match clauses |

## State Transitions

Each clause goes through a deterministic pipeline:

```
stream_clauses()
       │
       ▼
  ┌────────────────┐
  │  Heading Match  │ ──fast path──► ✓ → category_id, confidence
  │  (fast path)    │                  ✗ → proceed to semantic
  └────────────────┘
       │ (no match)
       ▼
  ┌────────────────┐
  │ Semantic Match  │ ──embedding──► ✓ → category_id, confidence
  │  (fallback)     │                  ✗ → "no-match"
  └────────────────┘
       │
       ▼
  ┌────────────────┐
  │ Extraction      │ ──SLM/LLM──► position, confidence, citation
  │  Agent          │
  └────────────────┘
       │
       ▼
  ┌────────────────┐
  │  QA Agent       │ ──verify──► verdict (agree/disagree/uncertain)
  │                 │              revised_position (if disagree)
  └────────────────┘
       │
       ▼
  ┌────────────────┐
  │  Comparison     │ ──no-op──► pass through (placeholder for Phase 2)
  │  Agent          │
  └────────────────┘
       │
       ▼
  ┌────────────────┐
  │  is_amber?      │ ← QA disagrees OR confidence < 0.5 OR any error
  └────────────────┘
       │
       ▼
  Append to assessments list
```

## JSON Schema (ReviewReport)

The JSON output schema is versioned. Current version: `1.0.0`.

```json
{
  "schema_version": "1.0.0",
  "document": {
    "filename": "nda.docx",
    "page_count": 12,
    "clause_count": 28,
    "parsed_at": "2026-07-02T14:30:00Z",
    "pii_stripped": true
  },
  "playbook_id": "precheck-nda-v1",
  "generated_at": "2026-07-02T14:31:00Z",
  "assessments": [
    {
      "clause_id": "clause-001",
      "clause_text": "The receiving party shall hold all Confidential Information in confidence for a period of three (3) years...",
      "playbook_category": "confidentiality-term",
      "position": "favorable",
      "confidence": 0.92,
      "citation": "for a period of three (3) years",
      "qa_verdict": "agree",
      "qa_revised_position": null,
      "qa_revised_rationale": null,
      "is_amber": false,
      "extraction_model": "ollama/llama3.2:3b",
      "qa_model": "ollama/llama3.2:3b",
      "error": null
    }
  ],
  "summary": {
    "favorable_count": 12,
    "neutral_count": 10,
    "unfavorable_count": 4,
    "uncertain_count": 2,
    "no_match_count": 0,
    "amber_count": 3,
    "avg_confidence": 0.85
  }
}
```
