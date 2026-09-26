---

description: "Task list for specs/021-memo-export — Memo Export feature"

---

# Tasks: Memo Export

**Input**: Design documents from `specs/021-memo-export/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/cli-contract.md

**Tests**: Tests are REQUIRED per feature spec. TDD approach — write tests first, verify failure, then implement.

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Maps to user story (US1–US5)
- Exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create memo subpackage structure

- [X] T001 Create `src/openreview_cli/review/memo/` package with `__init__.py` exporting `MemoFormat`, `export_memo()`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data models, filename utilities, and exporter orchestrator shared by ALL user stories.

**⚠️ CRITICAL**: No user story work begins until this phase is complete.

- [X] T002 [P] Write model unit tests in `tests/unit/review/test_memo_models.py` verifying `MemoFormat`, `MemoReport`, `MemoSummary`, `MemoClause`, `MemoCitation`, `MemoTierInfo` dataclass fields and defaults
- [X] T003 Implement `MemoFormat` enum and all memo dataclasses (`MemoReport`, `MemoSummary`, `MemoClause`, `MemoCitation`, `MemoTierInfo`) in `src/openreview_cli/review/memo/models.py`
- [X] T004 [P] Write filename unit tests in `tests/unit/review/test_memo_filename.py` for filename generation (FR-09), dedup suffix, stem sanitization
- [X] T005 Implement filename generation and dedup logic in `src/openreview_cli/review/memo/filename.py`
- [X] T006 [P] Write exporter unit tests in `tests/unit/review/test_memo_exporter.py` for `MemoExporter` construction, `_build_memo_report()` conversion from `ReviewReport`, section assembly, empty-report error
- [X] T007 Implement `MemoExporter` orchestrator class with `_build_memo_report()` and `export()` in `src/openreview_cli/review/memo/exporter.py`

**Checkpoint**: Foundation ready — models, filename utils, and exporter skeleton exist. User story implementation can begin.

---

## Phase 3: User Story 1 — Markdown Export (Priority: P1) 🎯 MVP

**Goal**: User runs review with `--format md` and gets a valid Markdown memo file with all required sections (FR-01, FR-02, FR-03, FR-04, FR-05, FR-07, FR-08).

**Independent Test**: Run review on fixture document with `--format md`. Assert output file exists with `.md` extension. Verify file contains: header with document name/mode/date, summary table, per-clause G/A/R badges (`✅`/`⚠️`/`❌`), confidence bars (`[████████░░] 0.82`), recommendation, disclaimer, playbook version.

### Tests for User Story 1 ⚠️

- [X] T008 [P] [US1] Write Markdown format unit tests in `tests/unit/review/test_memo_formats.py` — verify `render_markdown()` produces header, summary table, per-clause badges, confidence bars, recommendation, disclaimer, playbook version

### Implementation for User Story 1

- [X] T009 [US1] Implement `render_markdown()` in `src/openreview_cli/review/memo/formats.py` using GFM table syntax, emoji badges (`✅`/`⚠️`/`❌`), ASCII confidence bars (reuse `_confidence_bar()` pattern from `report.py`)
- [X] T010 [US1] Wire `--format md` into review subcommands in `src/openreview_cli/app.py` for PreCheck, DealCheck, HireCheck following CLI contract (`contracts/cli-contract.md`)
- [X] T011 [US1] Write Markdown export integration test in `tests/integration/test_memo_export.py` — end-to-end: review runs, `.md` file created, required sections present

**Checkpoint**: US1 fully functional. User can export Markdown memo.

---

## Phase 4: User Story 2 — JSON Export (Priority: P1)

**Goal**: User runs review with `--format json` and gets a valid JSON file with all required memo fields (FR-02, FR-03, FR-07, FR-08).

**Independent Test**: Run review with `--format json`. Parse output with `json.loads()`. Assert keys: `memo_version`, `mode`, `document`, `playbook` (`name` + `version`), `review_date`, `overall` (`recommendation`, `clauses_checked`, `matches`, `differences`), `clauses` (each with `id`, `assessment`, `color`, `confidence`, `citation`), `disclaimer`, `tier_info`.

### Tests for User Story 2 ⚠️

- [X] T012 [P] [US2] Write JSON format unit tests in `tests/unit/review/test_memo_formats.py` — verify `render_json()` produces valid JSON with all required top-level keys and per-clause fields

### Implementation for User Story 2

- [X] T013 [US2] Implement `render_json()` in `src/openreview_cli/review/memo/formats.py` using `json.dumps()` with `MemoReport` → dict conversion via `dataclasses.asdict()`; include `memo_version`, `tier_info`, full clause schema
- [X] T014 [US2] Extend MemoExporter to support JSON format in `src/openreview_cli/review/memo/exporter.py` — wire `MemoFormat.JSON` to `render_json()`

**Checkpoint**: US2 complete. Users can export machine-readable JSON alongside Markdown.

---

## Phase 5: User Story 3 — DOCX Export (Priority: P2)

**Goal**: User runs review with `--format docx` and gets a valid DOCX file openable in Word/LibreOffice with G/A/R cell shading, confidence bars, and disclaimer (FR-02, FR-03, FR-04, FR-05, FR-07).

**Independent Test**: Run review with `--format docx`. Open result with `python-docx`. Assert `doc.tables` non-empty and at least one paragraph contains disclaimer text. Assert Green/Amber/Red cell fill colors applied (RGB 198,239,206 / 255,235,156 / 255,199,206).

### Tests for User Story 3 ⚠️

- [X] T015 [P] [US3] Write DOCX format unit tests in `tests/unit/review/test_memo_formats.py` — verify `render_docx()` returns a `Document` with tables, G/A/R shading, disclaimer paragraph

### Implementation for User Story 3

- [X] T016 [US3] Implement `render_docx()` in `src/openreview_cli/review/memo/formats.py` using `python-docx` — headings, tables, paragraphs, mixed formatting
- [X] T017 [US3] Add DOCX table styling: cell shading for G/A/R (RGB), confidence bar as proportional-width cells, italic disclaimer, horizontal rules between sections

**Checkpoint**: US3 complete. All three format renderers exist. User can export DOCX.

---

## Phase 6: User Story 4 — Custom Output Directory (Priority: P3)

**Goal**: User specifies `--output-dir /path/to/dir` and memo writes to that directory; auto-creates if missing (FR-10, FR-09).

**Independent Test**: Run review with `--format md --output-dir /tmp/test-memos/`. Assert file exists under `/tmp/test-memos/`. Run with non-existent path; assert directory created.

### Tests for User Story 4 ⚠️

- [X] T018 [P] [US4] Write output directory unit tests in `tests/unit/review/test_memo_filename.py` — verify `resolve_output_dir()` creates dir, rejects file-path, falls back to default

### Implementation for User Story 4

- [X] T019 [US4] Implement `--output-dir` flag in `src/openreview_cli/app.py` for PreCheck/DealCheck/HireCheck subcommands per CLI contract
- [X] T020 [US4] Implement directory auto-creation and validation in `src/openreview_cli/review/memo/filename.py`; wire through `MemoExporter`

**Checkpoint**: US4 complete. Users can route memos to any directory.

---

## Phase 7: User Story 5 — Multiple Formats in Single Export (Priority: P3)

**Goal**: User specifies multiple `--format` flags (e.g., `--format md --format json`) and gets one file per unique format with same base filename (FR-11, FR-09 dedup).

**Independent Test**: Run review with `--format md --format json`. Assert both `.md` and `.json` files exist with matching base names. Run with duplicate flags `--format md --format md`; assert only one `.md` file.

### Tests for User Story 5 ⚠️

- [X] T021 [P] [US5] Write multi-format integration tests in `tests/integration/test_memo_export.py` — assert N files for N unique formats, dedup for duplicate flags

### Implementation for User Story 5

- [X] T022 [US5] Implement format deduplication in `src/openreview_cli/review/memo/exporter.py` — deduplicate `MemoFormat` set before writing, handle partial failures (DOCX error doesn't block Markdown)

**Checkpoint**: US5 complete. All user stories functional.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Edge cases, error handling, terminal output, documentation.

- [X] T023 [P] Write edge case tests in `tests/integration/test_memo_edge_cases.py` — empty report, unsupported format, file-exists dedup, truncation, missing citation, duplicate flags
- [X] T024 Implement edge case handling in `src/openreview_cli/review/memo/exporter.py` — truncate clause text ≥ 10k chars, show "Citation: not available" for missing citation, error on empty report
- [X] T025 Add terminal output confirmation messages — "Memo exported to: path/to/file" for single format, bullet list for multiple
- [X] T026 [P] Update `src/openreview_cli/review/__init__.py` and `src/openreview_cli/review/memo/__init__.py` public API exports (`MemoFormat`, `export_memo`, `MemoExporter`)
- [X] T027 Update CLI help text and error exit codes per `contracts/cli-contract.md` — exit codes 1 (no results), 2 (unsupported format), 3 (directory error)
- [X] T028 Run quickstart.md validation scenarios 1–7; fix any issues found
- [X] T029 [P] Full pre-commit sweep: `ruff check`, `ruff-format`, `mypy strict`, `pytest -k memo -v`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **US1 Markdown (Phase 3)**: Depends on Foundational — can start immediately after Phase 2
- **US2 JSON (Phase 4)**: Depends on Foundational — parallel with US1 (different renderers in same file `formats.py`, but independent functions)
- **US3 DOCX (Phase 5)**: Depends on Foundational — parallel with US1/US2 (different section of `formats.py`)
- **US4 Custom Output Dir (Phase 6)**: Depends on Foundational + US5 filename utils — can start after T005
- **US5 Multiple Formats (Phase 7)**: Depends on Foundational (T007 exporter) + at least one renderer
- **Polish (Phase 8)**: Depends on all US phases complete

### User Story Dependencies

- **US1 (P1)**: Can start after Foundational — no dependency on other stories
- **US2 (P1)**: Can start after Foundational — no dependency on other stories
- **US3 (P2)**: Can start after Foundational — no dependency on other stories
- **US4 (P3)**: Depends on filename utils (T005) — can run alongside format renderers
- **US5 (P3)**: Depends on MemoExporter (T007) + at least one renderer

### Within Each User Story

Tests written and FAILING before implementation. Models before services. Story complete before moving to next priority.

---

### Parallel Opportunities

- All Phase 2 [P] tasks in parallel (models, filename, exporter scaffold)
- US1 (Markdown), US2 (JSON), US3 (DOCX) can all start in parallel after Phase 2
- Tests [P] and implementation within a story can run sequentially (TDD order)
- Edge case tests (T023) parallel with implementation (T024)
- Update exports (T026) and help text (T027) in parallel

---

## Parallel Example: Phase 3+4+5

```bash
# Launch all three format renderers in parallel after Phase 2:
Task T009: "Implement render_markdown() in formats.py"
Task T013: "Implement render_json() in formats.py"
Task T016: "Implement render_docx() in formats.py"
```

```bash
# Launch tests for all formats in parallel:
Task T008: "Markdown format unit tests"
Task T012: "JSON format unit tests"
Task T015: "DOCX format unit tests"
```

---

## Implementation Strategy

### MVP First (US1 Only)

1. Complete Phase 1: Setup → T001
2. Complete Phase 2: Foundational → T002–T007
3. Complete Phase 3: US1 (Markdown) → T008–T011
4. **STOP and VALIDATE**: Run Markdown export end-to-end on fixture document
5. Deploy/demo ready with Markdown output

### Incremental Delivery

1. Phase 1 + Phase 2 → Foundation ready
2. Phase 3 (US1 Markdown) → MVP: single-format export
3. Phase 4 (US2 JSON) → machine-readable export
4. Phase 5 (US3 DOCX) → Word document export
5. Phase 6 (US4) + Phase 7 (US5) → directory control + multi-format
6. Phase 8 → Edge cases, polish, pre-commit sweep

### Parallel Format Strategy

Single developer: implement renderers sequentially (Markdown → JSON → DOCX).
Multiple developers: all three renderers in parallel after Phase 2.

---

## Notes

- [P] tasks = different files, no cross-dependencies
- All tasks include exact file paths for LLM-executable specificity
- Commit after each task or logical group
- Stop at any checkpoint to validate independently
- Avoid: vague tasks, same-file conflicts, cross-story dependencies
