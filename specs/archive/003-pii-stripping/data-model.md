# Data Model: PII Stripping

**Date**: 2026-06-25
**Feature**: 003-pii-stripping

## Overview

The PII stripping system processes parsed document text (from Phase 2) and produces anonymized text with deterministic placeholders, an encrypted mapping for value restoration, and an audit trail. The core entities are `PiiEntity` (a detected PII instance), `PiiResult` (the combined output of stripping), `PiiAudit` (detection metadata), and `PiiError` (a fatal stripping failure).

## Entities

### PiiEntity

A single detected piece of personally identifiable information.

**Attributes**:

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `entity_type` | `str` | Presidio entity type or custom type | `"PERSON"`, `"AMOUNT"`, `"EMAIL_ADDRESS"` |
| `original_value` | `str` | The raw text that was detected | `"ABC Corp."`, `"$5,000,000"` |
| `start` | `int` | Start character offset in source text | `45` |
| `end` | `int` | End character offset in source text | `55` |
| `score` | `float` | Confidence score from the detection engine (0.0–1.0) | `0.85` |
| `placeholder` | `str` | Assigned placeholder token | `"[PARTY_A]"`, `"[AMOUNT_1]"` |
| `source` | `str` | Detection method: `"nlp"`, `"regex"`, or `"metadata"` | `"nlp"` |

**Validation Rules**:
- `entity_type` must be non-empty
- `original_value` must be non-empty
- `start` must be ≥ 0
- `end` must be > `start`
- `score` must be between 0.0 and 1.0 (inclusive)
- `placeholder` must match the pattern `\[([A-Z]+_[A-Z0-9]+)\]`

**Example**:
```python
PiiEntity(
    entity_type="PERSON",
    original_value="John Smith",
    start=45,
    end=55,
    score=0.87,
    placeholder="[NAME_1]",
    source="nlp",
)
```

---

### PiiResult

The combined output of PII stripping for a single document.

**Attributes**:

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `stripped_text` | `str` | Document text with PII replaced by placeholders | `"[PARTY_A] agrees to pay [AMOUNT_1]..."` |
| `mapping` | `dict[str, str]` | Placeholder → original value mapping | `{"PARTY_A": "ABC Corp.", "AMOUNT_1": "$5,000,000"}` |
| `entities` | `list[PiiEntity]` | All detected PII entities with metadata | See PiiEntity above |
| `page_count` | `int` | Number of pages processed | `50` |
| `duration_seconds` | `float` | Processing time (seconds) | `2.34` |
| `warnings` | `list[str]` | Non-fatal warnings (e.g., non-English text) | `["Non-English text detected..."]` |

**Relationships**:
- Contains many `PiiEntity` objects
- Produces one `PiiAudit` (derived from entity list)
- Belongs to one document (one PiiResult per document)

**Validation Rules**:
- Every placeholder in `stripped_text` must have a corresponding entry in `mapping`
- Every entry in `mapping` must correspond to at least one placeholder in `stripped_text`
- `page_count` must be ≥ 1
- `duration_seconds` must be ≥ 0

**Example**:
```python
PiiResult(
    stripped_text="[PARTY_A] agrees to pay [PARTY_B] the sum of [AMOUNT_1]...",
    mapping={"PARTY_A": "ABC Corp.", "PARTY_B": "XYZ Inc.", "AMOUNT_1": "$5,000,000"},
    entities=[...],
    page_count=50,
    duration_seconds=2.34,
    warnings=[],
)
```

---

### PiiAudit

Detection metadata for a single stripping run. Contains zero actual PII values.

**Attributes**:

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `version` | `int` | Audit format version | `1` |
| `threshold` | `float` | Confidence threshold used | `0.7` |
| `duration_seconds` | `float` | Processing time (seconds) | `2.34` |
| `page_count` | `int` | Number of pages processed | `50` |
| `non_english_sections` | `int` | Count of non-English sections encountered | `2` |
| `entity_counts` | `dict[str, EntityTypeStats]` | Per-type detection statistics | See below |
| `metadata_fields_redacted` | `int` | Count of metadata fields redacted | `4` |

