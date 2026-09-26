# Contract: strip_pii()

**Date**: 2026-06-25
**Feature**: 003-pii-stripping
**Module**: `src/openreview_cli/pii/`

## Overview

The `strip_pii()` function is the public interface for PII stripping. It accepts parsed document text (from Phase 2's `stream_clauses()` or `parse_document()`), detects PII entities, replaces them with deterministic placeholders, and returns a `PiiResult` containing the stripped text, the placeholder-to-original mapping, and detection metadata.

## Function Signature

```python
def strip_pii(
    clauses: list[Clause],
    document: Document,
    *,
    threshold: float = 0.7,
    strip_metadata: bool = True,
) -> PiiResult:
    """Strip PII from parsed document clauses.

    Args:
        clauses: List of parsed clauses from Phase 2.
        document: Document metadata from Phase 2.
        threshold: Confidence score threshold for NLP-based detections.
            Regex recognizers always run at full confidence (1.0) and are
            not affected by this threshold. Default: 0.7.
        strip_metadata: Whether to redact document metadata (filename,
            author, title, company). Default: True.

    Returns:
        PiiResult containing stripped text, mapping, entities, and audit data.

    Raises:
        PiiError: If PII detection fails unexpectedly. The error message
            includes the clause heading and processing phase but never
            includes character offsets or text snippets.
    """
```

## Input Contract

### `clauses: list[Clause]`
- Non-empty list of `Clause` objects from Phase 2
- Each clause has: `id`, `title` (optional), `text`, `level`, `parent_id`, `source_page` / `source_paragraph`
- The `title` field is used in error messages (safe metadata — not PII)
- The `text` field is the raw content to be stripped
- The `source_page` field is used for page-sequential processing order

### `document: Document`
- `Document` object from Phase 2
- `source_path` is used for filename metadata redaction
- `page_count` is used for progress display
- `format` is either `"pdf"` or `"docx"`

### `threshold: float`
- Must be between 0.0 and 1.0 (inclusive)
- Default: 0.7 (from `config.yml` `privacy.pii_threshold`)
- Controls NLP-based detection filtering only
- Regex recognizers always return score 1.0

### `strip_metadata: bool`
- Default: True
- When True, document metadata (filename, author, title, company) is redacted
- Metadata entities are added to the mapping alongside body text entities

## Output Contract

### `PiiResult`

```python
@dataclass(slots=True)
class PiiResult:
    stripped_text: str          # Full document text with placeholders
    mapping: dict[str, str]    # {placeholder_key: original_value}
    entities: list[PiiEntity]  # All detected entities with metadata
    page_count: int            # Pages processed
    duration_seconds: float    # Processing time (warm)
    warnings: list[str]        # Non-fatal warnings
```

**Invariants**:
1. Every placeholder token in `stripped_text` has a corresponding key in `mapping`
2. Every key in `mapping` corresponds to at least one placeholder in `stripped_text`
3. `mapping` keys do NOT include brackets — e.g., key is `"PARTY_A"`, not `"[PARTY_A]"`
4. Placeholder tokens in `stripped_text` ARE bracketed — e.g., `"[PARTY_A]"`
5. Repeated occurrences of the same entity value map to the same placeholder
6. Placeholders are deterministic: alphabetical sort of unique values within each type, then sequential numbering

### Empty Document (No PII)

When a document contains no PII:
- `stripped_text` is the original text unchanged
- `mapping` is `{}`
- `entities` is `[]`
- `warnings` is `[]`

## Error Contract

### `PiiError`

Raised when PII stripping fails. The review MUST NOT proceed with unstripped text.

```python
@dataclass
class PiiError(Exception):
    exit_code: int        # Always 9
    category: str         # "engine_crash" | "model_not_found" | "invalid_key"
    clause_heading: str | None  # Clause being processed (safe metadata)
    phase: str | None     # "regex phase" | "NER phase" | "anonymizer phase"
    message: str          # Human-readable, no PII content
    action: str           # User action to take
```

**Message format** (FR-010):
```
PII detection failed while processing clause '{clause_heading}' ({phase}). Run with --no-pii to skip stripping. Report this bug.
```

**Forbidden in error messages**:
- Character offsets
- Text snippets
- Original PII values
- Stack traces (logged at DEBUG level only, with text redacted)

## Behavioral Contract

### Processing Order
1. Metadata redaction (if `strip_metadata=True`)
2. Sort clauses by `source_page` (PDF) or `source_paragraph` (DOCX)
3. Page-sequential PII detection with 50-character overlap buffer
4. Placeholder assignment (global, deterministic)
5. Text replacement (longest-first)
6. Audit generation

### Non-English Text
- Detected via Phase 2 parser's language detection flags
- Only regex recognizers run (emails, phone numbers, amounts, tax IDs)
- NLP NER is skipped for non-English sections
- Warning added to `PiiResult.warnings`:
  `"Non-English text detected — structured PII stripped, but named entities in non-English sections may remain."`

### Re-Stripping
- Always processes original text from scratch
- Overwrites existing `pii_map.json` and `pii_audit.json`
- Returns a signal that downstream cache should be invalidated

### Thread Safety
- `strip_pii()` is NOT thread-safe (Presidio's AnalyzerEngine is not thread-safe)
- Must be called from the main thread
- This is acceptable because PII stripping is synchronous and precedes any async operations

## File I/O Contract

### `write_pii_mapping()`

```python
def write_pii_mapping(
    mapping: dict[str, str],
    review_dir: Path,
    encryption_key: str,
) -> Path:
    """Write encrypted PII mapping to disk.

    Args:
        mapping: Placeholder → original value dict.
        review_dir: Path to the review directory.
        encryption_key: AES key (16, 24, or 32 chars).

    Returns:
        Path to the written pii_map.json file.

    Side effects:
        - Creates review_dir if it doesn't exist
        - Writes pii_map.json with chmod 600
        - Overwrites existing file (no append mode)
    """
```

**File format** (`pii_map.json`):
```json
{
  "version": 1,
  "encrypted": true,
  "entries": {
    "PARTY_A": "<AES-CBC encrypted ciphertext, base64>",
    "AMOUNT_1": "<AES-CBC encrypted ciphertext, base64>"
  }
}
```

### `read_pii_mapping()`

```python
def read_pii_mapping(
    review_dir: Path,
    encryption_key: str,
) -> dict[str, str]:
    """Read and decrypt PII mapping from disk.

    Returns:
        Decrypted placeholder → original value dict.

    Raises:
        FileNotFoundError: If pii_map.json doesn't exist.
        PiiError: If decryption fails (wrong key).
    """
```

### `write_pii_audit()`

```python
def write_pii_audit(
    audit: PiiAudit,
    review_dir: Path,
) -> Path:
    """Write PII audit file to disk.

    The audit file contains ZERO actual PII values — only counts,
    confidence ranges, and processing metadata.

    Returns:
        Path to the written pii_audit.json file.
    """
```

## CLI Integration Contract

### `--no-pii` Flag

Added to review commands (not `parse`):
```
openreview review contract.pdf --no-pii
```

When `--no-pii` is set OR `privacy.strip_pii: false` in config:
1. Display warning: `"⚠️ PII stripping disabled. Contract text may be sent to providers as-is."`
2. Skip `strip_pii()` entirely
3. Pass original text to downstream phases
4. No `pii_map.json` or `pii_audit.json` written

### Progress Display

During stripping, display per-page progress:
```
Stripping PII... page 12/50 ━━━━━━━━━━━━━━━━━━━━━━━━ 24%
```

## Performance Contract

| Metric | Target | Measurement |
|--------|--------|-------------|
| Processing time (50-page, warm) | <3 seconds | `time.perf_counter()` |
| Processing overhead (memory) | <100 MB | `tracemalloc` (excluding NLP model baseline) |
| NLP model cold-start | Documented (not a target) | `time.perf_counter()` |
| Recall (50 seeded docs) | ≥90% | Test suite |
| Precision (50 seeded docs) | ≥95% | Test suite |
| False replacement rate | <5% | Test suite |
