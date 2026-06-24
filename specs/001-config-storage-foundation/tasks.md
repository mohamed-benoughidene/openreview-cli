---

description: "Task list for Config + Storage Foundation implementation"
---

# Tasks: Config + Storage Foundation

**Input**: Design documents from `/specs/001-config-storage-foundation/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: TDD approach — tests written FIRST (FAIL), then implementation (PASS).

**Organization**: Tasks grouped by user story. Tests written before implementation for every story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- This is a single-project CLI tool using `src/` layout
- Source: `src/openreview_cli/`
- Tests: `tests/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T001 Add PyYAML and platformdirs dependencies via `uv add PyYAML platformdirs`
- [X] T002 [P] Create config/ package with `__init__.py` at `src/openreview_cli/config/__init__.py`
- [X] T003 [P] Create storage/ package with `__init__.py` at `src/openreview_cli/storage/__init__.py`
- [X] T004 [P] Create test fixtures directory at `tests/fixtures/` with `valid_config.yml` and `invalid_config.yml`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T005 [P] Implement platform-aware path resolution in `src/openreview_cli/config/paths.py` using `platformdirs.user_config_dir()`, `user_log_dir()`, and `user_data_dir()` — import platformdirs **inside function calls** (lazy import, not at module level) per constitution Principle III
- [X] T006 [P] Implement stdlib logging setup in `src/openreview_cli/logging_config.py` with `FileHandler` (to log file) and `StreamHandler` (to stderr), default INFO, DEBUG via argument
- [X] T007 Implement SQLite connection manager in `src/openreview_cli/storage/database.py` with WAL mode, foreign keys, and context manager for transactions
- [X] T008 Implement migration runner in `src/openreview_cli/storage/database.py` that checks `schema_version` table and applies pending `.sql` migrations in order. On migration failure, rollback and refuse to run — app exits with code 5
- [X] T009 Create initial migration `src/openreview_cli/storage/migrations/001_initial.sql` with all Phase 1 tables (schema_version, clients, reviews, review_diffs, cost_logs) per `contracts/sqlite-schema.sql`
- [X] T010 Define Pydantic config models in `src/openreview_cli/config/loader.py` using `pydantic.BaseModel` for each config section (privacy, gateway, storage) — import pydantic **inside function calls** (lazy import, not at module level) per constitution Principle III
- [X] T011 Define default config values in `src/openreview_cli/config/defaults.py` matching the defaults table from Configuration.md
- [X] T012 [P] Implement shared error formatting module in `src/openreview_cli/errors.py` with exit codes 5 (config errors) and 6 (cost limit errors), providing clear messages (field name, problem, valid options, fix suggestion)

**Checkpoint**: Foundation ready — user story implementation can now begin with TDD

---

## Phase 3: User Story 1 - First-Time Setup (Priority: P1) 🎯 MVP

**Goal**: A lawyer can run `openreview --version` on a fresh install and config files + DB are auto-created.

**Independent Test**: `openreview --version` on a fresh install creates `config.yml`, `auth.json`, and `openreview.db` with correct defaults.

### Tests for User Story 1 (Write FIRST — must FAIL)

- [X] T013 [P] [US1] Write test for config.yml creation with defaults on first run in `tests/unit/test_config_loader.py` — expects file exists at `platformdirs.user_config_dir("openreview") / "config.yml"`
- [X] T014 [P] [US1] Write test for auth.json creation with chmod 600 on Unix and empty content in `tests/unit/test_auth.py` — expects file permissions are 0o600
- [X] T015 [P] [US1] Write test for auth.json permission warning on insecure permissions (Unix) in `tests/unit/test_auth.py` — expects warning message for 0o644

### Implementation for User Story 1 (PASS the tests)

- [X] T016 [US1] Implement config.yml creation with defaults in `src/openreview_cli/config/loader.py` — on first run, `yaml.safe_dump(default_config, f, default_flow_style=False)`
- [X] T017 [US1] Implement auth.json creation (empty JSON) with chmod 600 on Unix in `src/openreview_cli/config/auth.py` — create if missing, set permissions via `os.chmod(path, 0o600)`
- [X] T018 [US1] Implement auth.json permission check (Unix warning, Windows warning) in `src/openreview_cli/config/auth.py` — check `path.stat().st_mode` on Unix, warning only on Windows
- [X] T019 [US1] Wire config/auth loading and DB initialization into app startup in `src/openreview_cli/app.py` — call `load_config()`, `ensure_auth()`, `init_database()` at startup, with logging calls for each operational event (`logger.info("config loaded")`, `logger.info("database initialized")`, etc.)
- [X] T020 [US1] Add performance test for DB initialization latency (<2s) in `tests/unit/test_database.py` using `time.perf_counter()` — asserts SC-007

**Checkpoint**: At this point, `openreview --version` creates config files and DB. **MVP delivered!**

---

## Phase 4: User Story 2 - View and Modify Configuration (Priority: P1)

**Goal**: A lawyer can view and change configuration via CLI commands without editing YAML by hand.

**Independent Test**: `openreview config show` displays merged config, `openreview config get privacy.tier` returns a value, `openreview config set privacy.tier maximum` updates the file.

### Tests for User Story 2 (Write FIRST — must FAIL)

- [X] T021 [P] [US2] Write test for `config show` command output in `tests/unit/test_cli_config.py` — expects Rich-rendered table with all config values
- [X] T022 [P] [US2] Write test for `config get <key>` command in `tests/unit/test_cli_config.py` — expects single value output for dot-notation key
- [X] T023 [P] [US2] Write test for `config set <key> <value>` command in `tests/unit/test_cli_config.py` — expects file updated and success message
- [X] T024 [P] [US2] Write test for config.yml backup creation before set in `tests/unit/test_config_loader.py` — expects `config.yml.bak` exists after set
- [X] T025 [P] [US2] Write test for config validation on invalid set value in `tests/unit/test_config_loader.py` — expects error for `config set privacy.tier invalid`

### Implementation for User Story 2 (PASS the tests)

- [X] T026 [US2] Implement `config show` command in `src/openreview_cli/app.py` — Typer command that loads merged config and renders via Rich
- [X] T027 [US2] Implement `config get <key>` command in `src/openreview_cli/app.py` — Typer command with `key: str` argument, dot-notation lookup
- [X] T028 [US2] Implement `config set <key> <value>` command in `src/openreview_cli/app.py` — Typer command with `key: str` and `value: str` arguments
- [X] T029 [US2] Implement config.yml backup before set in `src/openreview_cli/config/loader.py` — copy `config.yml` to `config.yml.bak` before writing
- [X] T030 [US2] Implement config validation on set in `src/openreview_cli/config/loader.py` — validate against Pydantic model, reject invalid values with error message using error module from T012
- [X] T031 [US2] Add performance test for config operation latency (<500ms) in `tests/unit/test_cli_config.py` using `time.perf_counter()` — asserts SC-006

**Checkpoint**: `openreview config show/get/set` all work correctly.

---

## Phase 5: User Story 3 - Environment Variable Overrides (Priority: P2)

**Goal**: A lawyer can temporarily override config via env vars without editing files.

**Independent Test**: Set `OPENREVIEW_PRIVACY_TIER=maximum`, run `openreview config show` — displays `maximum` even if file says `balanced`.

### Tests for User Story 3 (Write FIRST — must FAIL)

- [ ] T032 [P] [US3] Write test for OPENREVIEW_* env var override in `tests/unit/test_config_loader.py` — expects `OPENREVIEW_PRIVACY_TIER=maximum` overrides file value
- [ ] T033 [P] [US3] Write test for provider API key env var override in `tests/unit/test_auth.py` — expects `OPENAI_API_KEY` overrides `auth.json` value
- [ ] T034 [P] [US3] Write test for config resolution priority hierarchy in `tests/unit/test_config_loader.py` — expects env var > config.yml > built-in defaults, missing keys fall through to next level

### Implementation for User Story 3 (PASS the tests)

- [ ] T035 [US3] Implement env var override logic for OPENREVIEW_* in `src/openreview_cli/config/loader.py` — scan `os.environ` for `OPENREVIEW_*` keys, apply after loading YAML
- [ ] T036 [US3] Implement env var override for provider API keys in `src/openreview_cli/config/auth.py` — check `os.environ` for each provider key (OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.)
- [ ] T037 [US3] Integrate env var merging into config resolution in `src/openreview_cli/config/loader.py` — merge env vars into loaded config using priority: CLI > args > env > file > defaults, missing values fall through to next level

**Checkpoint**: `openreview config show` respects OPENREVIEW_* env vars over file values.

---

## Phase 6: User Story 4 - Cost Tracking (Priority: P2)

**Goal**: The system logs API call costs and enforces daily/per-review limits.

**Independent Test**: Insert a cost log, verify daily limit rejects when exceeded, verify per-review limit rejects when exceeded.

### Tests for User Story 4 (Write FIRST — must FAIL)

- [ ] T038 [P] [US4] Write test for cost log insertion in `tests/unit/test_database.py` — expects row inserted into `cost_logs` table with correct values
- [ ] T039 [P] [US4] Write test for daily cost limit in `tests/unit/test_database.py` — expects `check_daily_limit(1000)` returns False when today's total >= limit
- [ ] T040 [P] [US4] Write test for per-review cost limit in `tests/unit/test_database.py` — expects `check_review_limit("review_id", 100)` returns False when review total >= limit

### Implementation for User Story 4 (PASS the tests)

- [ ] T041 [US4] Implement cost log insertion in `src/openreview_cli/storage/database.py` — function `log_cost(review_id, model, provider, prompt_tokens, completion_tokens, cost_cents)` inserts into `cost_logs`
- [ ] T042 [US4] Implement daily cost limit check in `src/openreview_cli/storage/database.py` — function `check_daily_limit(max_cents)` sums today's `cost_logs`, compares to limit, exit code 6 on breach
- [ ] T043 [US4] Implement per-review cost limit check in `src/openreview_cli/storage/database.py` — function `check_review_limit(review_id, max_cents)` sums review's cost_logs, compares to limit, exit code 6 on breach
- [ ] T044 [US4] Add performance test for cost log insertion latency (<100ms) in `tests/unit/test_database.py` using `time.perf_counter()` — asserts SC-004

**Checkpoint**: Cost tracking and limit enforcement work. Exit code 6 on limit breach.

---

## Phase 7: User Story 5 - Client Management (Priority: P3)

**Goal**: A lawyer can manage their client list via CLI commands.

**Independent Test**: `openreview client add acme "Acme Corp"` creates a client, `openreview client list` shows it, `openreview client delete acme` removes it.

### Tests for User Story 5 (Write FIRST — must FAIL)

- [ ] T045 [P] [US5] Write test for `client add` command in `tests/unit/test_cli_client.py` — expects client row inserted into `clients` table
- [ ] T046 [P] [US5] Write test for `client list` command in `tests/unit/test_cli_client.py` — expects formatted output with client id, name, dates
- [ ] T047 [P] [US5] Write test for `client delete` command (no reviews) in `tests/unit/test_cli_client.py` — expects client row deleted
- [ ] T048 [P] [US5] Write test for `client delete` with reviews (requires --force) in `tests/unit/test_cli_client.py` — expects error without --force, success with --force

### Implementation for User Story 5 (PASS the tests)

- [ ] T049 [US5] Implement `client add` command in `src/openreview_cli/app.py` — Typer command with `id: str` and `name: str` arguments, inserts into DB
- [ ] T050 [US5] Implement `client list` command in `src/openreview_cli/app.py` — Typer command that queries `clients` table and renders via Rich
- [ ] T051 [US5] Implement `client delete` command in `src/openreview_cli/app.py` — Typer command with `id: str` argument, checks for reviews, deletes row
- [ ] T052 [US5] Implement `--force` flag for client delete in `src/openreview_cli/app.py` — Typer `force: bool = typer.Option(False, "--force")`, bypasses review check

**Checkpoint**: Client CRUD works. `--force` deletes client + all associated reviews.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T053 Run quickstart.md validation scenarios end-to-end
- [ ] T054 [P] Verify memory budget with `pytest -m memory` — peak < 110 MB
- [ ] T055 [P] Add warm startup time measurement in `tests/unit/test_app.py` using `time.perf_counter()` — `openreview --version` on already-configured system must be <0.3s (constitution constraint)
- [ ] T056 [P] Update AGENTS.md SPECKIT markers with implementation notes

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **User Stories (Phase 3-7)**: All depend on Foundational completion
  - Each user story is independent (different business logic)
  - They must be done in priority order (P1 → P2 → P3) with the single-implementer model
- **Polish (Phase 8)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 (First-Time Setup)**: Depends on Foundational — No dependencies on other stories
- **US2 (Config View/Modify)**: Depends on Foundational + US1 — Reads config.yml (created by US1)
- **US3 (Env Var Overrides)**: Depends on Foundational + US1 + US2 — Merges env vars into same config model
- **US4 (Cost Tracking)**: Depends on Foundational + US1 — Uses DB connection (from Foundational) and config limits (from US1)
- **US5 (Client Management)**: Depends on Foundational + US1 — Uses DB connection and reviews table

### Within Each User Story (TDD)

1. Write ALL tests first → **Run → FAIL** (red)
2. Implement minimal code → **Run → PASS** (green)
3. Commit after each logical group

### Parallel Opportunities

- T002, T003, T004 all Setup — different packages, can parallelize
- T005, T006, T007 all Foundational — different files, can parallelize
- T008, T009, T010, T011, T012 — T009 depends on T008 (migration needs runner), rest are parallel
- Tests within each user story can run in parallel (different test files)
- Implementation tasks within each user story can run in parallel (different files)
- T054, T055, T056 (Polish) can run in parallel
- Different user stories build sequentially (each depends on prior)

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks everything)
3. **TDD Cycle**: Write tests for US1 → FAIL → Implement → PASS
4. **STOP and VALIDATE**: `openreview --version` on fresh install creates all config files
5. This is the MVP — config and storage foundation is working

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. **MVP**: US1 (First-Time Setup) — Test independently → Demo
3. US2 (Config View/Modify) — Test independently → Demo
4. US3 (Env Var Overrides) — Test independently → Demo
5. US4 (Cost Tracking) — Test independently → Demo
6. US5 (Client Management) — Test independently → Demo
7. Polish & cross-cutting → Finalize

### Commit Strategy

```
Phase 1 + 2:   feat: add config and storage foundation infrastructure
US1:           feat: implement first-time config creation
US2:           feat: implement config show/get/set commands
US3:           feat: implement environment variable overrides
US4:           feat: implement cost tracking and limits
US5:           feat: implement client management CRUD
Polish:        chore: polish and memory verification
```

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- **TDD workflow**: Write tests → FAIL → Implement → PASS within each story
- Commit after each logical group (one commit per user story)
- Stop at MVP checkpoint to validate independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence
- Use `context7` for any library-specific implementation questions (PyYAML, platformdirs, pydantic, typer, sqlite3)
- Lazy imports: heavy deps MUST be imported inside function calls, not at module level (constitution Principle III)
- Error messages: all user-facing errors MUST use the shared error formatting module from T012 with appropriate exit codes