**EntityTypeStats** (nested):

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `count` | `int` | Number of detected entities of this type | `12` |
| `min_score` | `float` | Lowest confidence score for this type | `0.72` |
| `max_score` | `float` | Highest confidence score for this type | `0.95` |

**Validation Rules**:
- `version` must be 1 (current format)
- `threshold` must be between 0.0 and 1.0
- `duration_seconds` must be ≥ 0
- `page_count` must be ≥ 1
- `non_english_sections` must be ≥ 0
- All `count` values must be ≥ 1
- `min_score` ≤ `max_score`
- **Must contain zero actual PII values** (enforced by construction — only counts and scores)

**Example**:
```python
PiiAudit(
    version=1,
    threshold=0.7,
    duration_seconds=2.34,
    page_count=50,
    non_english_sections=2,
    entity_counts={
        "PERSON": EntityTypeStats(count=12, min_score=0.72, max_score=0.95),
        "ORGANIZATION": EntityTypeStats(count=5, min_score=0.85, max_score=0.92),
        "EMAIL_ADDRESS": EntityTypeStats(count=3, min_score=1.0, max_score=1.0),
        "AMOUNT": EntityTypeStats(count=8, min_score=1.0, max_score=1.0),
    },
    metadata_fields_redacted=4,
)
```

**JSON serialization** (`pii_audit.json`):
```json
{
  "version": 1,
  "threshold": 0.7,
  "duration_seconds": 2.34,
  "page_count": 50,
  "non_english_sections": 2,
  "entities": {
    "PERSON": {"count": 12, "min_score": 0.72, "max_score": 0.95},
    "ORGANIZATION": {"count": 5, "min_score": 0.85, "max_score": 0.92},
    "EMAIL_ADDRESS": {"count": 3, "min_score": 1.0, "max_score": 1.0},
    "AMOUNT": {"count": 8, "min_score": 1.0, "max_score": 1.0}
  },
  "metadata_fields_redacted": 4
}
```

---

### PiiError

A fatal PII stripping failure. Analogous to `ParseError` from Phase 2.

**Attributes**:

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `exit_code` | `int` | Always 9 for PII errors | `9` |
| `category` | `str` | Error category | `"engine_crash"` |
| `clause_heading` | `str \| None` | Clause being processed when failure occurred | `"Payment Terms"` |
| `phase` | `str \| None` | Processing phase: `"regex phase"`, `"NER phase"`, `"anonymizer phase"` | `"NER phase"` |
| `message` | `str` | Human-readable error message | See spec FR-010 |
| `action` | `str` | What the user should do | `"Run with --no-pii to skip stripping. Report this bug."` |

**Categories**:
- `engine_crash` — Presidio analyzer or anonymizer raised an unexpected exception
- `model_not_found` — spaCy `en_core_web_lg` model is not installed
- `invalid_key` — Encryption key is invalid (wrong length)

**Validation Rules**:
- `exit_code` must be 9
- `category` must be one of the predefined categories
- `message` must be non-empty
- `action` must be non-empty
- `message` must NOT contain character offsets or text snippets (only clause heading and phase)

**Example**:
```python
PiiError(
    exit_code=9,
    category="engine_crash",
    clause_heading="Payment Terms",
    phase="NER phase",
    message="PII detection failed while processing clause 'Payment Terms' (NER phase). Run with --no-pii to skip stripping. Report this bug.",
    action="Run with --no-pii to skip stripping. Report this bug.",
)
```

---

## Entity Relationships

