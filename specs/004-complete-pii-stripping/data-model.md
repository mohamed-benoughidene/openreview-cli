# Data Model: Complete PII Stripping Integration

**Date**: 2026-06-30 | **Feature**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

## Entity Overview

The PII stripping integration introduces four core entities that manage the lifecycle of personally identifiable information from detection through encrypted storage to eventual deletion.

```
┌─────────────┐     ┌──────────────────┐     ┌──────────────┐
│  Document   │────▶│   PII Entity     │────▶│   Encrypted  │
│  (input)    │     │  (detected PII)  │     │   Mapping    │
└─────────────┘     └──────────────────┘     └──────────────┘
       │                                            │
       │                                            │
       ▼                                            ▼
┌─────────────┐                            ┌──────────────────┐
│ PII Audit   │                            │   PII Cache      │
│   Trail     │                            │  (SQLite row)    │
└─────────────┘                            └──────────────────┘
```

## Entity Definitions

### 1. PiiEntity

A detected instance of personally identifiable information in a document.

**Fields**:
- `entity_type`: str — Type of PII (e.g., "PERSON", "DATE", "MONEY", "ADDRESS", "EMAIL", "PHONE", "ORGANIZATION", etc.)
- `page_number`: int — 1-indexed page number where PII was detected
- `paragraph_index`: int — 0-indexed paragraph number within the page
- `char_offset_start`: int — Start character offset within the paragraph
- `char_offset_end`: int — End character offset within the paragraph
- `placeholder`: str — Replacement placeholder (e.g., "[PARTY_A]", "[DATE]", "[AMOUNT]")
- `original_value`: str — Original PII value (stored in encrypted mapping only, not in audit trail)
- `confidence`: float — Detection confidence score (0.0 to 1.0, from Presidio)

**Validation Rules**:
- `entity_type` must be one of the 16 supported placeholder types
- `page_number` must be ≥ 1
- `char_offset_start` must be < `char_offset_end`
- `confidence` must be ≥ `config.threshold` (default 0.5)

**Relationships**:
- Belongs to one `Document` (via `document_hash`)
- Stored in one `EncryptedMapping` (grouped by document)

---

### 2. EncryptedMapping

A reversible mapping between PII placeholders and original values, encrypted with Fernet.

**Fields**:
- `document_hash`: str — SHA-256 hash of the source document (primary key)
- `encrypted_data`: bytes — Fernet-encrypted JSON containing all `PiiEntity` records for this document
- `encryption_key_salt`: bytes — Salt for key derivation (HKDF)
- `created_at`: datetime — Timestamp when mapping was created
- `expiry_at`: datetime — Timestamp when mapping expires (created_at + 30 days)
- `config_hash`: str — SHA-256 hash of PII config used to generate this mapping

**Validation Rules**:
- `document_hash` must be unique (one mapping per document)
- `encrypted_data` must be valid Fernet token (decryptable with derived key)
- `expiry_at` must be > `created_at`
- `config_hash` must match current config hash (for cache validation)

**Relationships**:
- Contains multiple `PiiEntity` records (encrypted)
- Referenced by one `PiiCache` row (SQLite)

**Storage**:
- Filesystem: `~/.openreview/pii_mappings/{document_hash}.enc`
- Format: JSON (list of PiiEntity dicts) → Fernet encrypt → binary file

---

### 3. PiiAuditTrail

A per-document summary log of PII stripping operations (not per-entity detail).

**Fields**:
- `document_hash`: str — SHA-256 hash of the source document
- `timestamp`: datetime — Timestamp of the PII stripping operation
- `entity_count`: int — Total number of PII entities detected
- `entity_type_distribution`: dict — Mapping of entity_type → count (e.g., {"PERSON": 5, "DATE": 3, "MONEY": 2})
- `processing_time_ms`: int — Time taken to process the document (milliseconds)
- `config_hash`: str — SHA-256 hash of PII config used
- `status`: str — "success" | "partial" | "failed"
- `failed_pages`: list[int] — List of page numbers that failed processing (empty if status="success")

**Validation Rules**:
- `entity_count` must equal sum of values in `entity_type_distribution`
- `processing_time_ms` must be ≥ 0
- `status` must be one of: "success", "partial", "failed"
- If `status` = "success", `failed_pages` must be empty
- If `status` = "partial", `failed_pages` must be non-empty

**Relationships**:
- Belongs to one `Document` (via `document_hash`)
- Multiple audit records can exist for the same document (one per processing run)

**Storage**:
- SQLite table: `pii_audit_trail`
- Columns: `document_hash`, `timestamp`, `entity_count`, `entity_type_distribution` (JSON), `processing_time_ms`, `config_hash`, `status`, `failed_pages` (JSON)

---

### 4. PiiCache

SQLite cache for config change detection and expiry management.

