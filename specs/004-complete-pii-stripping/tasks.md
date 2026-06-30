# Tasks: Complete PII Stripping Integration

**Input**: Design documents from `/specs/004-complete-pii-stripping/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/cli-schema.md, contracts/config-schema.md, quickstart.md

**Tests**: Integration tests are included per user story as specified in spec.md (FR-003, FR-006, FR-007).

**Organization**: Tasks grouped by user story (US1–US5) per spec.md priorities P1–P5.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add new dependency, create directory structure, extend SQLite schema

- [X] T001 Add `cryptography` dependency via `uv add cryptography` (provides Fernet encryption for PII mapping)
- [X] T002 [P] Create `src/openreview_cli/review/` directory with `__init__.py`
- [X] T003 [P] Create SQLite migration `src/openreview_cli/storage/migrations/002_pii_tables.sql` adding `pii_cache` and `pii_audit_trail` tables per data-model.md schema
- [X] T004 Wire migration T003 into `src/openreview_cli/storage/database.py` `run_migrations()` function

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core PII infrastructure that all user stories depend on — Fernet encryption, config hash, retention, error recovery

**CRITICAL**: No user story work can begin until this phase is complete

- [X] T005 [P] Implement Fernet encryption module `src/openreview_cli/pii/encryption.py` — `derive_key(document_hash, salt) -> Fernet` using HKDF (SHA-256, 32-byte key) from `cryptography.hazmat.primitives.kdf.hkdf.HKDF`, `encrypt_pii_mapping(data: bytes, key) -> bytes`, `decrypt_pii_mapping(token: bytes, key) -> bytes`, handle `InvalidToken` for corrupted files
- [X] T006 [P] Implement config hash module `src/openreview_cli/pii/config_hash.py` — `compute_config_hash(pii_config: dict) -> str` serializes pii config to canonical JSON (sorted keys, no whitespace) and returns SHA-256 hex digest
- [X] T007 [P] Implement GDPR retention module `src/openreview_cli/pii/retention.py` — `cleanup_expired(db_path) -> int` deletes rows from `pii_cache` where `expiry_at < now` and removes associated mapping files, `delete_pii_data(db_path, document_hash_prefix) -> dict` deletes mapping + cache + audit for a document hash prefix (min 8 chars)
- [X] T008 Update `src/openreview_cli/pii/mapping.py` to use Fernet encryption from T005 instead of current Presidio-based encryption — `write_pii_mapping()` encrypts with Fernet, `read_pii_mapping()` decrypts, store salt alongside encrypted file
- [X] T009 Update `src/openreview_cli/pii/engine.py` to implement fail-fast error recovery with partial result preservation — catch exceptions per-page, collect `failed_pages` list, raise `PartialProcessingError` if any pages fail while preserving successfully processed pages in results
- [X] T010 Add `PartialProcessingError` exception class to `src/openreview_cli/pii/models.py` with `failed_pages: list[int]`, `successful_pages: list[int]`, `error_messages: dict[int, str]` attributes
- [X] T011 [P] Create `src/openreview_cli/pii/cache.py` — `PiiCache` class wrapping SQLite `pii_cache` table: `get(document_hash) -> row | None`, `put(document_hash, config_hash, review_result_path, mapping_path, ttl_days=30)`, `is_valid(document_hash, current_config_hash) -> bool`

**Checkpoint**: Foundation ready — Fernet encryption, config hash, retention, caching, error recovery all in place

---

## Phase 3: User Story 1 — First Review Command with Automatic PII Stripping (Priority: P1) MVP

**Goal**: Wire PII stripping to the `precheck` review subcommand so documents are automatically PII-stripped before processing. User runs `openreview precheck contract.pdf` and gets a PII-stripped review memo with encrypted mapping and audit trail.

**Independent Test**: Run `openreview precheck tests/fixtures/pii/sample_contract.pdf` — verify PII placeholders in output, encrypted mapping created, audit trail logged, exit code 0.

### Tests for User Story 1

- [X] T012 [P] [US1] Write integration test for automatic PII stripping in `tests/integration/test_precheck_pii.py` — test that `openreview precheck` on a fixture PDF produces memo with `[PARTY_A]`/`[DATE]`/`[AMOUNT]` placeholders, encrypted mapping file exists, audit trail row created with `status="success"`, exit code 0

### Implementation for User Story 1

- [X] T013 [P] [US1] Create `src/openreview_cli/review/base.py` — `ReviewCommand` base class with `run(document_path, pii_enabled=True)` method that orchestrates: parse document → strip PII (if enabled) → create encrypted mapping via `write_pii_mapping()` → write audit trail via `write_pii_audit()` → update `PiiCache` → return review result path
- [X] T014 [P] [US1] Create `src/openreview_cli/review/precheck.py` — `PreCheckCommand(ReviewCommand)` implementing NDA review logic (placeholder: parse clauses → output clause summary as review memo)
- [X] T015 [US1] Register `precheck` subcommand in `src/openreview_cli/app.py` — `@app.command()` decorator, accepts `DOCUMENT_PATH` argument, instantiates `PreCheckCommand`, calls `run()`, handles `PartialProcessingError` (exit code 2) and general errors (exit code 1), prints Rich-formatted success/partial output per contracts/cli-schema.md
- [X] T016 [US1] Add `openreview pii list` and `openreview pii delete` subcommands to `src/openreview_cli/app.py` using `retention.py` from T007 — list shows documents with PII data, delete removes all PII data for a document hash prefix

**Checkpoint**: `openreview precheck contract.pdf` works end-to-end with automatic PII stripping, encrypted mapping, audit trail, and `openreview pii list/delete` management commands

---

## Phase 4: User Story 2 — Opt-Out with --no-pii Flag (Priority: P2)

**Goal**: Allow users to skip PII stripping with `--no-pii` flag for fully local setups. System processes raw text, logs warning, no encrypted mapping created.

**Independent Test**: Run `openreview precheck --no-pii contract.pdf` — verify raw PII in output, no mapping file, warning logged, exit code 0.

### Tests for User Story 2

- [X] [P] [US2] Write integration test for `--no-pii` flag in `tests/integration/test_no_pii_flag.py` — test that `openreview precheck --no-pii` produces memo with raw PII values intact, no encrypted mapping file created, warning "PII stripping disabled" logged, audit trail row with `entity_count=0`

### Implementation for User Story 2

- [X] [US2] Add `--no-pii` flag to `precheck` command in `src/openreview_cli/app.py` — boolean flag (default False), when True: skip PII stripping step in `ReviewCommand.run()`, log warning "PII stripping disabled. Raw text processed.", skip encrypted mapping creation, still create audit trail with `entity_count=0`
- [X] [US2] Add `--pii-threshold FLOAT` option to `precheck` command in `src/openreview_cli/app.py` — overrides `config.yml` threshold for this run only, mutually exclusive with `--no-pii` (validate and error if both provided)

**Checkpoint**: `openreview precheck --no-pii contract.pdf` produces raw output with warning; `--pii-threshold` overrides config

---

## Phase 5: User Story 3 — Config Change Detection and Re-Stripping (Priority: P3)

**Goal**: Detect PII config changes via threshold hash comparison and re-process when config differs from cached result.

**Independent Test**: Run precheck → change threshold in config.yml → re-run → verify re-processing occurred (entity count changed, config hash updated).

### Tests for User Story 3

- [X] [P] [US3] Write integration test for config change detection in `tests/integration/test_config_change.py` — test that: (1) first run caches result with config hash A, (2) changing threshold produces config hash B, (3) second run detects mismatch and re-processes, (4) cache updated with new hash, (5) running without config change uses cached result

### Implementation for User Story 3

- [X] [US3] Update `ReviewCommand.run()` in `src/openreview_cli/review/base.py` to check `PiiCache.is_valid(document_hash, current_config_hash)` before processing — if cache valid, load cached result; if cache miss or hash mismatch, re-run PII stripping and update cache
- [X] [US3] Add `--force-reprocess` flag to `precheck` command in `src/openreview_cli/app.py` — forces re-processing even if cached result exists (bypasses config hash check)

**Checkpoint**: Config changes trigger automatic re-processing; `--force-reprocess` overrides cache

---

## Phase 6: User Story 4 — PII Accuracy Validation (Priority: P4)

**Goal**: Validate PII detection accuracy (recall ≥90%, precision ≥95%) against the seeded corpus with ground truth annotations.

**Independent Test**: Run `pytest tests/integration/test_pii_accuracy.py -v` — verify recall ≥90%, precision ≥95%, zero false positives on clean text.

### Tests for User Story 4

- [X] [P] [US4] Implement PII accuracy validation test in `tests/integration/test_pii_accuracy.py` — load `tests/fixtures/pii/seeded_contracts/ground_truth.json`, run PII detection on each contract, compute recall (true_positives / total_ground_truth) and precision (true_positives / total_detections), assert recall ≥90% and precision ≥95%, assert zero false positives on `no_pii_document.txt`

### Implementation for User Story 4

- [X] [US4] Add accuracy report output to `tests/integration/test_pii_accuracy.py` — print total ground truth entities, detected entities, true positives, false positives, false negatives, recall %, precision %

**Checkpoint**: Accuracy validation passes with recall ≥90%, precision ≥95%, zero false positives on clean text

---

## Phase 7: User Story 5 — PII Memory Budget Validation (Priority: P5)

**Goal**: Validate peak memory <100 MB (excluding NLP model) during PII stripping of a 500-page document.

**Independent Test**: Run `pytest tests/integration/test_pii_memory.py -v -m memory` — verify peak memory <100 MB, processing time <30 seconds.

### Tests for User Story 5

- [X] [P] [US5] Implement PII memory validation test in `tests/integration/test_pii_memory.py` — generate 500-page synthetic document with 2000 PII entities, run PII stripping with `tracemalloc` enabled, assert peak memory <100 MB (excluding NLP model), assert processing time <30 seconds

### Implementation for User Story 5

- [X] [US5] Add memory report output to `tests/integration/test_pii_memory.py` — print document page count, PII entity count, peak memory in MB, processing time in seconds

**Checkpoint**: Memory validation passes with peak <100 MB and processing time <30s for 500 pages

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Full test suite sweep, pre-commit validation, quickstart validation

- [X] [P] Add `pii` config section schema validation to `src/openreview_cli/config/loader.py` — validate `threshold` (float 0.0–1.0), `enabled` (bool), `retention_days` (int 1–365), `enabled_recognizers` (list of valid recognizer names), `placeholder_format` (string containing `{type}`) per contracts/config-schema.md
- [X] [P] Add CLI background cleanup hook — on CLI startup, run `retention.cleanup_expired()` to delete expired PII mappings (best-effort, non-blocking, log count deleted)
- [X] Run `uv run pytest tests/ -v` — full test suite, all pass
- [X] Run `uvx pre-commit run --all-files` — ruff, ruff-format, mypy, pytest-fast all pass
- [X] Run quickstart.md validation scenarios 1–7 end-to-end and verify all expected outcomes match

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Foundational — MVP, must complete first
- **US2 (Phase 4)**: Depends on US1 (adds `--no-pii` to precheck command from US1)
- **US3 (Phase 5)**: Depends on US1 (adds config change detection to ReviewCommand from US1)
- **US4 (Phase 6)**: Depends on Foundational only (accuracy test uses PiiEngine directly, independent of review commands)
- **US5 (Phase 7)**: Depends on Foundational only (memory test uses PiiEngine directly, independent of review commands)
- **Polish (Phase 8)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 (P1)**: Can start after Foundational — no dependencies on other stories
- **US2 (P2)**: Depends on US1 (extends precheck command with `--no-pii`)
- **US3 (P3)**: Depends on US1 (extends ReviewCommand with cache check)
- **US4 (P4)**: Independent of US1–US3 (uses PiiEngine directly)
- **US5 (P5)**: Independent of US1–US3 (uses PiiEngine directly)

### Within Each User Story

- Tests written and FAIL before implementation (TDD per AGENTS.md)
- Models before services
- Services before CLI registration
- Core implementation before integration

### Parallel Opportunities

- Phase 1: T002, T003 can run in parallel (different files)
- Phase 2: T005, T006, T007, T011 can run in parallel (different files)
- Phase 3: T012, T013, T014 can run in parallel (test, base, precheck — different files)
- Phase 4: T017 (test) can run in parallel with nothing (single file)
- Phase 5: T020 (test) can run in parallel with nothing (single file)
- Phase 6: T023 (test) can run in parallel with nothing (single file)
- Phase 7: T025 (test) can run in parallel with nothing (single file)
- Phase 8: T027, T028 can run in parallel (different files)

---

## Parallel Example: Phase 2 (Foundational)

```text
# Launch all independent foundational modules together:
Task: "T005 Implement Fernet encryption in src/openreview_cli/pii/encryption.py"
Task: "T006 Implement config hash in src/openreview_cli/pii/config_hash.py"
Task: "T007 Implement GDPR retention in src/openreview_cli/pii/retention.py"
Task: "T011 Create PiiCache in src/openreview_cli/pii/cache.py"

# Then sequentially (depend on T005):
Task: "T008 Update mapping.py to use Fernet"
Task: "T009 Update engine.py for error recovery"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T004)
2. Complete Phase 2: Foundational (T005–T011)
3. Complete Phase 3: US1 — First Review Command (T012–T016)
4. **STOP and VALIDATE**: Run `openreview precheck tests/fixtures/pii/sample_contract.pdf` — verify PII stripped, mapping created, audit logged
5. Demo if ready

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. US1 → `precheck` with automatic PII stripping → MVP!
3. US2 → `--no-pii` flag → user control over privacy/accuracy
4. US3 → Config change detection → threshold tuning works
5. US4 → Accuracy validation → confidence in PII engine quality
6. US5 → Memory validation → confidence in hardware budget
7. Polish → Full suite green, pre-commit clean

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- TDD: tests written before implementation per AGENTS.md convention
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Existing PII module (`src/openreview_cli/pii/`) has 6 files — tasks extend it, not replace it
- `cryptography` is the only new dependency (justified by Fernet encryption requirement)