```
Document (Phase 2)
    │
    ├── has many → Clause (Phase 2)
    │                 │
    │                 └── processed by → PiiEngine
    │                                       │
    │                                       ├── detects → PiiEntity (many)
    │                                       │
    │                                       └── produces → PiiResult (one per document)
    │                                                         │
    │                                                         ├── contains → mapping (dict)
    │                                                         │                  │
    │                                                         │                  └── written to → pii_map.json (encrypted)
    │                                                         │
    │                                                         └── derives → PiiAudit (one)
    │                                                                          │
    │                                                                          └── written to → pii_audit.json
    │
    └── metadata → redacted unconditionally
```

## Placeholder Assignment

### Type Mapping

| Spec Entity | Presidio Entity Type | Placeholder Prefix | Example |
|------------|---------------------|-------------------|---------|
| Party names | `ORGANIZATION` | `PARTY` | `[PARTY_A]`, `[PARTY_B]` |
| Individual names | `PERSON` | `NAME` | `[NAME_1]`, `[NAME_2]` |
| Email addresses | `EMAIL_ADDRESS` | `EMAIL` | `[EMAIL_1]` |
| Phone numbers | `PHONE_NUMBER` | `PHONE` | `[PHONE_1]` |
| Physical addresses | `LOCATION` | `ADDRESS` | `[ADDRESS_1]` |
| Dates of birth | `DATE_TIME` | `DOB` | `[DOB_1]` |
| Generic dates | `DATE_TIME` | `DATE` | `[DATE_1]` |
| Dollar amounts | `AMOUNT` (custom) | `AMOUNT` | `[AMOUNT_1]`, `[AMOUNT_2]` |
| Tax IDs | `TAX_ID` (custom) | `TAX_ID` | `[TAX_ID_1]` |
| Bank accounts | `IBAN_CODE` / `ACCT` (custom) | `ACCT` | `[ACCT_1]` |
| Passport/DL | `ID_DOCUMENT` (custom) | `ID` | `[ID_1]` |
| Company reg | `REG_NUMBER` (custom) | `REG` | `[REG_1]` |
| Filename (metadata) | — | `FILENAME` | `[FILENAME_1]` |
| Author (metadata) | — | `AUTHOR` | `[AUTHOR_1]` |
| Title (metadata) | — | `TITLE` | `[TITLE_1]` |
| Company (metadata) | — | `COMPANY` | `[COMPANY_1]` |

### Naming Convention

- **PARTY**: Uses letters (`A`, `B`, `C`, …) — per spec examples `[PARTY_A]`, `[PARTY_B]`
- **All other types**: Use sequential numbers (`1`, `2`, `3`, …) — per spec examples `[NAME_1]`, `[AMOUNT_1]`
- **Deterministic ordering**: Unique values sorted alphabetically within each type before numbering. Same entity always gets the same placeholder across re-runs regardless of detection order.

### Assignment Algorithm

```
1. Collect all detected entities from all pages
2. Group by placeholder prefix (PARTY, NAME, EMAIL, ...)
3. For each group:
   a. Extract unique original values
   b. Sort alphabetically (case-insensitive)
   c. For PARTY: assign letters A, B, C, ...
   d. For others: assign numbers 1, 2, 3, ...
4. Build mapping: {placeholder → original_value}
5. Replace in text: process longest values first to avoid substring collisions
```

---

## Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│          Parsed Document (Phase 2 output)                    │
│    Iterator[Clause] + Document metadata                      │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              Config Check                                    │
│  privacy.strip_pii == true?  --no-pii flag?                 │
│  If disabled → warn + pass through unchanged                │
└──────────────────────┬──────────────────────────────────────┘
                       │ (stripping enabled)
                       ▼
