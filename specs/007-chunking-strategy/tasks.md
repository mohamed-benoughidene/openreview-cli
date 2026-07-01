---

description: "Task list for chunking strategy feature implementation"

---

# Tasks: Chunking Strategy

**Input**: Design documents from `/specs/007-chunking-strategy/`

**Prerequisites**: plan.md, spec.md, data-model.md, contracts/chunking-api.md

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

Single project — `src/`, `tests/` at repository root.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create chunking module skeleton

- [X] T001 Create `src/openreview_cli/chunking/` module with `__init__.py` exporting `stream_chunks`, `Chunk`, `ChunkConfig`
- [X] T002 [P] Create test files: `tests/unit/test_chunking_models.py`, `tests/unit/test_chunking_tokenizer.py`, `tests/unit/test_chunking_splitter.py`, `tests/unit/test_chunking_stream.py`, `tests/integration/test_chunking_cli.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Data models and tokenizer — blocks all user stories

- [X] T003 Implement `Chunk` dataclass in `src/openreview_cli/chunking/models.py` — fields: id, text, token_count, source_clause_id, source_clause_title, source_clause_level, chunk_index_within_clause, char_offset_start, char_offset_end, parent_chunk_id, structural_location. Use `@dataclass(slots=True)`. Add validation in `__post_init__`.
- [X] T004 [P] Implement `ChunkConfig` dataclass in `src/openreview_cli/chunking/models.py` — fields: chunk_size (default 512), chunk_overlap (default 50), group_short_clauses (default True), respect_clause_boundaries (default True). Validation: overlap < chunk_size.
- [X] T005 [P] Implement `count_tokens(text) -> int` in `src/openreview_cli/chunking/tokenizer.py` — whitespace + punctuation splitter.
- [X] T006 [P] Implement `split_tokens(text, start, end) -> list[tuple[str, int, int]]` in `src/openreview_cli/chunking/tokenizer.py` — split text into token ranges for overlap calculation.

**Checkpoint**: Foundation ready — all models and tokenizer can be tested independently.

---

## Phase 3: User Story 1 - Chunk a Parsed Contract (Priority: P1) MVP

**Goal**: Core RCTS chunking with clause-boundary awareness, metadata preservation, empty clause skipping, config validation, and memory-budgeted streaming.

**Independent Test**: `stream_chunks(clauses)` yields `Chunk` objects with correct `source_clause_id`, metadata, no cross-clause spanning, and <10 MB peak memory.

- [X] T007 [US1] Implement `split_clause(clause, config) -> Iterator[Chunk]` in `src/openreview_cli/chunking/splitter.py` — RCTS algorithm with clause-boundary awareness. Try paragraph boundaries first, then sentence, then word. Preserve clause metadata in all sub-chunks.
- [X] T008 [US1] Implement `group_short_clauses(clauses, config) -> list[list[Clause]]` in `src/openreview_cli/chunking/splitter.py` — merge consecutive short clauses from same article when combined size < chunk_size.
- [X] T009 [US1] Implement `stream_chunks(clauses, config) -> Iterator[Chunk]` in `src/openreview_cli/chunking/stream.py` — core generator. Skip empty clauses (FR-016), validate config (FR-014), yield chunks one at a time (FR-009).

**Checkpoint**: US1 fully functional — core chunking works, all metadata preserved.

---

## Phase 4: User Story 2 - Clause-Boundary-Aware Chunking (Priority: P1)

**Goal**: Hierarchical chunking with parent_chunk_id references and structural_location metadata.

**Independent Test**: Nested clauses (Article I → Section 1.1 → Sub-section (a)) produce chunks with correct parent_chunk_id chain.

- [X] T010 [US2] Add `assign_parent_chunk_ids(chunks, clauses_by_id) -> None` in `src/openreview_cli/chunking/splitter.py` — set parent_chunk_id based on clause hierarchy (level, parent_id from Clause model).
- [X] T011 [US2] Add `build_structural_location(chunk, clause, clauses_by_id) -> str` in `src/openreview_cli/chunking/splitter.py` — e.g., "Article_II/Section_2.1/Subsection_(a)".
- [X] T012 [US2] Integrate hierarchy into `stream_chunks()` in `src/openreview_cli/chunking/stream.py` — call assign_parent_chunk_ids and build_structural_location.

**Checkpoint**: Hierarchical chunking works — parent references reconstruct full document structure.

---

## Phase 5: User Story 4 - Chunking After PII Stripping (Priority: P1)

**Goal**: PII placeholders preserved in chunks during chunking.

**Independent Test**: Chunk text contains [PARTY_1], [DATE_1] etc., not raw PII. PII mapping is not modified or exposed.

- [X] T013 [US4] Add PII placeholder test in `tests/unit/test_chunking_stream.py` — verify chunks from PII-stripped clauses contain placeholders, not raw PII.
- [X] T014 [US4] Add integration test in `tests/integration/test_chunking_cli.py` — strip PII then chunk, verify no raw PII in output. (Delivered by spec 008 bridge — `test_pii_safe_chunking` passes)

**Checkpoint**: PII safety verified — chunks contain placeholders only.

---

## Phase 6: User Story 3 - Configurable Chunk Size (Priority: P2)

**Goal**: config.yml overrides for chunk_size, chunk_overlap, per-mode configuration.

**Independent Test**: Different config.yml values produce different chunk sizes.

- [X] T015 [US3] Add `load_chunk_config(mode: str | None) -> ChunkConfig` in `src/openreview_cli/chunking/stream.py` — read from config.yml with per-mode overrides (e.g., precheck.chunk_size).

**Checkpoint**: Config-driven chunking works — no hardcoded sizes.

---

## Phase 7: User Story 5 - Chunk Command with Output Options (Priority: P3)

**Goal**: CLI command with --format text/json and --summary, plus progress indicator.

**Independent Test**: `openreview chunk contract.json --format json` outputs valid JSON array.

- [X] T016 [US5] Add `chunk` command in `src/openreview_cli/app.py` — follows parse command pattern. Accepts path, --format (text/json), --summary. Validates config (exit 2 on invalid), handles errors (exit 1).
- [X] T016a [US5] Add `try/except KeyboardInterrupt` in chunk command in `src/openreview_cli/app.py` — exit cleanly with message "Chunking interrupted" (exit code 130).
- [X] T017 [P] [US5] Add `format_chunks_text(chunks) -> str` in `src/openreview_cli/chunking/stream.py` — human-readable output: "Chunk N: [source_clause_title] (N tokens)".
- [X] T018 [P] [US5] Add `format_chunks_json(chunks) -> str` in `src/openreview_cli/chunking/stream.py` — flat JSON array of chunk objects.
- [X] T019 [P] [US5] Add `format_chunks_summary(clause_count, chunk_count, duration) -> str` in `src/openreview_cli/chunking/stream.py`.
- [X] T020 [US5] Add progress indicator in `src/openreview_cli/chunking/stream.py` — "Chunking clause N of M" via Rich.
- [X] T020a [US5] Add progress indicator test in `tests/integration/test_chunking_cli.py` — verify output contains "Chunking clause N of M" pattern.

**Checkpoint**: CLI usable end-to-end — parse, chunk, inspect results.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Edge cases, table handling, linting, full test pass.

- [X] T021 [P] Add table flattening in `src/openreview_cli/chunking/splitter.py` — detect table-like patterns (3+ consecutive lines with aligned columns separated by 2+ spaces), flatten rows to inline text (FR-021).
- [X] T021a [P] Add table flattening test in `tests/unit/test_chunking_splitter.py` — verify table rows are flattened to inline text with correct column alignment.
- [X] T022 [P] Add edge case tests in `tests/unit/test_chunking_splitter.py` — flat text with no structure, oversized paragraphs, empty clauses, very short clauses (grouping), Ctrl+C handling.
- [X] T023 Run `uv run pytest -k "chunking" -v` — all tests green.
- [X] T024 Run `uv run ruff check . && uv run ruff format --check . && uv run mypy src/ tests/` — lint + types clean.
- [X] T025 Run quickstart.md validation scenarios — chunk --help verified.
- [X] T026 [P] Add performance benchmark in `tests/integration/test_chunking_performance.py` — chunk a 50-page contract and assert duration <2s (SC-001). Generate 50-page fixture if not present.
- [X] T027 [P] Add memory measurement test in `tests/integration/test_chunking_memory.py` — measure peak memory with tracemalloc during chunking of 50-page contract and assert <10 MB (SC-005).

**Checkpoint**: Feature complete — all tests, lint, types pass.

---

## Phase 9: Convergence

**Purpose**: Close gaps between the spec contract and the implementation

- [X] T028 Refactor `stream_chunks` to yield chunks without accumulating `all_chunks` list per FR-009 (`contradicts` — stream.py:54 accumulates `all_chunks: list[Chunk]` before `yield from`, spec requires "never accumulated in memory")
- [X] T029 Add chunk-size accuracy test validating 90% of chunks are within ±10% of target chunk size per SC-007 (`partial`)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2
- **US2 (Phase 4)**: Depends on US1 (builds on stream_chunks)
- **US4 (Phase 5)**: Depends on US1 (stream_chunks must exist)
- **US3 (Phase 6)**: Depends on US1 (stream_chunks must exist)
- **US5 (Phase 7)**: Depends on US1 (stream_chunks must exist)
- **Polish (Phase 8)**: Depends on all user stories

### User Story Dependencies

- **US1 (P1)**: Can start after Phase 2 — No dependencies on other stories
- **US2 (P1)**: Depends on US1 stream_chunks
- **US4 (P1)**: Depends on US1 stream_chunks
- **US3 (P2)**: Depends on US1 stream_chunks
- **US5 (P3)**: Depends on US1 stream_chunks

### Parallel Opportunities

- T002/T003/T004/T005/T006 can all run in parallel (different files, no dependencies)
- T017/T018/T019 can run in parallel
- T021/T022 can run in parallel
- US2, US4, US3, US5 can be worked on in parallel once US1 is complete

---

## Implementation Strategy

### MVP First (US1 Only)

1. Complete Phase 1: Setup (T001-T002)
2. Complete Phase 2: Foundational (T003-T006)
3. Complete US1 (T007-T009)
4. **STOP and VALIDATE**: Test chunking with a parsed contract

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 → Chunking works with clause boundaries, metadata, memory budget
3. Add US2 → Hierarchical chunking with parent references
4. Add US4 → PII-safe chunking verified
5. Add US3 → Config-driven output
6. Add US5 → CLI command with format options

---

## Notes

- [P] tasks = different files, no dependencies — can be parallelized
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Commit after each task or logical group
- Total: 30 tasks (5 setup/foundational, 3 US1, 3 US2, 2 US4, 1 US3, 7 US5, 9 polish)
