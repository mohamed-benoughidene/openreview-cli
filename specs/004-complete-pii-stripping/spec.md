# Feature Specification: Complete PII Stripping Integration

**Feature Branch**: `feat/complete-pii-stripping`

**Created**: 2026-06-30

**Status**: Draft

**Input**: User description: "Complete PII stripping integration"

## Clarifications

### Session 2026-06-30

- Q: What encryption algorithm should the system use for the encrypted PII mapping file? → A: Fernet symmetric encryption (cryptography library, authenticated, tamper-evident)
- Q: What level of detail should the PII audit trail capture? → A: Per-document summary (entity count, type distribution, processing time, config hash)
- Q: Are there specific regulatory compliance requirements the PII stripping system must satisfy? → A: GDPR-aligned data protection (purpose limitation, data minimization, retention limits)
- Q: What is the maximum document size (in pages) the PII stripping system must support? → A: 500 pages (covers large M&A documents, due diligence packages)
- Q: What should happen when PII stripping fails partway through processing a document? → A: Fail-fast, preserve partial results, report failed pages for manual retry

## User Scenarios & Testing *(mandatory)*

### User Story 1 - First Review Command with Automatic PII Stripping (Priority: P1)

A solo lawyer runs the first review subcommand (e.g., `openreview precheck`) on a contract containing sensitive information (party names, dates, monetary amounts). The system automatically detects and replaces all PII with placeholders (e.g., `[PARTY_A]`, `[DATE]`, `[AMOUNT]`) before any processing occurs. The lawyer receives a review memo with PII placeholders intact, and the original PII values are stored in an encrypted, reversible mapping for later reference.

**Why this priority**: This is the core privacy guarantee. Without PII stripping wired to a review command, the product cannot ship any review functionality. This unblocks all downstream review modes and validates the privacy-first architecture end-to-end.

**Independent Test**: Can be fully tested by running `openreview precheck` on a test contract with known PII entities and verifying: (1) all PII is replaced with placeholders in the output, (2) the encrypted mapping is created, (3) the audit trail logs the stripping operation. Delivers immediate value: a working, privacy-compliant review command.

**Acceptance Scenarios**:

1. **Given** a 50-page PDF contract containing 10 party names, 5 dates, and 3 monetary amounts, **When** the user runs `openreview precheck contract.pdf`, **Then** the system detects and replaces all 18 PII entities with appropriate placeholders, creates an encrypted mapping file, and produces a review memo with placeholders intact.
2. **Given** a contract with no PII (clean text), **When** the user runs `openreview precheck clean-contract.pdf`, **Then** the system processes the document normally with zero PII detections and no placeholder substitutions.
3. **Given** a contract with PII in headers, footers, and tables, **When** the user runs `openreview precheck complex-contract.pdf`, **Then** the system detects PII across all document regions (not just body text) and replaces them consistently.

---

### User Story 2 - Opt-Out of PII Stripping with --no-pii Flag (Priority: P2)

A lawyer working with a fully local model setup (no cloud API calls) wants to skip PII stripping to preserve maximum accuracy for a sensitive legal analysis. They run `openreview precheck --no-pii contract.pdf`. The system processes the document with raw PII intact, skips the stripping step, and produces a review memo with original entity values. The system logs a warning that PII stripping was disabled.

**Why this priority**: This supports the "maximum privacy tier" (all-local, no network calls) where PII stripping is optional. It also enables accuracy benchmarking (stripped vs. raw) and debugging. Lower priority than P1 because the default path (with stripping) is the privacy-safe default.

**Independent Test**: Can be fully tested by running `openreview precheck --no-pii contract.pdf` and verifying: (1) no PII detection occurs, (2) no encrypted mapping is created, (3) the output contains original PII values, (4) a warning is logged. Delivers value: user control over privacy/accuracy tradeoff.

**Acceptance Scenarios**:

