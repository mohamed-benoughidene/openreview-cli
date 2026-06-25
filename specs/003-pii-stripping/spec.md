# Feature Specification: PII Stripping

**Feature Branch**: `feat/003-pii-stripping`

**Created**: 2026-06-25

**Status**: Draft

**Input**: User description: "Phase 3 — PII Stripping: Presidio analyzer + anonymizer wrapper, PII map storage (JSON per document), 3 privacy tiers"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Strip PII from Parsed Document Text (Priority: P1)

After parsing a contract (PDF or DOCX via Phase 2), the user runs a review command. Before any text is chunked, embedded, or sent to an external API, the tool automatically detects and replaces personally identifiable information — names, emails, phone numbers, addresses, dollar amounts, tax IDs, bank account numbers, dates of birth, passport/DL numbers, and company registration numbers — with deterministic placeholders like `[PARTY_A]`, `[AMOUNT_1]`, `[EMAIL_1]`. The stripped text is what flows downstream; the real values never leave the machine.

**Why this priority**: This is the core privacy gate. Without it, raw contract text (including party names, dollar figures, and contact details) would be sent to cloud AI providers, violating the project's constitutional Privacy First principle. Every downstream phase (chunking, embedding, comparison, memo generation) depends on receiving PII-stripped text.

**Independent Test**: Can be fully tested by passing a sample text string containing known PII entities through the stripping function and verifying that every entity is replaced with the correct placeholder type, the stripped text is returned, and the original values are preserved in the mapping output.

**Acceptance Scenarios**:

1. **Given** a parsed document text containing party names "ABC Corp." and "XYZ Inc.", **When** the PII stripping function processes the text, **Then** the output text contains `[PARTY_A]` and `[PARTY_B]` in place of the real names, and no real party names remain in the stripped text.
2. **Given** a parsed document text containing an email "john@acme.com", a phone number "+1-555-0123", and an address "123 Main St, Dover, DE 19901", **When** the PII stripping function processes the text, **Then** each entity is replaced with the correct placeholder type (`[EMAIL_1]`, `[PHONE_1]`, `[ADDRESS_1]`).
3. **Given** a parsed document text containing dollar amounts "$5,000,000" and "$1M", **When** the PII stripping function processes the text, **Then** amounts are replaced with `[AMOUNT_1]` and `[AMOUNT_2]`.
4. **Given** a parsed document text containing legal terms like "Force Majeure", "Indemnification", and "Confidentiality", **When** the PII stripping function processes the text, **Then** these legal terms are NOT replaced — they remain untouched in the stripped output.

---

### User Story 2 - Persist PII Mapping for Later Restoration (Priority: P1)

After PII stripping completes, the tool saves a mapping file (`pii_map.json`) that records which placeholder corresponds to which real value. This mapping is stored locally in the review directory (`~/.local/share/openreview/reviews/[review_id]/pii_map.json`). The mapping allows the memo generation phase to show the user "Party A = ABC Corp." alongside the anonymised analysis, without ever having sent "ABC Corp." to any API.

**Why this priority**: Without the mapping, stripped text is a one-way transformation — the user cannot relate `[PARTY_A]` back to the actual entity. The mapping is essential for the memo output to be useful.

**Independent Test**: Can be fully tested by stripping a text sample, writing the mapping to disk, reading it back, and verifying every placeholder resolves to its original value. Also verify the mapping file can be deleted (simulating review deletion).

**Acceptance Scenarios**:

1. **Given** a document has been PII-stripped producing placeholders `[PARTY_A]` → "ABC Corp." and `[AMOUNT_1]` → "$5,000,000", **When** the mapping is saved, **Then** a valid JSON file exists at the expected path containing `{"PARTY_A": "ABC Corp.", "AMOUNT_1": "$5,000,000"}`.
2. **Given** a saved PII mapping file, **When** the user deletes the review, **Then** the mapping file is deleted along with all other review artifacts.
3. **Given** a PII mapping file from a previous stripping run, **When** the same document is re-stripped, **Then** the mapping is overwritten with fresh results (not appended).
4. **Given** the user changes `privacy.pii_threshold` in config from 0.7 to 0.5, **When** a previously stripped document is re-processed, **Then** the mapping is regenerated from the original text using the new threshold and all downstream cached chunks (embeddings, comparisons) are invalidated.

