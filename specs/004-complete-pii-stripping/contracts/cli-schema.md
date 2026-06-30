# CLI Contract: Review Commands with PII Integration

**Date**: 2026-06-30 | **Feature**: [spec.md](../spec.md) | **Data Model**: [data-model.md](../data-model.md)

## Overview

This contract defines the CLI interface for review commands with PII stripping integration. The first review subcommand is `precheck` (NDA review). Future review modes (DealCheck, HireCheck, etc.) will follow the same pattern.

## Command: `openreview precheck`

### Synopsis

```bash
openreview precheck [OPTIONS] DOCUMENT_PATH
```

### Description

Runs the PreCheck review mode (NDA review) on the specified document. Automatically strips PII before processing unless `--no-pii` is specified. Creates an encrypted PII mapping and audit trail for privacy-compliant review.

### Arguments

- `DOCUMENT_PATH` (required, positional)
  - Type: Path to PDF or DOCX file
  - Validation: File must exist, must be readable, must be a valid PDF or DOCX
  - Example: `contract.pdf`, `/path/to/document.docx`

### Options

#### PII Control

- `--no-pii` (flag, default: false)
  - Disables PII stripping. Processes document with raw PII intact.
  - Logs warning: "PII stripping disabled. Raw text processed."
  - Use case: Fully local setup (no cloud API calls), accuracy benchmarking, debugging
  - Mutually exclusive with: `--pii-threshold`

- `--pii-threshold FLOAT` (default: from config.yml, typically 0.5)
  - Overrides PII detection confidence threshold for this run only.
  - Range: 0.0 to 1.0
  - Example: `--pii-threshold 0.7` (more conservative, fewer false positives)
  - Mutually exclusive with: `--no-pii`

#### Output Control

- `--output PATH` (default: `./review_results/{document_hash}/`)
  - Directory where review results are stored.
  - Creates directory if it doesn't exist.
  - Contains: PII-stripped review memo, encrypted PII mapping, audit trail

- `--format TEXT` (choices: `text`, `json`, default: `text`)
  - Output format for review memo.
  - `text`: Human-readable plain text
  - `json`: Machine-readable JSON (for programmatic consumption)

#### Advanced

- `--force-reprocess` (flag, default: false)
  - Forces re-processing even if cached result exists.
  - Use case: Config changed but cache not invalidated, or user wants fresh results.

- `--pages TEXT` (optional, future enhancement)
  - Comma-separated list of page numbers to process (e.g., `1,5,10-20`).
  - Use case: Retry failed pages after partial processing error.
  - **Status**: Out of scope for this feature, reserved for future use.

### Exit Codes

- `0` — Success (PII stripped, review completed)
- `1` — General error (file not found, invalid format, etc.)
- `2` — PII processing error (partial or complete failure)
  - Partial failure: some pages processed, others failed
  - Complete failure: no pages processed
- `3` — Configuration error (invalid config.yml, missing dependencies, etc.)

### Standard Output

#### Success (exit code 0)

```
✓ PII stripping complete: 18 entities detected (5 party names, 8 dates, 3 amounts, 2 addresses)
✓ Review memo generated: ./review_results/abc123/memo.txt
✓ Encrypted PII mapping: ./review_results/abc123/pii_mapping.enc
✓ Audit trail logged

Review Summary:
- Document: contract.pdf (50 pages)
- Processing time: 2.3 seconds
- PII entities: 18 (all replaced with placeholders)
- Review mode: PreCheck (NDA)
- Status: Complete
```

#### Partial Failure (exit code 2)

```
⚠ PII stripping partial: 15 entities detected, 3 pages failed
✓ Review memo generated: ./review_results/abc123/memo.txt (pages 1-42, 44-50)
⚠ Failed pages: 43 (OCR error: low confidence)
✓ Encrypted PII mapping: ./review_results/abc123/pii_mapping.enc (partial)
✓ Audit trail logged

Review Summary:
- Document: contract.pdf (50 pages)
- Processing time: 2.8 seconds
- PII entities: 15 (replaced with placeholders)
- Failed pages: 1 (page 43)
- Review mode: PreCheck (NDA)
- Status: Partial (retry failed pages with --pages 43)
```

#### --no-pii Mode (exit code 0)

