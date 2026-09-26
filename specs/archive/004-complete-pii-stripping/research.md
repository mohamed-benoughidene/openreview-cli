# Research: Complete PII Stripping Integration

**Date**: 2026-06-30 | **Feature**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

## Research Tasks

### R-1: Fernet Encryption Best Practices

**Decision**: Use Fernet symmetric encryption from the `cryptography` library for PII mapping files.

**Rationale**:
- Fernet provides authenticated encryption (AES-128-CBC with HMAC-SHA256), ensuring both confidentiality and integrity
- Tamper-evident: any modification to the encrypted data is detected during decryption
- Simple API: `Fernet.encrypt(data)` and `Fernet.decrypt(token)` with no configuration required
- Python ecosystem standard for symmetric encryption, already a transitive dependency of many projects
- No need to manage IVs, padding, or authentication tags manually (unlike raw AES-GCM)

**Alternatives Considered**:
- **AES-256-GCM (raw)**: More complex, requires manual IV management, padding, and authentication tag handling. No additional security benefit over Fernet for this use case.
- **OS-level encryption (filesystem)**: No application-level control, no tamper detection, requires user to configure filesystem encryption. Not portable across platforms.
- **No encryption (plaintext)**: Violates privacy-first principle. PII mapping must be encrypted to prevent accidental exposure.

**Implementation Notes**:
- Generate encryption key from document hash using HKDF (HMAC-based Key Derivation Function)
- Store key derivation salt alongside encrypted file
- Use `cryptography.fernet.Fernet` class
- Handle `InvalidToken` exception for corrupted/tampered files

---

### R-2: Presidio Integration Patterns

**Decision**: Use existing `PiiEngine` class from Phase 3 (already built and tested at unit level). Integrate with review commands via a `strip_pii(document_path)` wrapper function.

**Rationale**:
- Phase 3 already built `PiiEngine.detect_all_pages()` with Presidio analyzer and anonymizer
- 16 placeholder types already defined (party names, dates, amounts, addresses, etc.)
- Unit tests already exist for entity detection and replacement
- Integration is straightforward: call `detect_all_pages()`, collect results, create encrypted mapping

**Alternatives Considered**:
- **Custom PII detection (regex-only)**: Lower accuracy, no NER (Named Entity Recognition). Presidio already validated.
- **spaCy NER directly**: Requires custom training data for legal entities. Presidio provides out-of-the-box legal entity recognition.

**Implementation Notes**:
- `strip_pii(document_path)` returns `(stripped_text, pii_entities, audit_record)`
- `pii_entities` is a list of `PiiEntity` dataclasses (type, location, placeholder, original_value)
- `audit_record` contains entity count, type distribution, processing time, config hash
- Pass `config.threshold` to `PiiEngine` for sensitivity tuning

---

### R-3: Config Hash Comparison Strategies

**Decision**: Compute SHA-256 hash of PII config section (threshold, enabled recognizers, placeholder types) and store in SQLite alongside cached review result. On re-run, compare stored hash with current config hash. If mismatch, re-run PII stripping.

**Rationale**:
- Simple, deterministic, no false positives/negatives
- SHA-256 is fast (<1ms for small config)
- SQLite storage allows efficient lookup by document hash
- Captures all config changes (threshold, recognizers, placeholder types) in one hash

**Alternatives Considered**:
- **Per-field comparison (threshold, recognizers, etc.)**: More complex, requires schema versioning, harder to maintain.
- **Timestamp-based (config modified time)**: Unreliable (file mtime can change without content change, clock skew).
- **No config change detection**: User gets stale results after changing config. Unacceptable for threshold tuning.

**Implementation Notes**:
- Serialize config to canonical JSON (sorted keys, no whitespace) before hashing
- Store `(document_hash, config_hash, review_result_path)` in SQLite `pii_cache` table
- On re-run: query `pii_cache` by `document_hash`, compare `config_hash`
- If match: load cached result. If mismatch or missing: re-run PII stripping, update cache

---

### R-4: tracemalloc Memory Profiling

**Decision**: Use Python's built-in `tracemalloc` module to measure peak memory during PII stripping. Exclude NLP model memory (constitutionally exempt).

