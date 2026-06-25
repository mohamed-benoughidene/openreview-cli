# Tasks: PII Stripping — Phase 3

**Input**: Design documents from `specs/003-pii-stripping/`

**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/strip_pii.md, quickstart.md

**Organization**: Tasks are grouped by user story with TDD workflow — tests are written FIRST (they fail), then implementation.

## Format

- `[ID]` — sequential task number in execution order
- `[P]` — can run in parallel (different files, no dependencies)
- `[Story]` — which user story this task belongs to (US1, US2, US3, US4)

---

## Phase 1: Setup

**Purpose**: Add dependencies, download NLP model, create module skeleton

- [ ] T001 Install PII dependencies via `uv add presidio-analyzer presidio-anonymizer`
- [ ] T002 [P] Download spaCy model: `uv run python -m spacy download en_core_web_lg`
- [ ] T003 Create `src/openreview_cli/pii/` module with `__init__.py` exporting `strip_pii`, `PiiResult`, `PiiEntity`, `PiiError`
- [ ] T004 [P] Create test fixture directories: `tests/fixtures/pii/seeded_contracts/`, add `no_pii_document.txt`, `multi_occurrence.txt`, `non_english_mixed.txt`
- [ ] T004a [P] Generate 25 auto-generated seeded PII documents using Presidio's synthetic PII generator in `tests/fixtures/pii/seeded_contracts/auto/` and annotate 25 manually annotated documents from Phase 2 test corpus in `tests/fixtures/pii/seeded_contracts/manual/` per SC-001/SC-002/SC-003
- [ ] T005 [P] Add `pii_error()` constant to `src/openreview_cli/errors.py` with exit code 9

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Dataclasses, error types, config fields — MUST be complete before any user story

- [ ] T006 [P] Create `PiiEntity` dataclass (`@dataclass(slots=True)`) in `src/openreview_cli/pii/models.py` with fields: `entity_type`, `original_value`, `start`, `end`, `score`, `placeholder`, `source`
- [ ] T007 [P] Create `PiiResult` dataclass (`@dataclass(slots=True)`) in `src/openreview_cli/pii/models.py` with fields: `stripped_text`, `mapping`, `entities`, `page_count`, `duration_seconds`, `warnings`
- [ ] T008 [P] Create `PiiAudit` dataclass and `EntityTypeStats` nested dataclass in `src/openreview_cli/pii/models.py` with validation rules (no PII values, counts match)
- [ ] T009 [P] Create `PiiError(Exception)` in `src/openreview_cli/pii/models.py` with fields: `exit_code=9`, `category`, `clause_heading`, `phase`, `message`, `action`
- [ ] T010 Add `privacy.pii_threshold` field (default 0.7) and `privacy.pii_encryption_key` field to `src/openreview_cli/config/loader.py`
- [ ] T011 [P] Add `get_review_dir(review_id)` helper to `src/openreview_cli/config/paths.py` returning `~/.local/share/openreview/reviews/{review_id}/`

**Checkpoint**: Foundation ready — dataclasses, config fields, error types exist

---

## Phase 3: User Story 1 — Strip PII from Parsed Document Text (Priority: P1) 🎯 MVP

**Goal**: Core PII detection engine. Accepts parsed clauses + document metadata, detects PII via Presidio (NLP + regex), replaces with deterministic placeholders, redacts metadata.

**Independent Test**: `uv run pytest tests/unit/test_pii_engine.py tests/unit/test_pii_recognizers.py tests/unit/test_pii_placeholders.py -v`

### Tests for User Story 1 (TDD: write first, they FAIL)

- [ ] T012 [P] [US1] Unit test for `PiiEntity`, `PiiResult`, `PiiAudit`, `PiiError` dataclasses in `tests/unit/test_pii_models.py`
- [ ] T013 [P] [US1] Unit test for custom `AMOUNT` recognizer regex in `tests/unit/test_pii_recognizers.py` — test `$5,000,000`, `$1M`, `$500` patterns
- [ ] T014 [P] [US1] Unit test for custom `TAX_ID` recognizer regex in `tests/unit/test_pii_recognizers.py` — test EIN `12-3456789`, SSN patterns
- [ ] T015 [P] [US1] Unit test for custom `ID_DOCUMENT` and `REG_NUMBER` recognizers in `tests/unit/test_pii_recognizers.py`