┌─────────────────────────────────────────────────────────────┐
│           Metadata Redaction                                 │
│  Filename, author, title, company → typed placeholders      │
│  Store originals in mapping                                  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│           Page-by-Page PII Detection                         │
│  For each page (with 50-char overlap):                      │
│    ├── English text → NLP NER + Regex recognizers           │
│    └── Non-English text → Regex recognizers only + warning  │
│  Collect all PiiEntity instances                             │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│           Placeholder Assignment                             │
│  Group by type → sort alphabetically → assign placeholders  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│           Text Replacement                                   │
│  Replace all entity occurrences with assigned placeholders  │
│  (longest-first to avoid substring collisions)              │
└──────────────────────┬──────────────────────────────────────┘
                       │
           ┌───────────┼───────────┐
           ▼           ▼           ▼
   ┌──────────┐  ┌───────────┐  ┌─────────────┐
   │ Stripped  │  │ pii_map   │  │ pii_audit   │
   │ Text     │  │ .json     │  │ .json       │
   │ (output) │  │ (AES enc) │  │ (no PII)    │
   └──────────┘  └───────────┘  └─────────────┘
```

---

## State Transitions

PII stripping is a one-way transformation per document. Re-stripping always regenerates from the original text (no incremental mode per spec FR-020).

```
Original Text → strip_pii() → PiiResult (stripped text + mapping + audit)
```

When re-stripping occurs (config change, threshold change, explicit re-run):
```
Original Text → strip_pii() → New PiiResult
                                    │
                                    ├── Overwrites pii_map.json
                                    ├── Overwrites pii_audit.json
                                    └── Invalidates downstream cache
                                         (embeddings, comparisons)
```

---

## File Layout (per review)

```
~/.local/share/openreview/reviews/{review_id}/
├── pii_map.json        # Encrypted PII mapping (chmod 600)
├── pii_audit.json      # Detection metadata (no PII values)
├── ... (other review artifacts from future phases)
```

---

## Memory Considerations

**PiiEntity size**: Each `PiiEntity` object uses `@dataclass(slots=True)` — estimated ~150 bytes per entity (excluding string content).

**Typical entity counts**: A 50-page contract with moderate PII yields ~50-200 entities.

**Peak memory breakdown** (excluding NLP model):
- Document text buffer: ~100 KB (one page at a time)
- Overlap buffer: 50 characters (~50 bytes)
- Presidio framework: ~10-20 MB
- Regex recognizers: ~1-2 MB
- Entity collection: ~50 KB (200 entities × ~250 bytes each including string content)
- Mapping dict: ~20 KB
- Audit data: ~2 KB
- **Total processing overhead**: ~15-25 MB (well under 100 MB budget)

---

## Validation Strategy

### Unit Tests

**PiiEntity Validation**:
- Test that `entity_type` is non-empty
- Test that `start` < `end`
- Test that `score` is in [0.0, 1.0]
- Test that `placeholder` matches the expected pattern

**PiiResult Validation**:
- Test mapping/text consistency: every placeholder in text has a mapping entry
- Test mapping/text consistency: every mapping entry has at least one placeholder in text

**PiiAudit Validation**:
- Test that no actual PII values are present in the serialized JSON
- Test that counts match the entity list

**PiiError Validation**:
- Test that `exit_code` is 9
- Test that `message` does not contain character offsets or text snippets

### Integration Tests

**Accuracy Validation**:
- Strip PII from 50 seeded documents (25 auto-generated, 25 manually annotated)
- Calculate recall: (detected entities / total PII entities) ≥ 90%
- Calculate precision: (true PII / all replacements) ≥ 95%

**Round-Trip Validation**:
- Strip → write mapping → read mapping → verify all placeholders resolve

**Memory Validation**:
- Process a 50-page document with tracemalloc
- Assert processing overhead < 100 MB (excluding NLP model baseline)

---

## Future Extensions (Not in Phase 3)

**Context-Aware Disambiguation**:
- Distinguish "Baker McKenzie" as a law firm vs. a person
- Requires coreference resolution or domain-specific NER training

**Cross-Document Entity Alignment**:
- Ensure "ABC Corp." gets `[PARTY_A]` across all documents in a multi-document review
- Requires a global entity registry scoped to the review

**Non-English NER**:
- Arabic NER, CJK NER, Cyrillic NER
- Requires multilingual NLP models