---

### User Story 3 - Respect Privacy Tier Configuration (Priority: P2)

The tool's behaviour adjusts based on the configured privacy tier. In all three tiers (maximum, balanced, performance), PII stripping is ON by default. The user can explicitly disable stripping via `--no-pii` flag or `privacy.strip_pii: false` in config, but the tool warns that contract text may be sent to providers as-is.

**Why this priority**: Privacy tiers are a configuration concern that sits on top of the core stripping logic. The stripping engine (P1) must work independently; this story adds the configuration wiring.

**Independent Test**: Can be tested by setting `privacy.strip_pii` to `true` and `false` in config, running the stripping step, and verifying the stripping is applied or skipped accordingly. Verify the warning message when stripping is disabled.

**Acceptance Scenarios**:

1. **Given** `privacy.strip_pii` is `true` (default), **When** a document is processed, **Then** PII stripping runs before any downstream processing.
2. **Given** the user passes `--no-pii` on the CLI, **When** a document is processed, **Then** PII stripping is skipped and the tool displays a warning: "⚠️ PII stripping disabled. Contract text may be sent to providers as-is."
3. **Given** `privacy.tier` is set to `maximum` (all-local), **When** a document is processed with `--no-pii`, **Then** the tool still displays the PII warning but proceeds, since no data leaves the machine anyway.

---

### User Story 4 - Handle Stripping Failures Gracefully (Priority: P2)

If the PII detection engine crashes or is unavailable (e.g., Presidio model not installed, unexpected input causes an exception), the tool does not crash. It warns the user, suggests running with `--no-pii` to skip PII stripping, and asks the user to report the bug. The review does NOT proceed with unstripped text silently — the user must acknowledge the risk.

**Why this priority**: Graceful failure is critical for trust. A silent failure that sends unstripped text to a cloud API is worse than a crash.

**Independent Test**: Can be tested by simulating a Presidio crash (mocking the analyzer to raise an exception) and verifying the tool produces the correct error message and does not send unstripped text downstream.

**Acceptance Scenarios**:

1. **Given** the PII detection engine raises an unexpected exception during stripping, **When** the error is caught, **Then** the tool displays: "PII detection failed while processing clause 'Payment Terms' (NER phase). Run with --no-pii to skip stripping. Report this bug." and halts the review. The clause heading (structural metadata from Phase 2) is the only PII-safe context included — no offsets, no text snippets.
2. **Given** the PII detection model files are missing, **When** the stripping step is invoked, **Then** the tool displays: "PII detection model not found." with reinstallation instructions and halts.
3. **Given** a stripping failure has occurred, **When** the user re-runs with `--no-pii`, **Then** the review proceeds with the PII warning and no stripping.

---

### Edge Cases

- What happens when a document contains NO PII? The stripping function should return the text unchanged and produce an empty mapping `{}`.
- How does the system handle a document with PII entities that appear multiple times (e.g., "ABC Corp." mentioned 50 times)? All occurrences should map to the same placeholder `[PARTY_A]`.
- What happens when two different entities share the same name (e.g., "John Smith" appearing as both a signer and a witness)? Context-aware entity resolution is a future enhancement — for MVP, all instances of the same literal string map to the same placeholder.
- How does the system handle PII in uncommon formats (e.g., "Mohamed's obligation" where the name is possessive)? Entity-based detection (not regex) should detect the entity even in possessive or modified forms.
- What happens when the document is very short (e.g., a 1-paragraph NDA)? Stripping should still work and produce correct results.
- What happens when a legal term resembles PII (e.g., "Baker McKenzie" is both a law firm name and could be detected as a person's name)? The false replacement rate must stay under 5% — known legal entities and terms should not be replaced.
- What happens when the document contains non-English text (Arabic, CJK, Cyrillic — detected by Phase 2 parser)? Presidio's regex recognizers run on the non-English sections to catch structured PII (emails, phone numbers, amounts, tax IDs). The English NLP model does not run on non-English text — named entities in those scripts are not detected. The user receives a warning: "Non-English text detected — structured PII stripped, but named entities in non-English sections may remain."
- What happens when document metadata (filename, author, title, company) contains PII? Metadata fields are unconditionally redacted with typed placeholders — e.g., `Smith_Employment_2024.pdf` becomes `[FILENAME_1].pdf`, author "John Smith" becomes `[AUTHOR_1]`. The original metadata values are stored in the per-document PII mapping alongside body text entities.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST detect and replace the following PII entity types: party names, individual names, email addresses, phone numbers, physical addresses, dates of birth, dollar amounts, tax IDs, bank account numbers, passport/DL numbers, and company registration numbers.
- **FR-002**: System MUST use deterministic, typed placeholders for each entity type following the naming convention: `[PARTY_A]`, `[PARTY_B]`, `[NAME_1]`, `[EMAIL_1]`, `[PHONE_1]`, `[ADDRESS_1]`, `[DOB_1]`, `[AMOUNT_1]`, `[TAX_ID_1]`, `[ACCT_1]`, `[ID_1]`, `[REG_1]`, `[DATE_1]`. Placeholders MUST be assigned by sorting detected entity values alphabetically before numbering — the same entity always receives the same placeholder across re-runs regardless of detection order.
- **FR-003**: System MUST ensure that repeated occurrences of the same entity map to the same placeholder throughout the document (consistency).
- **FR-004**: System MUST produce two outputs from stripping: (a) the stripped text with placeholders, and (b) a mapping dictionary of placeholder → original value.
- **FR-005**: System MUST persist the PII mapping as a JSON file at the review's local storage path.
- **FR-006**: System MUST use entity-based NLP detection (backed by spaCy `en_core_web_lg` via Presidio) to detect PII patterns at the entity level. NLP detections are subject to a configurable confidence threshold with a default of 0.7 — entities below the threshold are skipped. Regex recognizers (emails, phone numbers, amounts, tax IDs, dates) always run at full confidence and are not affected by this threshold. The threshold is configurable via `privacy.pii_threshold` in `config.yml`.
- **FR-007**: System MUST strip PII immediately after document parsing and before any chunking, embedding, or API call — it is the first transformation applied to extracted text.
- **FR-008**: System MUST respect the `privacy.strip_pii` configuration setting and the `--no-pii` CLI flag.
- **FR-009**: System MUST display a warning when PII stripping is disabled: "⚠️ PII stripping disabled. Contract text may be sent to providers as-is."
- **FR-010**: System MUST halt the review (not proceed silently) if PII stripping fails unexpectedly, displaying an actionable error message. The error message MUST include the clause heading (structural metadata from Phase 2) and the processing phase ("regex phase", "NER phase", or "anonymizer phase") but MUST NOT include character offsets or text snippets. Example: "PII detection failed while processing clause 'Payment Terms' (NER phase). Run with --no-pii to skip stripping. Report this bug."
- **FR-011**: System MUST NOT replace common legal terms, clause headings, or standard contract vocabulary with PII placeholders (false replacement rate under 5%).
- **FR-012**: System MUST NOT send the PII mapping file to any external service — it stays local.
- **FR-013**: System MUST delete the PII mapping file when the user deletes the associated review.
- **FR-014**: System MUST operate within the project's memory budget — PII stripping of a 50-page document must not push peak memory above 100 MB (110 MB floor). The NLP model (`en_core_web_lg`) is exempt from this budget per the constitution amendment (Principle III exception).
- **FR-015**: System MUST encrypt PII mapping values at rest using AES encryption (Presidio's built-in encrypt operator) before writing to disk. The encryption key is stored in the user's config file. The mapping file MUST be created with `chmod 600` permissions.
- **FR-016**: When the Phase 2 parser detects non-English text (Arabic, CJK, Cyrillic) in a document, the system MUST run Presidio's regex recognizers only (no NLP NER) on those sections and MUST display a warning to the user that named entities in non-English text may not have been stripped.
- **FR-017**: System MUST unconditionally redact document metadata fields (filename, author, title, company) with typed placeholders (`[FILENAME_1]`, `[AUTHOR_1]`, `[TITLE_1]`, `[COMPANY_1]`). Original metadata values are stored in the per-document PII mapping alongside body text entities.
- **FR-018**: System MUST write a PII audit file (`pii_audit.json`) alongside the mapping file, containing entity detection counts (per type), confidence ranges, processing duration, threshold used, and a count of non-English sections encountered. The audit file MUST NOT contain any actual PII values — only counts and metadata.
- **FR-019**: PII stripping MUST process pages sequentially with a 50-character overlap buffer between consecutive pages (to catch entities that span page breaks). The system MUST display per-page progress: "Stripping PII... page 12/50".
- **FR-020**: When a document is re-stripped (due to config change, threshold change, or explicit re-run), the system MUST process the original text from scratch, regenerate the mapping and audit files, and invalidate all downstream cached chunks (embeddings, comparisons). There is no incremental / append mode for stripping.
 
### Key Entities

- **PII Entity**: A detected piece of personally identifiable information, with attributes: entity type (name, email, amount, etc.), original value, start/end position in source text, and confidence score from the detection engine.
- **PII Placeholder**: A deterministic token replacing a PII entity in the stripped text. Format: `[TYPE_N]` where TYPE is the entity category and N is a sequential counter per type.
- **PII Mapping**: A dictionary mapping each placeholder string to its original value. Serialized as JSON. Scoped to a single document (one mapping file per document). In multi-document reviews, each document has its own mapping file. Cross-document entity alignment is deferred to a future enhancement.
- **Privacy Configuration**: The user's chosen privacy tier and strip_pii boolean setting, sourced from `config.yml` or CLI flags, that determines whether stripping runs.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: PII detection recall is at least 90% — of actual PII entities in a test corpus of 50 seeded documents, at least 90% are detected and replaced.
- **SC-002**: PII detection precision is at least 95% — of items the system replaces, at least 95% are genuinely PII (not legal terms or standard vocabulary).
- **SC-003**: False replacement rate is under 5% — legal terms like "Force Majeure", "Indemnification", law firm names used as clause references, and standard contract vocabulary are NOT replaced.
- **SC-004**: PII stripping of a 50-page document completes in under 3 seconds on the reference machine (8 GB RAM, 2-core CPU, no GPU). This target measures per-document processing time only (after the NLP model is loaded and warm). The one-time model load time is documented separately.
- **SC-005**: Peak memory during PII stripping stays under 100 MB (110 MB floor) when processing a 50-page document. The loaded NLP model (`en_core_web_lg`) is exempt from this budget per the constitution amendment — the processing overhead (Presidio framework, regex recognizers, output buffers, document text) must stay under 100 MB.
- **SC-006**: The PII mapping file round-trips correctly — every placeholder in the stripped text has a corresponding entry in the mapping, and every entry in the mapping corresponds to a placeholder in the stripped text.
- **SC-007**: When PII stripping is disabled via `--no-pii` or config, a user-visible warning is displayed in 100% of cases.
- **SC-008**: Metadata fields (filename, author, title, company) are redacted in 100% of cases — no PII leaks through document metadata.
- **SC-009**: A `pii_audit.json` file is present alongside every `pii_map.json` after stripping. The audit file contains zero actual PII values.
- **SC-010**: The confidence threshold is configurable in `config.yml` via `privacy.pii_threshold` with a default of 0.7. Changing the threshold causes the document to be re-stripped from the original text and downstream cache invalidated.

## Assumptions

- Phase 2 (Document Parsing) is complete and provides structured text output that can be fed to the PII stripping engine.
- The Presidio analyzer and anonymizer libraries are compatible with Python 3.12. The NLP model loading (`en_core_web_lg`, ~500 MB in RAM) is exempt from the 100 MB peak memory budget per the constitution amendment (Principle III). The remaining processing overhead (Presidio framework, regex recognizers, document buffers) must stay under 100 MB.
- The Presidio default NLP engine uses spaCy `en_core_web_lg` for detecting named entities (PERSON, ORG, LOCATION) in English text. Arabic language PII patterns are out of scope for this phase. Non-English text (CJK, Cyrillic) detected by Phase 2 parser is handled by regex recognizers only, with a warning to the user.
- The PII mapping file format is a flat JSON dictionary (not nested), keyed by placeholder string with original value as the value.
- The `config.yml` schema from Phase 1 already includes the `privacy.strip_pii` and `privacy.tier` fields. This phase adds a new `privacy.pii_threshold` field (default 0.7) but does not modify existing fields.
- Presidio's built-in CUDA/MPS auto-detection is used per the constitution GPU mandate (Principle III). GPU detection and acceleration are automatic — no configuration required from the user. CPU is the default fallback.
- PII stripping runs synchronously (not async) since it is a local CPU operation that precedes any network calls.
- Context-aware entity disambiguation (e.g., distinguishing "Baker McKenzie" the law firm from a person named "Baker McKenzie") is a future enhancement. The MVP relies on Presidio's built-in entity recognition.

## Clarifications

### Session 2026-06-25

- Q: What NLP model should be used given the 100 MB memory budget conflict with en_core_web_lg (~500 MB)? → A: Use en_core_web_lg (~500 MB) and amend constitution Principle III to grant a one-time memory exception for NLP model loading. Processing overhead (Presidio framework, regex, buffers) stays under 100 MB.
- Q: How should PII stripping handle non-English text (Arabic, CJK, Cyrillic) detected by Phase 2 parser? → A: Run Presidio's regex recognizers only (catches emails, phone numbers, amounts, tax IDs) on non-English sections. English NLP model does not run on non-English text. Display a warning that named entities in those sections may remain.
- Q: What level of protection should the PII mapping file have? → A: chmod 600 file permissions + AES encryption of stored values using Presidio's encrypt operator, with the encryption key stored in the user's config file.
- Q: Should the 3-second PII stripping target include the one-time model load? → A: No — measure per-document processing time only (after model is warm). Document the cold-start time separately.
- Q: How should the 50 test documents for accuracy validation be created? → A: 25 auto-generated using Presidio's fake PII generator + 25 manually annotated real contracts from the Phase 2 test corpus.
- Q: How should multi-document reviews handle PII mappings? → A: One mapping per document. Cross-document entity alignment deferred to future enhancement.
- Q: Should document metadata (filename, author, title, company) be stripped? → A: Yes — unconditionally redact metadata with typed placeholders (`[FILENAME_1]`, `[AUTHOR_1]`). Original values stored in the PII mapping.
- Q: What confidence threshold should filter low-quality NLP detections? → A: Configurable in `config.yml` via `privacy.pii_threshold`, default 0.7. Research showed Presidio achieves 22.7% precision on business documents at default threshold of 0; 0.7 eliminates most false positives from legal terms and law firm names.
- Q: Should the system produce an audit trail of what was stripped? → A: Yes — `pii_audit.json` alongside the mapping, with entity counts per type, confidence ranges, and duration. Zero actual PII values in the audit file.
- Q: What detail should go into error messages when stripping fails? → A: Clause heading (structural metadata) + processing phase only. No offsets, no text snippets.
- Q: When does re-stripping regenerate from scratch vs reuse cached results? → A: Always re-strip from the original text on any config change. Invalidate all downstream cached data.
- Q: Should progress be shown during stripping? → A: Yes — page-by-page with a 50-character overlap buffer. Display "Stripping PII... page 12/50".
- Q: Should placeholders be stable across re-runs? → A: Yes — sort entity values alphabetically before numbering. Same entity always gets the same placeholder regardless of detection order.