### Implementation for User Story 1

- [ ] T016 [P] [US1] Implement custom regex recognizers in `src/openreview_cli/pii/recognizers.py` — `AmountRecognizer`, `TaxIdRecognizer`, `IdDocumentRecognizer`, `RegNumberRecognizer`
- [ ] T017 [US1] Implement `PiiEngine` class in `src/openreview_cli/pii/engine.py` — wraps Presidio `AnalyzerEngine` with spaCy `en_core_web_lg` backend, lazy imports, `score_threshold=0.7`
- [ ] T018 [US1] [after T016, T017] Implement custom recognizer registration in `PiiEngine.__init__()` — register all custom recognizers via `analyzer.registry.add_recognizer()`
- [ ] T019 [US1] Implement `detect_on_page(text, threshold)` method in `PiiEngine` — call `analyzer.analyze(score_threshold=threshold)`, return list of entity spans with NLP scores plus regex-only handling for non-English sections
- [ ] T020 [P] [US1] Implement placeholder assignment in `src/openreview_cli/pii/placeholders.py` — group by entity type → sort unique values alphabetically → assign `[TYPE_N]` or `[PARTY_X]`, build mapping dict
- [ ] T021 [US1] Implement metadata redaction in `src/openreview_cli/pii/engine.py` — parse filename, author, title, company into `[FILENAME_N]`, `[AUTHOR_1]`, `[TITLE_1]`, `[COMPANY_1]`, add to mapping
- [ ] T022 [US1] Implement `strip_pii()` public function in `src/openreview_cli/pii/__init__.py` — orchestrates: metadata redaction → page-sequential detection → placeholder assignment → text replacement (longest-first)
- [ ] T023 [US1] Implement page-sequential processing with 50-character overlap buffer in `PiiEngine.detect_all_pages()` — only emit entities whose start is ≥ overlap length

**Checkpoint**: Core stripping works — parsed text goes in, stripped text + mapping + entities come out

---

## Phase 4: User Story 2 — Persist PII Mapping for Later Restoration (Priority: P1)

**Goal**: Encrypted PII mapping I/O — write encrypted mapping to disk, read it back, delete on review removal.

**Independent Test**: `uv run pytest tests/unit/test_pii_mapping.py tests/integration/test_pii_strip_command.py -v`

### Tests for User Story 2 (TDD: write first, they FAIL)

- [ ] T024 [P] [US2] Unit test for `write_pii_mapping()` in `tests/unit/test_pii_mapping.py` — write encrypted JSON, verify chmod 600, verify version key exists
- [ ] T025 [P] [US2] Unit test for `read_pii_mapping()` — read back same file, decrypt, verify original values; test wrong key raises `PiiError`
- [ ] T026 [P] [US2] Unit test for `write_pii_audit()` in `tests/unit/test_pii_audit.py` — verify JSON structure, zero PII values assertion
- [ ] T027 [P] [US2] Integration test for end-to-end strip flow in `tests/integration/test_pii_strip_command.py` — parsed document → stripped text + encrypted mapping + audit, round-trip validation, and performance assertion (warm stripping of 50-page document <3s per SC-004). Also assert mapping file path is never included in any HTTP request payload (architectural invariant per FR-012).

### Implementation for User Story 2