```
⚠ PII stripping disabled. Raw text processed.
✓ Review memo generated: ./review_results/abc123/memo.txt
✓ Audit trail logged

Review Summary:
- Document: contract.pdf (50 pages)
- Processing time: 1.9 seconds
- PII entities: N/A (stripping disabled)
- Review mode: PreCheck (NDA)
- Status: Complete (raw PII in output)
```

### Standard Error

#### File Not Found (exit code 1)

```
Error: Document not found: contract.pdf
```

#### Invalid Format (exit code 1)

```
Error: Unsupported file format: .txt (supported: .pdf, .docx)
```

#### Config Error (exit code 3)

```
Error: Invalid PII threshold in config.yml: 1.5 (must be 0.0-1.0)
```

---

## Command: `openreview pii`

### Synopsis

```bash
openreview pii SUBCOMMAND
```

### Description

Manages PII data (encrypted mappings, audit trails, cache entries). Supports GDPR-compliant deletion and listing.

### Subcommands

#### `openreview pii list`

Lists all documents with PII data (encrypted mappings, audit trails).

**Options**:
- `--format TEXT` (choices: `text`, `json`, default: `text`)
  - Output format

**Output** (text format):

```
Documents with PII data:

1. contract.pdf
   - Document hash: abc123def456...
   - PII entities: 18
   - Created: 2026-06-30 14:23:15
   - Expires: 2026-07-30 14:23:15
   - Mapping: ~/.openreview/pii_mappings/abc123def456.enc

2. nda-agreement.pdf
   - Document hash: xyz789abc012...
   - PII entities: 7
   - Created: 2026-06-29 09:15:42
   - Expires: 2026-07-29 09:15:42
   - Mapping: ~/.openreview/pii_mappings/xyz789abc012.enc

Total: 2 documents
```

#### `openreview pii delete DOCUMENT_HASH`

Deletes all PII data for a specific document (encrypted mapping, audit trail, cache entry).

**Arguments**:
- `DOCUMENT_HASH` (required, positional)
  - Type: SHA-256 hash (or prefix, minimum 8 characters)
  - Example: `abc123def456`, `abc123`

**Output**:

```
✓ Deleted PII data for document hash: abc123def456
  - Encrypted mapping: removed
  - Audit trail: removed (3 records)
  - Cache entry: removed
```

#### `openreview pii cleanup`

Deletes all expired PII data (entries past their 30-day expiry).

**Options**:
- `--dry-run` (flag, default: false)
  - Shows what would be deleted without actually deleting

**Output**:

```
✓ Cleanup complete: 5 expired entries deleted
  - Expired before: 2026-06-30 15:00:00
  - Documents affected: 5
  - Storage freed: 2.3 MB
```

---

## Error Handling

### PartialProcessingError

Raised when PII stripping fails on some pages but succeeds on others.

**Attributes**:
- `failed_pages`: list[int] — List of page numbers that failed
- `successful_pages`: list[int] — List of page numbers that succeeded
- `error_messages`: dict[int, str] — Mapping of page number → error message

**User Action**: Retry failed pages with `--pages` option (future enhancement) or accept partial results.

### ProcessingError

Raised when PII stripping fails on all pages.

**Attributes**:
- `error_message`: str — Error message from the first failed page

**User Action**: Check document format, OCR quality, or Presidio configuration.

### ConfigChangedError

Raised when config hash mismatch is detected but `--force-reprocess` is not specified.

**Attributes**:
- `old_config_hash`: str — Hash of config used for cached result
- `new_config_hash`: str — Hash of current config

**User Action**: Re-run with `--force-reprocess` to use new config.

---

## Integration with Existing Commands

### `openreview parse`

Existing command (Phase 2) parses documents into clause streams. No changes required. PII stripping is orthogonal to parsing.

### `openreview config`

Existing command manages configuration. PII section added to `config.yml` (see [config-schema.md](config-schema.md)).

### `openreview --version`

No changes required.

---

## Future Enhancements (Out of Scope)

- `--pages` option for retrying failed pages
- `openreview pii export` for exporting PII mapping (for manual review)
- `openreview pii import` for importing PII mapping (for restoring deleted data)
- Per-recognizer configuration (enable/disable specific PII types)
- Custom placeholder types (user-defined)