1. **Given** a contract containing PII, **When** the user runs `openreview precheck --no-pii contract.pdf`, **Then** the system processes the document without PII detection, produces a review memo with original entity values, and logs a warning: "PII stripping disabled. Raw text processed."
2. **Given** a contract containing PII, **When** the user runs `openreview precheck contract.pdf` (without --no-pii), **Then** the system performs PII stripping as in User Story 1 (default behavior unchanged).

---

### User Story 3 - Config Change Detection and Re-Stripping (Priority: P3)

A lawyer changes the PII detection threshold in `config.yml` from the default (0.5) to a more conservative value (0.7) to reduce false positives. They re-run `openreview precheck contract.pdf` on a previously processed document. The system detects the config change (via threshold hash comparison), re-runs PII stripping with the new threshold, and updates the encrypted mapping and audit trail.

**Why this priority**: This ensures consistency when users tune PII detection sensitivity. Without config change detection, users might get stale results after changing thresholds. Lower priority because config changes are infrequent and the system can document this as a known limitation initially.

**Independent Test**: Can be fully tested by: (1) running `openreview precheck contract.pdf` with default threshold, (2) changing threshold in `config.yml`, (3) re-running the command on the same document, (4) verifying the system detects the config change and re-processes with the new threshold. Delivers value: config changes take effect without manual cache clearing.

**Acceptance Scenarios**:

1. **Given** a document previously processed with threshold 0.5, **When** the user changes threshold to 0.7 in `config.yml` and re-runs `openreview precheck contract.pdf`, **Then** the system detects the config change (threshold hash mismatch), re-runs PII stripping with threshold 0.7, and updates the encrypted mapping.
2. **Given** a document previously processed with threshold 0.5, **When** the user re-runs `openreview precheck contract.pdf` without changing config, **Then** the system uses the cached PII-stripped result (no re-processing).

---

### User Story 4 - PII Accuracy Validation (Priority: P4)

The development team runs the PII accuracy validation suite on a seeded corpus of 50 contracts with known PII entities (ground truth). The system computes recall (percentage of true PII detected) and precision (percentage of detections that are true PII). The validation report shows recall ≥90% and precision ≥95%, confirming the PII engine meets the product's accuracy targets.

**Why this priority**: This validates the PII engine's accuracy before shipping review commands. Without accuracy validation, the team cannot confirm the engine is production-ready. Lower priority than P1-P3 because validation is a one-time gate, not a user-facing feature.

**Independent Test**: Can be fully tested by running `pytest tests/integration/test_pii_accuracy.py` and verifying: (1) the test loads the seeded corpus with ground truth, (2) computes recall and precision, (3) asserts recall ≥90% and precision ≥95%. Delivers value: confidence that PII engine meets accuracy targets.

**Acceptance Scenarios**:

1. **Given** a seeded corpus of 50 contracts with ground truth PII annotations (party names, dates, amounts, addresses), **When** the accuracy validation suite runs, **Then** the system computes recall ≥90% (at least 90% of true PII detected) and precision ≥95% (at most 5% false positives).
2. **Given** a clean-text document (no PII), **When** the accuracy validation suite runs, **Then** the system reports zero false positives (precision = 100% on clean text).

---

### User Story 5 - PII Memory Budget Validation (Priority: P5)

The development team runs the PII memory validation suite on a 500-page synthetic document. The system measures peak memory usage during PII stripping using `tracemalloc`. The validation report shows peak memory <100 MB (excluding the NLP model, which is constitutionally exempt), confirming the PII engine meets the hardware budget.

**Why this priority**: This validates the PII engine's memory footprint before shipping. Without memory validation, the team cannot confirm the engine runs on the reference 8GB machine. Lowest priority because memory validation is a one-time gate, not a user-facing feature.

**Independent Test**: Can be fully tested by running `pytest tests/integration/test_pii_memory.py` and verifying: (1) the test generates a 500-page synthetic document, (2) runs PII stripping with `tracemalloc` enabled, (3) asserts peak memory <100 MB (excluding NLP model). Delivers value: confidence that PII engine meets hardware budget.

**Acceptance Scenarios**:

1. **Given** a 500-page synthetic document with 2000 PII entities, **When** the memory validation suite runs, **Then** the system measures peak memory <100 MB (excluding NLP model ~500MB) during PII stripping.
2. **Given** a 500-page synthetic document, **When** the memory validation suite runs, **Then** the system completes processing in <30 seconds.

---

### Edge Cases

- What happens when a document contains PII in non-Latin scripts (e.g., Cyrillic, Greek)? The system detects PII based on entity type patterns (dates, amounts) and Presidio's multilingual recognizers, but accuracy may be lower. The system logs a warning if non-English text is detected.
- How does the system handle a document with mixed PII and non-PII content in the same paragraph? The system replaces only the PII entities with placeholders, preserving the surrounding text. The encrypted mapping stores the original values for reversibility.
- What happens when the encrypted mapping file is corrupted or missing? The system cannot reverse the PII placeholders. The review memo still contains placeholders, but the original PII values are lost. The system logs an error and suggests re-processing the document.
- How does the system handle a document with PII in images or scanned text? The system uses OCR (via Docling) to extract text from images, then runs PII detection on the extracted text. Accuracy depends on OCR quality.
- What happens when the user runs a review command on a directory of documents? The system processes each document independently, creating a separate encrypted mapping and audit trail for each. The system shows progress (e.g., "Processing 1/10, 2/10, ...").
- What happens when PII stripping fails partway through processing a document? The system fails fast, preserves any successfully processed pages in the encrypted mapping, and reports which pages failed. The user can retry failed pages manually without re-processing the entire document.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST wire PII stripping to the first review subcommand (e.g., `precheck`) so that all documents are PII-stripped before processing.
- **FR-002**: System MUST add a `--no-pii` CLI flag to review commands that disables PII stripping and processes documents with raw text.
- **FR-003**: System MUST create integration tests for the `--no-pii` flag that verify: (1) no PII detection occurs, (2) no encrypted mapping is created, (3) output contains original PII values.
- **FR-004**: System MUST implement config change detection by comparing the PII threshold hash in `config.yml` against the hash stored in the cached result. If the hash differs, the system re-runs PII stripping with the new threshold.
- **FR-005**: System MUST populate the PII accuracy validation corpus (`tests/fixtures/pii/seeded_contracts/ground_truth.json`) with at least 50 contracts containing annotated PII entities (party names, dates, amounts, addresses).
- **FR-006**: System MUST implement PII accuracy validation that computes recall (percentage of true PII detected) and precision (percentage of detections that are true PII) against the ground truth corpus.
- **FR-007**: System MUST implement PII memory validation that measures peak memory usage during PII stripping on a 500-page synthetic document using `tracemalloc`.
- **FR-008**: System MUST ensure PII recall ≥90% on the validation corpus.
- **FR-009**: System MUST ensure PII precision ≥95% on the validation corpus (at most 5% false positives).
- **FR-010**: System MUST ensure peak memory <100 MB (excluding NLP model) during PII stripping of a 500-page document.
- **FR-011**: System MUST ensure PII processing time <30 seconds for a 500-page document (linear scaling from 50-page baseline).
- **FR-012**: System MUST run the full test suite (`pytest`) and pre-commit hooks (`ruff`, `mypy`, `pytest-fast`) and ensure all pass before declaring Phase 3 complete.
- **FR-013**: System MUST implement GDPR-aligned data retention: encrypted PII mappings expire after 30 days by default, and users can delete all PII data for a document on demand.
- **FR-014**: System MUST implement fail-fast error recovery: when PII stripping fails partway through a document, the system preserves successfully processed pages in the encrypted mapping and reports which pages failed, allowing manual retry without full re-processing.
- **FR-015**: System MUST support a `--pii-threshold FLOAT` CLI flag on review commands that overrides the PII detection confidence threshold from `config.yml` for a single run.
- **FR-016**: System MUST support a `--force-reprocess` CLI flag on review commands that bypasses the config hash cache and forces re-processing.