- [ ] T028 [US2] Implement `write_pii_mapping()` in `src/openreview_cli/pii/mapping.py` — serialize mapping dict, encrypt each value via Presidio `AnonymizerEngine` with `OperatorConfig("encrypt", {"key": crypto_key})`, write JSON with chmod 600
- [ ] T029 [US2] Implement `read_pii_mapping()` in `src/openreview_cli/pii/mapping.py` — read JSON, decrypt each value via Presidio `DeanonymizeEngine` with same key, return dict
- [ ] T030 [US2] Implement `write_pii_audit()` in `src/openreview_cli/pii/audit.py` — derive `PiiAudit` from entity list, serialize to JSON, write alongside mapping
- [ ] T031 [US2] Implement encryption key management in `PiiEngine` — check config for key on init, auto-generate random 256-bit key with `secrets.token_urlsafe(32)[:32]` if missing, write to config
- [ ] T031a [P] [US2] Create integration test skeleton in `tests/integration/test_pii_accuracy.py` — define test corpus fixtures, recall/precision calculation, 90%/95% thresholds per SC-001/SC-002/SC-003
- [ ] T031b [P] [US2] Create integration test skeleton in `tests/integration/test_pii_memory.py` — `tracemalloc` start/stop, 50-page seeded document, assert peak <100 MB (excluding model baseline) per SC-005

**Checkpoint**: PII mapping round-trips correctly — encrypted on disk, decrypts on read, audit trail present

---

## Phase 5: User Story 3 — Respect Privacy Tier Configuration (Priority: P2)

**Goal**: `--no-pii` flag, `privacy.strip_pii` config, configurable threshold, re-strip on config change.

**Independent Test**: `uv run pytest tests/integration/test_pii_config.py -v`

### Tests for User Story 3 (TDD: write first, they FAIL)

- [ ] T032 [P] [US3] Unit test for `strip_pii()` skipped when `privacy.strip_pii = False` in `tests/unit/test_pii_engine.py`
- [ ] T033 [P] [US3] Integration test for `--no-pii` flag and config-driven disabling in `tests/integration/test_pii_config.py` — verify warning displayed, no mapping/audit files created
- [ ] T034 [P] [US3] Integration test for threshold change triggers re-strip in `tests/integration/test_pii_config.py` — change threshold from 0.7 to 0.5, verify mapping regenerated, downstream cache invalidation signal

### Implementation for User Story 3

- [ ] T035 [US3] Add `--no-pii` flag to review commands in `src/openreview_cli/app.py` — display warning "⚠️ PII stripping disabled. Contract text may be sent to providers as-is." when set
- [ ] T036 [US3] Wire `strip_pii()` skip logic — check `privacy.strip_pii` from config AND `--no-pii` flag before calling the engine; if disabled, pass through original text unchanged
- [ ] T037 [US3] Implement config change detection — compare current `privacy.pii_threshold` hash to stored hash; if different, re-strip from original text, regenerate mapping, invalidate downstream cache

**Checkpoint**: Privacy tiers work — `--no-pii` skips stripping with warning, threshold changes trigger re-strip

---

## Phase 6: User Story 4 — Handle Stripping Failures Gracefully (Priority: P2)

**Goal**: PII engine crash → halt with actionable error (clause heading + phase, no offsets). Model not found → reinstall instructions. Invalid key → config error.

**Independent Test**: `uv run pytest tests/integration/test_pii_error_handling.py -v`

### Tests for User Story 6 (TDD: write first, they FAIL)

- [ ] T038 [P] [US4] Integration test for Presidio crash recovery in `tests/integration/test_pii_error_handling.py` — mock `analyzer.analyze()` to raise exception, verify `PiiError` is raised with exit_code=9, verify error message contains clause heading + phase, verify NO offsets or text snippets, verify no stripped output is produced (review is halted per FR-010)
- [ ] T039 [P] [US4] Integration test for missing model in `tests/integration/test_pii_error_handling.py` — simulate `OSError` during model load, verify "model not found" message with reinstall instructions
- [ ] T040 [P] [US4] Integration test for invalid encryption key in `tests/integration/test_pii_error_handling.py` — provide wrong-length key, verify `PiiError` with "Config error" message
- [ ] T041 [P] [US4] Integration test for non-English text warning in `tests/integration/test_pii_error_handling.py` — process `non_english_mixed.txt`, verify warning message and that regex recognizers fired on non-English sections

### Implementation for User Story 6