**Rationale**:
- `tracemalloc` is stdlib, no external dependencies
- Provides accurate peak memory measurement via `tracemalloc.get_traced_memory()`
- Can filter by module to exclude NLP model allocations
- Already used in Phase 3 memory tests

**Alternatives Considered**:
- **psutil (RSS)**: Includes NLP model memory, less accurate for isolating PII processing overhead.
- **memory_profiler (line-by-line)**: Slow, not suitable for integration tests.
- **No memory validation**: Cannot confirm <100MB budget. Unacceptable for constitution compliance.

**Implementation Notes**:
- Start `tracemalloc` before PII stripping, stop after
- Call `tracemalloc.get_traced_memory()` to get `(current, peak)`
- Assert `peak < 100 * 1024 * 1024` (100 MB in bytes)
- Generate 500-page synthetic document with 2000 PII entities for validation
- Run in CI via `pytest -m memory`

---

### R-5: GDPR Data Retention Patterns

**Decision**: Implement 30-day expiry for encrypted PII mappings by default. Provide CLI command `openreview pii delete <document_hash>` for on-demand deletion. Store expiry timestamp in SQLite `pii_cache` table.

**Rationale**:
- GDPR Article 5(1)(e): "kept in a form which permits identification of data subjects for no longer than is necessary"
- 30 days balances utility (user can re-run review) with data minimization
- On-demand deletion satisfies "right to erasure" (Article 17)
- SQLite storage allows efficient expiry queries

**Alternatives Considered**:
- **No expiry (retain indefinitely)**: Violates GDPR data minimization principle.
- **Shorter expiry (7 days)**: Too aggressive, user may need to re-run review within 30 days.
- **Longer expiry (90 days)**: Unnecessary data retention, increases privacy risk.

**Implementation Notes**:
- Add `expiry_timestamp` column to `pii_cache` table
- Background cleanup: run `DELETE FROM pii_cache WHERE expiry_timestamp < CURRENT_TIMESTAMP` on CLI startup (optional, low priority)
- `openreview pii delete <document_hash>`: delete all PII data for a document (mapping, audit trail, cache entry)
- `openreview pii list`: list all documents with PII data (for user awareness)

---

### R-6: Error Recovery Strategy

**Decision**: Fail-fast with partial result preservation. If PII stripping fails mid-document, preserve successfully processed pages in encrypted mapping, report failed pages, allow manual retry.

**Rationale**:
- Balances data recovery (user can retry failed pages) with simplicity (no automatic retry logic)
- Presidio errors are rare (mostly OCR quality issues), so automatic retry adds complexity without benefit
- Partial results allow user to continue working on successfully processed pages
- Failed pages are reported with error message (e.g., "Page 42: OCR failed, low confidence")

**Alternatives Considered**:
- **Fail-fast, discard all progress**: User loses all work, must re-process entire document. Unacceptable for large documents.
- **Automatic retry (exponential backoff)**: Adds complexity, may compound errors (e.g., OCR failure won't succeed on retry).
- **Silent failure (skip failed pages)**: User unaware of missing PII data. Privacy risk.

**Implementation Notes**:
- Process pages sequentially, catch exceptions per page
- On exception: log error, add page to `failed_pages` list, continue to next page
- After processing: if `failed_pages` not empty, raise `PartialProcessingError` with list of failed pages
- Encrypted mapping contains only successfully processed pages
- User can retry failed pages via `openreview precheck --pages 42,43 contract.pdf` (future enhancement, out of scope for this feature)

---

## Research Summary

All NEEDS CLARIFICATION items resolved:
- Encryption: Fernet (authenticated, tamper-evident)
- Presidio: Use existing `PiiEngine` from Phase 3
- Config hash: SHA-256 of canonical JSON, stored in SQLite
- Memory profiling: `tracemalloc` (stdlib, accurate, filterable)
- GDPR retention: 30-day expiry, on-demand deletion
- Error recovery: Fail-fast, preserve partial results, report failed pages

No unresolved dependencies or integrations. Ready for Phase 1 design.
