# Tasks: Prompt Management

**Input**: Design documents from `/specs/009-prompt-management/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/cli.md, quickstart.md

**Tests**: TDD approach — tests written BEFORE implementation for every task.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Module skeleton, migration, and test fixtures

- [X] T001 Create `src/openreview_cli/prompts/` module directory with `__init__.py` exposing public API (PromptStore, PromptVersion, PromptBinding)
- [X] T002 [P] Create SQLite migration `src/openreview_cli/storage/migrations/004_prompts.sql` — `prompt_versions` table (composite PK: name, version; CHECK content <= 16384), `prompt_bindings` table (PK: slot, FK to prompt_versions), index on name, PRAGMA user_version = 4
- [X] T003 [P] Create test fixture YAML files: `tests/fixtures/prompts/extract-clauses.yaml` and `tests/fixtures/prompts/qa-answer.yaml` with sample prompt content matching the export format from research.md R-8

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data models that all user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Create Pydantic models in `src/openreview_cli/prompts/models.py` — `PromptVersion` (name: str, version: int, content: str with max_length=16384, created_at: str, tags: list[str] | None, description: str | None, test_results: list[dict] | None, optimization_meta: dict | None), `PromptBinding` (slot: str, prompt_name: str, prompt_version: int, created_at: str), `Prompt` (name: str, latest_version: int, created_at: str)
- [X] T005 Write unit tests for Pydantic models in `tests/unit/test_prompt_models.py` — validate 16 KB content limit, composite key uniqueness, optional fields default to None, created_at ISO 8601 format

**Checkpoint**: Foundation ready — models validated, migration file ready, user story implementation can now begin

---

## Phase 3: User Story 1 — Versioned Prompt Storage (Priority: P1) 🎯 MVP

**Goal**: Developer can create, version, list, show, diff, and delete prompts via CLI

**Independent Test**: `openreview prompt create --name test --content "test"` → `openreview prompt list` shows it → `openreview prompt update test --content "v2"` → `openreview prompt show test --version 1` shows original → `openreview prompt diff test --from 1 --to 2` shows change

### Tests for User Story 1 (TDD — write FIRST, ensure they FAIL)

- [X] T006 [P] [US1] Write unit tests for PromptStore CRUD in `tests/unit/test_prompt_store.py` — test create (version 1), update (auto-increment), get (specific version), get_latest, list (pagination), delete (all versions), content >16 KB rejection, duplicate name handling
- [X] T007 [P] [US1] Write unit tests for prompt CLI commands in `tests/unit/test_prompt_cli.py` — test create/update/list/show/delete/diff subcommands with Typer CliRunner, verify exit codes and output format
- [X] T008 [US1] Write integration test for prompt lifecycle in `tests/integration/test_prompt_lifecycle.py` — end-to-end: create → update → list → show → diff → delete, verify all versions accessible, verify deletion removes all versions

### Implementation for User Story 1

- [X] T009 [US1] Implement PromptStore class in `src/openreview_cli/prompts/store.py` — methods: `create(name, content, metadata)`, `update(name, content, metadata)`, `get(name, version)`, `get_latest(name)`, `list(page, per_page)`, `delete(name)`. Use SQLite with PRAGMA foreign_keys = ON. Auto-increment version via `SELECT MAX(version) + 1 FROM prompt_versions WHERE name = ?`. Raise ValueError if content > 16384 bytes.
- [X] T010 [US1] Implement CLI subcommands in `src/openreview_cli/prompts/cli.py` — `create` (--name, --content, --tags, --description), `update` (NAME positional, --content, --tags, --description), `list` (--page, --per-page, Rich table output), `show` (NAME positional, --version), `delete` (NAME positional, --force), `diff` (NAME positional, --from, --to, use difflib.unified_diff with Rich rendering). Exit codes per contracts/cli.md.
- [X] T011 [US1] Register prompt subcommand tree in `src/openreview_cli/app.py` — import from prompts.cli, call `app.add_typer(prompt_app, name="prompt")` following existing pattern

**Checkpoint**: User Story 1 fully functional — developer can manage prompt versions via CLI

---

## Phase 4: User Story 2 — Prompt-to-Model Binding (Priority: P1)

**Goal**: Developer can bind a prompt version to a gateway model slot, gateway uses it at runtime

**Independent Test**: `openreview prompt bind --slot extraction --prompt test --version 1` → `openreview prompt bindings` shows it → gateway.resolve("extraction") returns bound prompt content → `openreview prompt unbind --slot extraction` → gateway falls back to default

### Tests for User Story 2 (TDD — write FIRST, ensure they FAIL)

- [X] T012 [P] [US2] Write unit tests for PromptStore binding methods in `tests/unit/test_prompt_store.py` (extend) — test bind (valid slot, valid version), bind (invalid slot), bind (non-existent version), unbind (existing binding), unbind (no binding), bindings() list, resolve() with/without binding
- [X] T013 [P] [US2] Write integration test for gateway-prompt integration in `tests/integration/test_prompt_gateway.py` — mock gateway.chat(), verify resolved prompt content appears in messages array, verify fallback to default when no binding exists

### Implementation for User Story 2

- [X] T014 [US2] Implement PromptStore binding methods in `src/openreview_cli/prompts/store.py` (extend) — methods: `bind(slot, name, version)`, `unbind(slot)`, `bindings()`, `resolve(slot_name)`. Validate slot against VALID_SLOTS (from gateway.router). resolve() checks binding first, falls back to default prompt from defaults loader.
- [X] T015 [US2] Implement CLI binding subcommands in `src/openreview_cli/prompts/cli.py` (extend) — `bind` (--slot, --prompt, --version), `unbind` (--slot), `bindings` (Rich table: slot → prompt_name:version). Exit codes per contracts/cli.md.
- [X] T016 [US2] Modify `src/openreview_cli/gateway/router.py` — in `chat()`, `embed()`, `rerank()` methods, call `PromptStore.resolve(slot_name)` before building messages array. Prepend resolved prompt content as system message. Import PromptStore from prompts.store. Handle empty string return (no system message).

**Checkpoint**: User Story 2 fully functional — prompts are operational, gateway uses bound prompts

---

## Phase 5: User Story 3 — Prompt A/B Testing & Export/Import (Priority: P2)

**Goal**: Developer can run A/B test on prompt versions, export/import prompts as YAML

**Independent Test**: `openreview prompt test --prompt test --versions 1,2` → shows error requiring benchmark harness → `openreview prompt export test --output /tmp/test.yaml` → `openreview prompt import /tmp/test.yaml` → re-creates prompt

**Note**: Benchmark harness (roadmap N-3) does not exist yet. US3 defines integration contract but shows "requires benchmark" error.

### Tests for User Story 3 (TDD — write FIRST, ensure they FAIL)

- [X] T017 [P] [US3] Write unit tests for YAML export/import in `tests/unit/test_prompt_store.py` (extend) — test export (single, all), import (preserves versions, no overwrite), invalid YAML handling
- [X] T018 [P] [US3] Write unit tests for history and test commands in `tests/unit/test_prompt_cli.py` (extend) — test history (shows versions with metadata), test command (requires benchmark, shows error if not configured)

### Implementation for User Story 3

- [X] T019 [US3] Implement PromptStore export/import in `src/openreview_cli/prompts/store.py` (extend) — `export(name=None)` returns YAML-serializable dict, `import_prompt(data)` creates entries preserving version numbers. Per research.md R-8 format. Cannot overwrite existing prompts.
- [X] T020 [US3] Implement CLI export/import/history/test in `src/openreview_cli/prompts/cli.py` (extend) — `export` ([NAME], --output), `import` (PATH positional), `history` (NAME positional, Rich table), `test` (--prompt, --versions, --benchmark). test shows informative error if benchmark not configured.

**Checkpoint**: User Story 3 fully functional — A/B testing contract defined, export/import works

---

## Phase 6: User Story 4 — GRPO Optimization & Default Prompts (Priority: P3)

**Goal**: Developer can run GRPO optimization, default prompts ship with package, variables resolve at runtime

**Independent Test**: `openreview prompt optimize --prompt test --iterations 3` → shows error requiring benchmark harness → default prompts load on first use → `{key}` variables resolve in prompt content

**Note**: Benchmark harness (roadmap N-3) does not exist yet. GRPO shows "requires benchmark" error.

### Tests for User Story 4 (TDD — write FIRST, ensure they FAIL)

- [X] T021 [P] [US4] Write unit tests for default prompt loader in `tests/unit/test_prompt_defaults.py` — test YAML loading from `prompts/defaults/`, first-use loading, import cannot overwrite defaults
- [X] T022 [P] [US4] Write unit tests for variable substitution in `tests/unit/test_prompt_variables.py` — test {key} replacement, unknown variable warning, per-slot variable sets
- [X] T023 [US4] Write memory budget test in `tests/integration/test_prompt_memory.py` — use memory_tracker fixture, run all prompt commands, assert peak < 110 MB

### Implementation for User Story 4

- [X] T024 [US4] Implement default prompt loader in `src/openreview_cli/prompts/defaults.py` — load YAML from `src/openreview_cli/prompts/defaults/`, insert on first use (check if store empty). Create default prompts for all 5 slots: extraction, reasoning, embedding, reranking, graph.
- [X] T025 [US4] Implement variable substitution in `src/openreview_cli/prompts/variables.py` — `substitute(content, slot, variables)` using `str.format_map()` with defaultdict. Log warning for unknown variables. Per-slot variable sets per contracts/cli.md.
- [X] T026 [US4] Implement GRPO optimize CLI command in `src/openreview_cli/prompts/cli.py` (extend) — `optimize` (--prompt, --benchmark, --iterations). Check for benchmark harness, show error if not configured. Define integration contract.
- [X] T027 [US4] Integrate variable substitution into gateway in `src/openreview_cli/gateway/router.py` (extend) — after PromptStore.resolve(), call variables.substitute() with slot-specific variables before prepending system message.

**Checkpoint**: All user stories fully functional — GRPO contract defined (requires benchmark harness), defaults load, variables resolve

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Validation, documentation, final checks

- [X] T028 [P] Run quickstart.md validation scenarios 1-7, verify all pass
- [X] T029 Run full prompt test suite (`uv run pytest tests/ -k prompt -v`), lint (`uv run ruff check .`), format check (`uv run ruff format --check`), type check (`uv run mypy src/ tests/`). Fix any failures.
- [X] T030 Update `src/openreview_cli/prompts/__init__.py` to export all public classes with docstrings

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational — MVP, no dependencies on other stories
- **User Story 2 (Phase 4)**: Depends on User Story 1 (needs PromptStore CRUD)
- **User Story 3 (Phase 5)**: Depends on User Story 1 + 2 (needs PromptStore + resolve)
- **User Story 4 (Phase 6)**: Depends on User Story 1 + 3 (needs PromptStore + test command)
- **Polish (Phase 7)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 (P1)**: Can start after Foundational — no dependencies on other stories
- **US2 (P1)**: Depends on US1 (PromptStore CRUD) — independently testable after US1
- **US3 (P2)**: Depends on US1 + US2 (needs resolve for A/B testing)
- **US4 (P3)**: Depends on US1 + US3 (needs test command for GRPO)

### Within Each User Story

- Tests (TDD) MUST be written and FAIL before implementation
- Models before services (store)
- Services (store) before CLI
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- T002 and T003 (Phase 1) can run in parallel (different files)
- T004 and T005 (Phase 2) can run in parallel (different files)
- T006 and T007 (Phase 3 tests) can run in parallel (different files)
- T012 and T013 (Phase 4 tests) can run in parallel (different files)
- T017 and T018 (Phase 5 tests) can run in parallel (different files)
- T021 and T022 (Phase 6 tests) can run in parallel (different files)
- T028 and T030 (Phase 7) can run in parallel

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T003)
2. Complete Phase 2: Foundational (T004-T005)
3. Complete Phase 3: User Story 1 (T006-T011)
4. **STOP and VALIDATE**: Run quickstart Scenario 1 (Basic Lifecycle)
5. If green, proceed to User Story 2

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. US1 → Test independently → MVP! (developer can manage prompts)
3. US2 → Test independently → Prompts are operational (gateway uses them)
4. US3 → Test independently → A/B testing contract defined, export/import works
5. US4 → Test independently → GRPO optimization, default prompts, variables
6. Each story adds value without breaking previous stories

### TDD Workflow

For every task:
1. **Write failing test** — define expected behavior
2. **Run test** — verify it fails (red)
3. **Write minimal code** — make test pass (green)
4. **Refactor** — improve without breaking tests
5. **Commit** — conventional commit message

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- TDD: tests written BEFORE implementation for every task
- Benchmark harness (roadmap N-3) does not exist — US3 and US4 define integration contracts but show "requires benchmark" errors
- All file paths verified against task-context.md (0 MISMATCHES)
- 20 NEW files, 2 MODIFIED files (app.py, gateway/router.py)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently

---

## Phase 8: Convergence

**Purpose**: Resolve remaining lint issues to satisfy the constitution's pre-commit gate (ruff check MUST pass).

- [X] T031 Fix 3 remaining ruff lint errors in `src/openreview_cli/gateway/router.py` (RUF005: iterable unpacking) and `src/openreview_cli/prompts/store.py` (TC003: `builtins` import in type-checking block). Verified: `ruff check .` — 0 errors, `ruff format --check` — clean, `mypy src/ tests/` — clean, `pytest tests/ -k prompt` — 102/102 pass.