- [ ] T042 [US4] Implement `PiiError` raising in `PiiEngine.detect_on_page()` — catch Presidio exceptions, extract current clause heading and phase, raise `PiiError` with formatted message (no offsets, no text snippets)
- [ ] T043 [US4] Implement spaCy model-not-found handling in `PiiEngine.__init__()` — catch `OSError` on `spacy.load()`, raise `PiiError(category="model_not_found")` with reinstall instructions
- [ ] T044 [US4] Implement encryption key validation in `write_pii_mapping()` — check key length is 16, 24, or 32 bytes; raise `PiiError(category="invalid_key")` if not
- [ ] T045 [US4] Implement non-English warning in `PiiEngine.detect_on_page()` — check Phase 2 language flag per clause, skip NLP NER for non-English sections, add warning to `PiiResult.warnings`

**Checkpoint**: All error paths covered — crash halts with safe error, model missing tells user what to do, invalid key catches early

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Audit trail, progress display, accuracy validation, memory validation, pre-commit

- [ ] T046 [P] Implement Rich progress display in `PiiEngine.detect_all_pages()` — show `"Stripping PII... page 12/50"` with `rich.progress.Progress`
- [ ] T047 [US2] Implement `pii_map.json` deletion on review deletion — wire into existing review-deletion path in `src/openreview_cli/app.py`
- [ ] T048 [US1] Add `__all__` exports to `src/openreview_cli/pii/__init__.py` — export `strip_pii`, `PiiResult`, `PiiEntity`, `PiiAudit`, `PiiError`, `write_pii_mapping`, `read_pii_mapping`
- [ ] T049 Run accuracy validation: `uv run pytest tests/integration/test_pii_accuracy.py -v`
- [ ] T050 Run memory validation: `uv run pytest tests/integration/test_pii_memory.py -v -m memory`
- [ ] T051 Run full test suite and pre-commit: `uv run pytest tests/; uvx pre-commit run --all-files`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **User Story 1 (Phase 3, US1 — P1)**: Depends on Phase 2 — No dependencies on other stories
- **User Story 2 (Phase 4, US2 — P1)**: Depends on Phase 2 + Phase 3 (US1) — mapping I/O needs entities from engine
- **User Story 3 (Phase 5, US3 — P2)**: Depends on Phase 2 + Phase 3 (US1) — config wiring needs engine
- **User Story 4 (Phase 6, US4 — P2)**: Depends on Phase 2 + Phase 3 (US1) — error handling needs engine
- **Polish (Phase 7)**: Depends on all phases being complete

### Within Each User Story

- Tests are written FIRST (they FAIL), then implementation
- Models before services
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel
- Within a user story: all tests [P] can run in parallel, all implementation [P] can run in parallel
- US3 and US4 can be worked on in the same pass since both depend only on Phase 2 + Phase 3

---

## Parallel Example: User Story 1

```bash
# Write all tests for US1 in parallel:
Task: "tests/unit/test_pii_models.py"
Task: "tests/unit/test_pii_recognizers.py"
Task: "tests/unit/test_pii_engine.py"
Task: "tests/unit/test_pii_placeholders.py"

# Write all PII files for US1 in parallel:
Task: "src/openreview_cli/pii/models.py"
Task: "src/openreview_cli/pii/recognizers.py"
Task: "src/openreview_cli/pii/placeholders.py"

# Sequential (engine depends on recognizers and models):
Task: "src/openreview_cli/pii/engine.py"  ← after recognizers
Task: "src/openreview_cli/pii/__init__.py"  ← after engine
```

---

## Implementation Strategy

### MVP First (Phases 1–4: US1 + US2)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (BLOCKS all)
3. Complete Phase 3: User Story 1 — Core PII detection with placeholders
4. Complete Phase 4: User Story 2 — Encrypted mapping persistence
5. **STOP and VALIDATE** — MVP ready: text goes in, stripped text + encrypted mapping + audit come out, never leaves the machine. Privacy gate exists.

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 + US2 → Test independently → **MVP!** (core privacy gate)
3. Add US3 → Test independently (opt-out, threshold)
4. Add US4 → Test independently (error resilience)
5. Each story adds value without breaking previous stories

### Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Verify tests fail before implementing (TDD)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence
