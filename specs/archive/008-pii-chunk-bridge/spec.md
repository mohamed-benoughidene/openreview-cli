# Feature Specification: PII-to-Chunk Pipeline Bridge

**Feature Branch**: `feat/008-pii-chunk-bridge`

**Created**: 2026-07-01

**Status**: Draft

**Input**: User description: "N-4a from product blueprint: Bridge between PII stripping (Phase 3) and chunking (Phase 7) so that T014 integration test passes. Current strip_pii() joins all clause text into a single blob, losing clause boundaries."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Per-Clause PII Stripping with Clause Preservation (Priority: P1)

A lawyer has a parsed contract with 47 clauses containing PII (party names, dates, amounts). They run PII stripping followed by chunking. Each clause retains its structure — no clause boundaries are lost in the transition. The chunking system operates on clauses with PII already replaced by placeholders.

**Why this priority**: Without per-clause PII preservation, the chunking pipeline cannot operate on PII-stripped text — clause boundaries are destroyed, making hierarchical chunking impossible. This blocks the entire privacy-first architecture.

**Independent Test**: Can be tested by stripping PII from a list of clauses, verifying each output clause has the same id, title, level, and parent_id as the input, and that the text contains placeholders (not raw PII).

**Acceptance Scenarios**:

1. **Given** a list of 3 clauses with PII (party names, dates), **When** PII is stripped per-clause, **Then** each output clause preserves its original id, title, level, and parent_id
2. **Given** a clause with a party name "Acme Corp" in its text, **When** PII is stripped, **Then** the clause text contains `[PARTY_1]` (or equivalent placeholder) instead of "Acme Corp"
3. **Given** a clause with no PII, **When** PII is stripped, **Then** the clause text is unchanged and no mapping entries are created for it

---

### User Story 2 - End-to-End PII-Safe Chunking (Priority: P1)

A lawyer runs the full pipeline: parse → strip PII → chunk. The output chunks contain PII placeholders, not raw PII. The chunk structure (clause references, hierarchy) is intact. This is T014 from spec 007.

**Why this priority**: This is the integration acceptance test that proves Phase 3 and Phase 7 work together. Without it, the privacy-first chain from document to retrieval-ready chunks is unverified.

**Independent Test**: Can be tested by parsing a contract, stripping PII, chunking the result, and verifying all chunks contain only placeholder references (no raw PII). This is T014.

**Acceptance Scenarios**:

1. **Given** a parsed contract with PII, **When** the user strips PII and chunks the result, **Then** all chunks contain PII placeholders — no raw names, dates, emails, or other PII entities
2. **Given** a PII-stripped contract with encrypted mapping, **When** chunked, **Then** the chunking process does not read, modify, or expose the PII mapping

---

### User Story 3 - No Regression on Existing PII Pipeline (Priority: P2)

An existing user of the PII stripping feature runs their regular workflow (strip and persist). Nothing changes — the existing `strip_pii()` and `strip_and_persist()` functions behave identically. The new per-clause function is additive.

**Why this priority**: Regression in the existing PII pipeline would break all downstream consumers. The existing API must remain stable.

**Independent Test**: Can be tested by running the existing PII test suite and verifying no tests fail.

**Acceptance Scenarios**:

1. **Given** the existing PII stripping test suite, **When** run after adding the bridge, **Then** all existing tests pass with zero changes
2. **Given** a call to `strip_pii()` with the same arguments, **When** called before and after adding the bridge, **Then** the returned `PiiResult` is byte-identical

---

### Edge Cases

- What happens when an empty list of clauses is passed? — Returns empty list and empty mapping.
- What happens when a clause contains only PII (e.g., "[PARTY_1]") after stripping? — The clause text becomes the placeholder only; clause metadata is preserved.
- What happens when a clause's PII spans the boundary where the existing `strip_pii()` overlap buffer operates? — The per-clause replacement operates on individual clause text, not combined text, so overlap buffer shifting is not applicable.
- What happens when the PII mapping contains entities whose original value does not appear verbatim in any single clause (metadata entities)? — Metadata entities (FILENAME, AUTHOR, TITLE, COMPANY) are appended to the last clause's text as trailing placeholders.
- What happens when the same PII value appears in multiple clauses? — The shared mapping ensures the same placeholder is used across clauses; `assign_placeholders` already deduplicates by entity type.
- What happens when PII detection fails on one clause? — The function returns partial results (stripped clauses for successes) with a warning, matching the existing `strip_pii()` behavior.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a `strip_pii_clauses(clauses, document, **kwargs) -> tuple[list[Clause], PiiResult]` function that returns PII-stripped clauses alongside the standard PiiResult. The `PiiResult.stripped_text` MUST contain the joined text of all stripped clauses (consistent with the existing `strip_pii()` output). Each output clause MUST preserve all metadata fields as specified in FR-002.
- **FR-002**: Each output clause MUST preserve: `id`, `title`, `level`, `parent_id`, `source_page`, `source_paragraph`, `source_span` from the input clause
- **FR-003**: The output clause text MUST have all detected PII replaced with placeholders (e.g., `[PARTY_1]`), using the same `assign_placeholders` and mapping system as `strip_pii()`
- **FR-004**: The PII mapping returned in `PiiResult.mapping` MUST be a single unified mapping covering all clauses (not per-clause mappings), consistent with `strip_pii()` behavior
- **FR-005**: The existing `strip_pii()` and `strip_and_persist()` functions MUST remain unchanged — the bridge is additive only
- **FR-006**: An integration test MUST be added at `tests/integration/test_chunking_cli.py` that parses a contract, strips PII via `strip_pii_clauses`, chunks the result, and asserts no raw PII appears in any chunk (delivers T014 from spec 007)
- **FR-007**: Metadata entities (FILENAME, AUTHOR, TITLE, COMPANY) that cannot be placed into any single clause's text MUST be appended as trailing placeholders to the last clause. If the document has no metadata entities (e.g., no AUTHOR, TITLE, or COMPANY fields), no placeholders are appended.

### Key Entities

- **Clause**: Existing model from `src/openreview_cli/parsing/models.py` — the bridge operates on the same `Clause` dataclass, adding no new fields
- **PiiResult**: Existing model from `src/openreview_cli/pii/models.py` — returned alongside the clause list, with the same mapping, entities, audit data as the existing `strip_pii()` function

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The `strip_pii_clauses()` function preserves all clause metadata (id, title, level, parent_id) for 100% of input clauses — verifiable in unit tests
- **SC-002**: The T014 integration test for PII-to-chunk end-to-end passes — chunks from PII-stripped text contain only placeholder references, no raw PII
- **SC-003**: Zero regressions in the existing PII test suite — all existing `test_pii_*` and `test_precheck_pii` tests pass with no changes
- **SC-004**: Processing time for `strip_pii_clauses()` is within 10% of the equivalent `strip_pii()` call for the same document. Measurement: wall-clock time averaged over 3 consecutive runs on the same document, using `time.perf_counter()`.

## Assumptions

- The bridge reuses the existing `PiiEngine.detect_all_pages()` for detection but performs the text replacement per-clause rather than on the joined blob
- The existing `assign_placeholders` function is reused without changes — deduplication and mapping work the same way
- Metadata entities that don't appear in any single clause's text are appended to the last clause as a trailing placeholder string
- The bridge is implemented in `src/openreview_cli/pii/engine.py` as a new function alongside the existing `strip_pii()`
- The integration test (T014) lives in the existing `tests/integration/test_chunking_cli.py` which already imports the chunking module — the test is written when both 007 and 008 code are available
- No new external dependencies are required — all reuse existing Pydantic, Presidio, and stdlib
- No per-clause audit logging is added — the existing document-level audit (via `PiiResult.entities` + `build_audit`) covers entity counts

## Clarifications

### Session 2026-07-01

- Q: If PII detection fails on one clause, should the bridge return partial results or crash? → A: Return partial results with warnings (match existing `strip_pii()`).
- Q: What should `PiiResult.stripped_text` contain in the bridge return? → A: Joined text of all stripped clauses (match existing `strip_pii()`).
- Q: Should the bridge add per-clause audit logging? → A: No — reuse existing document-level audit only.