### Key Entities

- **PII Entity**: A detected instance of personally identifiable information in a document. Key attributes: entity type (party name, date, amount, address, etc.), location (page number, paragraph index, character offset), placeholder value (e.g., `[PARTY_A]`), original value (stored in encrypted mapping).
- **Encrypted Mapping**: A reversible mapping between PII placeholders and original values. Stored as an encrypted file alongside the review result using Fernet symmetric encryption (authenticated, tamper-evident). Key attributes: document hash, placeholder-to-value mapping, encryption key (derived from document hash), creation timestamp.
- **PII Audit Trail**: A log of all PII stripping operations at the per-document summary level (not per-entity detail, to avoid exposing PII patterns in logs). Key attributes: document hash, timestamp, entity count, entity type distribution (e.g., "5 party names, 3 dates, 2 amounts"), processing time, config hash (threshold version).
- **Config Hash**: A hash of the PII detection configuration (threshold, enabled recognizers, etc.) stored with the cached result. Used to detect config changes and trigger re-processing.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can run the first review command (`openreview precheck`) on a contract and receive a PII-stripped review memo within 30 seconds for a 500-page document.
- **SC-002**: PII recall ≥90% on the validation corpus (at least 90% of true PII entities are detected and replaced).
- **SC-003**: PII precision ≥95% on the validation corpus (at most 5% of detected entities are false positives).
- **SC-004**: Peak memory <100 MB (excluding NLP model) during PII stripping of a 500-page document.
- **SC-005**: PII processing time <60 seconds for a 500-page document on CPU-only hardware (reference machine: 8 GB RAM, 2-core CPU, no GPU). GPU-accelerated machines will achieve faster processing, typically under 30 seconds.
- **SC-006**: 100% of integration tests pass (including `--no-pii` flag tests, config change detection tests, accuracy validation, memory validation).
- **SC-007**: Pre-commit hooks (ruff, mypy, pytest-fast) pass with zero errors.
- **SC-008**: Users can opt out of PII stripping with `--no-pii` flag and receive a review memo with raw PII values intact.

## Assumptions

- The PII detection engine (Presidio with 16 placeholder types) is already built and tested at the unit level (Phase 3 deliverables S-19 to S-26).
- The first review subcommand (`precheck`) is the pilot mode for PII stripping integration. Other review modes will follow the same pattern.
- The NLP model (spaCy `en_core_web_lg`, ~500MB) is constitutionally exempt from the 100MB memory budget. All other processing (document text, Presidio framework, regex recognizers, output buffers) must stay under 100MB.
- The validation corpus (`tests/fixtures/pii/`) will be populated with synthetic contracts containing known PII entities. The corpus does not need to be representative of real-world contracts for initial validation.
- Config change detection uses a simple hash comparison (threshold hash in `config.yml` vs. hash stored in cached result). More sophisticated change detection (e.g., per-recognizer config) is out of scope.
- The `--no-pii` flag is intended for fully local setups (no cloud API calls). If a user specifies `--no-pii` with a cloud provider configured, the system logs a warning but does not block the operation.
- PII stripping accuracy may degrade for non-English text or PII in images/scanned documents. The system logs warnings for these cases but does not guarantee accuracy.
- The encrypted mapping file is stored alongside the review result. If the mapping is corrupted or deleted, the original PII values cannot be recovered. The system does not implement backup or recovery mechanisms.
- The system aligns with GDPR data protection principles: purpose limitation (PII collected only for review), data minimization (retain only necessary PII), and retention limits (encrypted mappings expire after 30 days unless explicitly retained by user). Users can delete all PII data for a document at any time.
- The system supports documents up to 500 pages in length. Performance targets scale linearly from the 50-page baseline (e.g., 500 pages → <30 seconds processing time).
- Error recovery follows a fail-fast strategy: when PII stripping encounters an error mid-document, the system preserves partial results (successfully processed pages) and reports failed pages for manual retry, rather than discarding all progress or implementing automatic retry logic.