**Fields**:
- `document_hash`: str — SHA-256 hash of the source document (primary key)
- `config_hash`: str — SHA-256 hash of PII config used to generate cached result
- `review_result_path`: str — Filesystem path to the cached review result (PII-stripped)
- `mapping_path`: str — Filesystem path to the encrypted PII mapping file
- `created_at`: datetime — Timestamp when cache entry was created
- `expiry_at`: datetime — Timestamp when cache entry expires (created_at + 30 days)

**Validation Rules**:
- `document_hash` must be unique (one cache entry per document)
- `review_result_path` and `mapping_path` must point to existing files
- `expiry_at` must be > `created_at`

**Relationships**:
- References one `EncryptedMapping` (via `mapping_path`)
- Referenced by one `PiiAuditTrail` record (latest run)

**Storage**:
- SQLite table: `pii_cache`
- Columns: `document_hash`, `config_hash`, `review_result_path`, `mapping_path`, `created_at`, `expiry_at`

---

## State Transitions

### PII Stripping Lifecycle

```
[Document Input]
       │
       ▼
[Check PiiCache by document_hash]
       │
       ├── Cache hit + config_hash match → [Load Cached Result]
       │
       ├── Cache hit + config_hash mismatch → [Re-run PII Stripping]
       │
       └── Cache miss → [Run PII Stripping]
                              │
                              ▼
                     [Detect PII Entities]
                              │
                              ▼
                     [Create Encrypted Mapping]
                              │
                              ▼
                     [Create PiiAuditTrail Record]
                              │
                              ▼
                     [Update PiiCache]
                              │
                              ▼
                     [Return PII-Stripped Result]
```

### Error Recovery States

```
[PII Stripping In Progress]
       │
       ├── All pages succeed → [status="success", failed_pages=[]]
       │
       ├── Some pages fail → [status="partial", failed_pages=[...]]
       │                        │
       │                        ▼
       │               [Preserve partial results]
       │               [Raise PartialProcessingError]
       │
       └── All pages fail → [status="failed", failed_pages=[...]]
                               │
                               ▼
                      [No results preserved]
                      [Raise ProcessingError]
```

### GDPR Retention Lifecycle

```
[Encrypted Mapping Created]
       │
       ▼
[expiry_at = created_at + 30 days]
       │
       ├── User runs `openreview pii delete <document_hash>` → [Delete mapping + cache + audit]
       │
       ├── expiry_at < current_timestamp → [Background cleanup deletes entry]
       │
       └── User re-runs review before expiry → [Extend expiry_at by 30 days]
```

---

## Validation Corpus

### GroundTruthEntity

An annotated PII entity in the validation corpus (for accuracy testing).

**Fields**:
- `document_path`: str — Path to the test document
- `entity_type`: str — Expected PII type
- `page_number`: int — Page where PII appears
- `paragraph_index`: int — Paragraph where PII appears
- `char_offset_start`: int — Start offset
- `char_offset_end`: int — End offset
- `original_value`: str — Expected PII value

**Storage**:
- JSON file: `tests/fixtures/pii/ground_truth.json`
- Format: list of GroundTruthEntity dicts

**Usage**:
- Load corpus, run PII detection on each document
- Compare detected entities against ground truth
- Compute recall (detected / total ground truth) and precision (correct detections / total detections)

---

## Schema Migrations

### SQLite Tables

```sql
-- PII cache for config change detection and expiry
CREATE TABLE IF NOT EXISTS pii_cache (
    document_hash TEXT PRIMARY KEY,
    config_hash TEXT NOT NULL,
    review_result_path TEXT NOT NULL,
    mapping_path TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    expiry_at TIMESTAMP NOT NULL
);

-- PII audit trail (per-document summary)
CREATE TABLE IF NOT EXISTS pii_audit_trail (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_hash TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    entity_count INTEGER NOT NULL,
    entity_type_distribution TEXT NOT NULL,  -- JSON
    processing_time_ms INTEGER NOT NULL,
    config_hash TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('success', 'partial', 'failed')),
    failed_pages TEXT NOT NULL  -- JSON array
);

-- Index for fast lookup by document_hash
CREATE INDEX IF NOT EXISTS idx_audit_document_hash ON pii_audit_trail(document_hash);

-- Index for expiry cleanup
CREATE INDEX IF NOT EXISTS idx_cache_expiry ON pii_cache(expiry_at);
```

---

## Data Flow Summary

1. **Input**: User runs `openreview precheck contract.pdf`
2. **Hash**: Compute `document_hash = SHA-256(contract.pdf)`
3. **Cache Check**: Query `pii_cache` by `document_hash`
   - If cache hit + `config_hash` match → load cached result
   - If cache miss or `config_hash` mismatch → run PII stripping
4. **PII Stripping**:
   - Parse document page-by-page (streaming)
   - Detect PII entities via Presidio
   - Create `PiiEntity` records
   - Encrypt mapping via Fernet → write to filesystem
   - Create `PiiAuditTrail` record → insert into SQLite
   - Update `PiiCache` → insert/update in SQLite
5. **Output**: Return PII-stripped review result to user
6. **Retention**: Background cleanup deletes expired entries (optional)
