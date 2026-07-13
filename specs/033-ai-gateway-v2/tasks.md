# Tasks: AI Gateway v2 Redesign

**Input**: Design documents from `/specs/033-ai-gateway-v2/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/, quickstart.md
**Tests**: TDD per project AGENTS.md — tests written BEFORE implementation. Each user story has a Tests subsection.

## Format: `[ID] [P?] [Story?] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions
- Gateway code: `src/openreview_cli/gateway/`
- Config: `src/openreview_cli/config/`
- Storage: `src/openreview_cli/storage/`
- CLI: `src/openreview_cli/app.py`
- Unit tests: `tests/unit/`
- Integration tests: `tests/integration/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create all new module files (skeletons/stubs) so imports resolve and the project structure is ready for parallel work. No business logic yet.

- [ ] T001 [P] Add `keyring` as optional dependency via `uv add --optional auth keyring` in `pyproject.toml`
- [ ] T002 [P] Create `src/openreview_cli/gateway/v2_config.py` with V2Config, ProviderConfig, SlotAssignment, ApiKeySource, FallbackConfig, CostLimits, CircuitBreaker Pydantic models (from `data-model.md`)
- [ ] T003 [P] Create `src/openreview_cli/gateway/resolver.py` skeleton with stub `resolve(short_name, providers) -> str`
- [ ] T004 [P] Create `src/openreview_cli/gateway/keyring_store.py` skeleton with stub `get/set/delete/list` methods
- [ ] T005 [P] Create `src/openreview_cli/gateway/migrate.py` skeleton with stub `migrate_config()` returning bool
- [ ] T006 [P] Create `src/openreview_cli/gateway/apply.py` skeleton with stub `apply_config(json_str) -> dict`

**Checkpoint**: All new module files exist. Imports resolve. No logic yet.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure fixes that MUST be complete before ANY user story can be implemented.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T007 [P] Add `grounding` field to `GatewayModels` Pydantic schema in `src/openreview_cli/config/loader.py` — fixes schema rejection of the 6th slot
- [ ] T008 [P] Create migration file `src/openreview_cli/storage/migrations/004_nullable_session.sql` that makes `cost_logs.session_id` nullable (table rebuild per SQLite constraints)
- [ ] T009 [P] Update `src/openreview_cli/storage/database.py` to apply migration 004 and handle nullable `session_id` in `cost_logs` inserts
- [ ] T010 [P] Update `src/openreview_cli/gateway/cost.py` to pass `session_id=None` when no session context exists, write cost records without FK failure
- [ ] T011 [P] Write unit test for `grounding` field persistence in `tests/unit/test_cli_gateway_v2.py` — set grounding slot, verify config reload includes it
- [ ] T012 [P] Write unit test for nullable `session_id` cost write in `tests/unit/test_gateway_cost.py` — cost record written without session produces no FK error

**Checkpoint**: Foundation ready. Bug fixes deployed. User story implementation can now begin.

---

## Phase 3: User Story 1 — Agent configures gateway non-interactively (Priority: P1) 🎯 MVP

**Goal**: Replace TTY-only wizard with JSON-stdin applier so agents and CI can set up the gateway without TTY.

**Independent Test**: Pipe a valid JSON config to `openreview gateway setup`, then run `openreview gateway status --format json` and confirm configured providers and slots appear.

### Tests for User Story 1

- [ ] T013 [P] [US1] Test valid JSON applied atomically in `tests/unit/test_gateway_apply.py` — apply valid JSON, verify config.yml and auth.json written, exit 0
- [ ] T014 [P] [US1] Test invalid JSON returns field-named error in `tests/unit/test_gateway_apply.py` — apply malformed JSON, verify no partial write, exit 1, error names the failed field
- [ ] T015 [P] [US1] Test no-TTY no-stdin returns usage message in `tests/unit/test_gateway_apply.py` — run with empty stdin, verify exit non-zero with usage message pointing to `--help`

### Implementation for User Story 1

- [ ] T016 [US1] Implement JSON parser + validator with atomic write semantics in `src/openreview_cli/gateway/apply.py` — parse stdin JSON, validate against V2Config schema, write config.yml + auth.json atomically (all-or-nothing), exit 0 on success
- [ ] T017 [US1] Replace wizard call with JSON applier in `src/openreview_cli/app.py` (`gateway setup` command) — stdin pipe reads JSON, calls apply.py, no interactive prompts
- [ ] T018 [US1] Add `--dry-run` flag to `gateway setup` CLI in `src/openreview_cli/app.py` — validates piped JSON, reports what would be written, does not modify files
- [ ] T019 [US1] Write CLI integration test for `gateway setup` flow in `tests/integration/test_e2e_gateway_v2.py` — pipe valid JSON, verify config persisted, pipe invalid JSON, verify error + no partial write

**Checkpoint**: User Story 1 fully functional. Agents can configure the gateway with a single JSON-pipe command.

---

## Phase 4: User Story 2 — Agent lists models reachable with current keys (Priority: P1)

**Goal**: Provide model discovery so agents know what models are available with the keys they configured.

**Independent Test**: After configuring two providers, run `openreview models available` and receive a non-empty list of models with short names, providers, and compatible slots.

### Tests for User Story 2

- [ ] T020 [P] [US2] Test `models available` with configured providers in `tests/unit/test_cli_gateway_v2.py` — 2 providers configured, output lists models from both
- [ ] T021 [P] [US2] Test `models available` with no providers in `tests/unit/test_cli_gateway_v2.py` — empty provider list, output is empty with info message
- [ ] T022 [P] [US2] Test `models available --provider` filter in `tests/unit/test_cli_gateway_v2.py` — filter by single provider, only that provider's models shown

### Implementation for User Story 2

- [ ] T023 [US2] Add registry filtering logic to `src/openreview_cli/gateway/registry.py` — method `get_available_models(configured_providers)` returns list of model entries filtered by providers the user has keys for
- [ ] T024 [US2] Implement `models available` CLI command in `src/openreview_cli/app.py` — lists models by short name, provider, compatible slots; supports `--provider` filter
- [ ] T025 [US2] Write CLI integration test for `models available` in `tests/unit/test_cli_gateway_v2.py` — verify output format, performance (<1s)

**Checkpoint**: User Story 2 complete. Agents can discover available models.

---

## Phase 5: User Story 3 — Agent sets a slot by short name (Priority: P1)

**Goal**: Allow agents to set slots using short model names without typing `provider/model` format.

**Independent Test**: After configuring OpenAI, run `openreview set reasoning gpt-4o` and `openreview test reasoning` succeeds without ever typing `openai/gpt-4o`.

### Tests for User Story 5

- [ ] T026 [P] [US3] Test short name resolves correctly in `tests/unit/test_gateway_resolver.py` — `"gpt-4o"` resolves to `("openai", "gpt-4o")` when OpenAI is configured
- [ ] T027 [P] [US3] Test direct > proxy preference in `tests/unit/test_gateway_resolver.py` — both OpenAI and OpenRouter configured, `"gpt-4o"` resolves to OpenAI
- [ ] T028 [P] [US3] Test explicit `provider/model` bypasses resolution in `tests/unit/test_gateway_resolver.py` — input `"openai/gpt-4o"` passes through unchanged

### Implementation for User Story 5

- [ ] T029 [US3] Implement `resolver.py` with alias map + provider priority ordering in `src/openreview_cli/gateway/resolver.py` — resolve short names to `(provider, model)` tuples; priority: direct > proxy; explicit `provider/model` passthrough; error with suggestions on no match
- [ ] T030 [US3] Integrate resolver into `set` command flow in `src/openreview_cli/app.py` — `openreview set <slot> <model>` calls resolver before persisting assignment
- [ ] T031 [US3] Integrate resolver into `router.py` chat/embed/rerank methods in `src/openreview_cli/gateway/router.py` — resolve model strings at call time if they're short names
- [ ] T032 [US3] Write CLI test for `set` command with short name in `tests/unit/test_cli_gateway_v2.py` — verify output shows resolved provider/model

**Checkpoint**: User Story 3 complete. Short-name resolution works for all slots.

---

## Phase 6: User Story 4 — All CLI commands are agent-friendly (Priority: P1)

**Goal**: Every gateway CLI command works non-interactively with structured output and machine-parseable errors.

**Independent Test**: Every gateway subcommand runs in non-TTY context (stdin=/dev/null) without hanging, prompting, or producing parse-unfriendly output. Shell script can call each subcommand and branch on exit code.

### Tests for User Story 6

- [ ] T033 [P] [US4] Test `--format json` on all gateway commands in `tests/unit/test_cli_gateway_v2.py` — `gateway status`, `gateway costs`, `gateway test`, `models available`, `auth list`, `migrate config` all produce valid JSON
- [ ] T034 [P] [US4] Test structured exit codes (1=user error, 2=config error, 3=provider error) in `tests/unit/test_cli_gateway_v2.py` — each error type produces correct exit code
- [ ] T035 [P] [US4] Test TTY detection prevents interactive hangs in `tests/unit/test_cli_gateway_v2.py` — run in non-TTY context, no prompts, no blocks
- [ ] T036 [P] [US4] Test JSON error format is valid parsable JSON in `tests/unit/test_cli_gateway_v2.py` — `{"error": str, "code": int, "message": str}` output on errors with `--format json`

### Implementation for User Story 6

- [ ] T037 [US4] Implement shared output formatter with structured exit codes + JSON error format in `src/openreview_cli/gateway/__init__.py` — `format_output(data, format="text"|"json")` helper, `format_error(error, code, message, format)` for JSON error objects
- [ ] T038 [US4] Add `--format text|json` flag to `gateway status`, `gateway costs`, `gateway test` in `src/openreview_cli/app.py` — wire shared output formatter
- [ ] T039 [US4] Add `--format text|json` flag to `models available`, `auth list`, `migrate config` in `src/openreview_cli/app.py` — remaining commands
- [ ] T040 [US4] Implement TTY detection wrapper in `src/openreview_cli/app.py` — commands that require TTY input exit with code 1 and clear message when no TTY detected

**Checkpoint**: User Story 4 complete. All CLI commands work non-interactively with structured output.

---

## Phase 7: User Story 5 — User upgrades to v2 config without losing work (Priority: P2)

**Goal**: Provide a one-time migration command so existing v1 users don't lose slot assignments.

**Independent Test**: Create a v1 config with known slot assignments, run `openreview migrate config`, verify v2 config has same effective assignments and `auth.json` is untouched.

### Tests for User Story 7

- [ ] T041 [P] [US5] Test v1 → v2 migration preserves slot assignments in `tests/unit/test_gateway_migrate.py` — 5 slots in v1, all present in v2 output
- [ ] T042 [P] [US5] Test migration does not modify `auth.json` in `tests/unit/test_gateway_migrate.py` — compare checksum before/after
- [ ] T043 [P] [US5] Test no-op on already-v2 config in `tests/unit/test_gateway_migrate.py` — exit 0, no files modified

### Implementation for User Story 7

- [ ] T044 [US5] Implement v1 → v2 config converter with safety backup in `src/openreview_cli/gateway/migrate.py` — read v1 slot-first YAML, parse providers from slot assignments, write v2 provider-first YAML, backup original to `.bak`
- [ ] T045 [US5] Wire `migrate config` CLI command in `src/openreview_cli/app.py` — detects v1 vs v2 format, runs conversion or no-op
- [ ] T046 [US5] Write CLI integration test for `migrate config` in `tests/unit/test_cli_gateway_v2.py` — create v1 config fixture, run migration, verify v2 format
- [ ] T047 [US5] Add v1 format detection error in gateway loader in `src/openreview_cli/config/loader.py` — if config version is 1, print error: "Run `openreview migrate config` to upgrade" and exit

**Checkpoint**: User Story 5 complete. v1 users can migrate without losing data.

---

## Phase 8: User Story 6 — API keys stored in OS keyring (Priority: P2)

**Goal**: Improve security by storing API keys in the OS keyring instead of a flat file.

**Independent Test**: With `keyring` installed, running `openreview auth add openrouter sk-or-...` stores key in OS keyring. Listing shows provider configured. Removal deletes from keyring.

### Tests for User Story 8

- [ ] T048 [P] [US6] Test `auth add` stores to keyring when available in `tests/unit/test_gateway_keyring.py` — mock `keyring` library, verify `set_password` called with correct args
- [ ] T049 [P] [US6] Test `auth add` falls back to `auth.json` with chmod 600 when keyring unavailable in `tests/unit/test_gateway_keyring.py` — mock `keyring` import failure, verify file write + permissions
- [ ] T050 [P] [US6] Test `auth list` shows sources without revealing full key in `tests/unit/test_gateway_keyring.py` — output shows provider, source (keyring/file/env), masked key (last 4 chars)
- [ ] T051 [P] [US6] Test `auth remove` deletes from correct store in `tests/unit/test_gateway_keyring.py` — key from keyring → `delete_password` called; key from file → removed from auth.json

### Implementation for User Story 8

- [ ] T052 [US6] Implement `keyring_store.py` with keyring + file fallback in `src/openreview_cli/gateway/keyring_store.py` — `get/set/delete/list_providers` methods; file fallback with chmod 600; one-time warning on fallback
- [ ] T053 [US6] Wire keyring store into `src/openreview_cli/config/auth.py` — auth resolution tier: env > keyring > file; write path chooses keyring or file based on availability
- [ ] T054 [US6] Implement `auth add/list/remove` CLI commands in `src/openreview_cli/app.py` — add with optional `--base-url` (stub for US9), list with masked keys, remove confirms deletion

**Checkpoint**: User Story 6 complete. API keys securely stored in OS keyring with transparent file fallback.

---

## Phase 9: User Story 7 — Cost tracking works end-to-end (Priority: P2)

**Goal**: Fix cost tracking FK bug and add query filters.

**Independent Test**: Run a gateway call that generates cost data, then query `openreview gateway costs --today` and verify cost record exists with non-zero token counts and no FK errors.

### Tests for User Story 9

- [ ] T055 [P] [US7] Test cost record with nullable `session_id` in `tests/unit/test_gateway_cost.py` — cost write succeeds when `session_id is None`, record has NULL in DB
- [ ] T056 [P] [US7] Test `gateway costs --today` filter in `tests/unit/test_gateway_cost.py` — only today's records returned
- [ ] T057 [P] [US7] Test `gateway costs --session` filter in `tests/unit/test_gateway_cost.py` — only records for given session ID returned

### Implementation for User Story 9

- [ ] T058 [US7] Update `src/openreview_cli/gateway/cost.py` to pass `session_id=None` when no session context exists — cost records always written without FK failure
- [ ] T059 [US7] Update `src/openreview_cli/storage/database.py` — ensure cost_logs insert accepts nullable `session_id`, query methods support `--today`, `--session`, `--since` filters
- [ ] T060 [US7] Implement `gateway costs` CLI command with `--today / --session / --since` flags and `--format json` in `src/openreview_cli/app.py`

**Checkpoint**: User Story 7 complete. Cost tracking works end-to-end with filterable queries.

---

## Phase 10: User Story 8 — Grounding slot in config schema (Priority: P2)

**Goal**: Complete the grounding slot wiring so `set grounding`, `gateway status`, and `gateway test grounding` all work.

**Note**: The Pydantic schema fix for `grounding` is already done in Phase 2 (T007). This phase wires the CLI commands.

### Tests for User Story 10

- [ ] T061 [P] [US8] Test `gateway set grounding` persists to config in `tests/unit/test_cli_gateway_v2.py` — set grounding with a model, verify config.yml contains the assignment
- [ ] T062 [P] [US8] Test `gateway test grounding` makes API call in `tests/unit/test_cli_gateway_v2.py` — test with configured slot, verify call succeeds; test with unconfigured slot, verify clear error
- [ ] T063 [P] [US8] Test `gateway status` shows grounding slot in `tests/unit/test_cli_gateway_v2.py` — both `--format text` and `--format json` display grounding

### Implementation for User Story 10

- [ ] T064 [US8] Wire `gateway set grounding <model>` CLI command in `src/openreview_cli/app.py` — validates slot name, calls resolver, persists to config.yml
- [ ] T065 [US8] Wire `gateway test grounding` CLI command in `src/openreview_cli/app.py` — reads slot config, makes test API call via router.py, reports success/failure
- [ ] T066 [US8] Wire grounding slot into `gateway status` output in `src/openreview_cli/app.py` — included alongside the other 5 slots in JSON and table output

**Checkpoint**: User Story 8 complete. Grounding slot fully functional.

---

## Phase 11: User Story 9 — User customizes provider with custom base URL (Priority: P3)

**Goal**: Support self-hosted OpenAI-compatible endpoints via `--base-url` flag.

**Independent Test**: Add a provider with `--base-url https://my-endpoint.example.com`, verify gateway calls reach the custom endpoint.

### Tests for User Story 11

- [ ] T067 [P] [US9] Test `auth add --base-url` stores custom URL in `tests/unit/test_cli_gateway_v2.py` — add with `--base-url`, verify ProviderConfig stores it
- [ ] T068 [P] [US9] Test router uses custom base URL in `tests/unit/test_gateway_router.py` — add provider with custom URL, make call, verify request goes to custom endpoint

### Implementation for User Story 11

- [ ] T069 [US9] Implement `--base-url` flag for `auth add` in `src/openreview_cli/app.py` — stores custom URL in ProviderConfig.base_url
- [ ] T070 [US9] Add custom provider routing support in `src/openreview_cli/gateway/router.py` — if ProviderConfig.base_url is set, use it as API base instead of default
- [ ] T071 [US9] Add base_url validation in `src/openreview_cli/gateway/v2_config.py` — ProviderConfig validator ensures URL has scheme (http/https)

**Checkpoint**: User Story 9 complete. Custom providers work end-to-end.

---

## Phase 12: Polish & Cross-Cutting Concerns

**Purpose**: Final sweep — exports, lint, types, docs, and validation.

- [ ] T072 [P] Update `src/openreview_cli/gateway/__init__.py` to export all new modules (V2Config, resolver, keyring_store, migrate, apply)
- [ ] T073 [P] Add Docstrings and type annotations to all new gateway modules
- [ ] T074 [P] Run full lint sweep (`ruff check src/ tests/`) and fix all issues
- [ ] T075 [P] Run full type check (`mypy --strict src/ tests/`) and fix all issues
- [ ] T076 [P] Validate all quickstart.md scenarios pass (Phase A, B, C) — run each validation step, document results
- [ ] T077 [P] Run complete test suite excluding memory tests (`uv run pytest tests/ -k "not memory" -q`) — all tests green
- [ ] T078 [P] Update `.specify/memory/reports/` with completeness report for spec 033

**Checkpoint**: Spec 033 fully implemented and validated.

---

## Dependencies & Execution Order

### Phase Dependencies
- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **User Stories (Phase 3-11)**: All depend on Foundational
  - P1 stories (US1-US4) can proceed in parallel after Phase 2
  - P2 stories (US5-US8) can proceed in parallel after Phase 2
  - P3 story (US9) can proceed after Phase 2
- **Polish (Phase 12)**: Depends on all user stories being complete

### User Story Within-Phase Ordering
- Tests MUST be written and fail BEFORE implementation (TDD per AGENTS.md)
- Within implementation: models first → services → CLI commands → integration tests
- Example US1: T013-T015 (tests, fail expected) → T016 (apply.py logic) → T017 (app.py wiring) → T018 (--dry-run) → T019 (integration test)

### User Story Dependencies
- **US1 (P1) MVP**: No dependency on other stories — can start first after Phase 2
- **US2 (P1)**: No dependency on other stories — uses existing registry.py
- **US3 (P1)**: No dependency on other stories — resolver.py is self-contained
- **US4 (P1)**: Touches `app.py` broadly — coordinate with US1 and US8 to avoid merge conflicts on `app.py` (both add CLI commands)
- **US5 (P2)**: Depends on v2_config.py (Phase 1, T002) — independent of other stories
- **US6 (P2)**: Depends on keyring_store.py (Phase 1, T004) — shares `app.py` auth commands with US9 (coordinate)
- **US7 (P2)**: Depends on T008/T009/T010 (Foundational Phase 2) — independent otherwise
- **US8 (P2)**: Depends on T007 (Foundational Phase 2) — adds commands to `app.py`, coordinate with US4
- **US9 (P3)**: Touches `auth add` in `app.py` — coordinate with US6 (same CLI section)

### Parallel Opportunities
- All [P] tasks within a phase can run in parallel (different files, no dependencies)
- All Setup tasks T001-T006 are [P] — parallel creation of skeleton files
- All Foundational tasks T007-T012 are [P] — grounding schema, migration SQL, cost update, tests
- Test tasks within each user story phase are [P] — can run in parallel
- P1 stories (US1-4) are file-independent and can be implemented in parallel:
  - US1: apply.py + app.py (gateway setup)
  - US2: registry.py + app.py (models available) — shares app.py but different command section
  - US3: resolver.py + app.py + router.py (set command) — shares app.py with US1
  - US4: shared formatter + app.py (--format json) — touches many app.py sections
- P2 stories (US5-8) are file-independent and can be implemented in parallel:
  - US5: migrate.py + app.py (migrate config)
  - US6: keyring_store.py + auth.py + app.py (auth commands)
  - US7: cost.py + database.py + app.py (costs)
  - US8: app.py (set/test grounding) — minimal, touches app.py
- US9 (P3): v2_config.py + router.py + app.py (custom base URL)

---

## Parallel Example: User Story 1

```bash
# Launch all tests for US1 together (T013, T014, T015):
uv run pytest tests/unit/test_gateway_apply.py -v

# Then run implementation in order:
# T016 → Implement JSON parser + atomic write in apply.py
# T017 → Wire gateway setup in app.py
# T018 → Add --dry-run flag in app.py
# T019 → CLI integration test
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1: Setup (T001-T006) — create all module stubs
2. Phase 2: Foundational (T007-T012) — critical bug fixes
3. Phase 3: User Story 1 (T013-T019) — JSON-stdin setup
4. **STOP and VALIDATE**: Run `uv run pytest tests/unit/ -k "not memory" -q` and pipe a sample JSON to `openreview gateway setup`
5. Deploy/demo if ready — agent can now configure the gateway via JSON!

### Incremental Delivery (Recommended)

1. Phase 1 + 2 → Bug fixes, foundation ready
2. + User Story 1 (P1) → **MVP**: agent configures gateway via JSON
3. + User Story 2 (P1) → Agent discovers available models
4. + User Story 3 (P1) → Agent sets slots by short name
5. + User Story 4 (P1) → All CLI commands non-interactive
6. + User Stories 5-8 (P2) → Migration, keyring, cost tracking, grounding
7. + User Story 9 (P3) → Custom providers
8. + Phase 12 (Polish) → Final sweep

### Parallel Team Strategy (3+ Developers)

With multiple developers:
1. All: Phase 1 + Phase 2 together (small, blocking, fast)
2. Once Phase 2 done, split:
   - Developer A: US1 (gateway setup) — `apply.py` + `app.py` (setup command)
   - Developer B: US2 (models available) + US3 (short-name) — `registry.py` + `resolver.py` + `app.py`
   - Developer C: US6 (keyring) — `keyring_store.py` + `auth.py` + `app.py` (auth commands)
3. After A+B complete:
   - Developer A: US4 (CLI non-interactive) — shared formatter + `app.py` (--format json everywhere)
   - Developer B: US5 (migrate) + US7 (cost) — `migrate.py` + `cost.py` + `app.py`
   - Developer C: US8 (grounding) + US9 (custom provider) — `app.py` + `router.py`
4. All: Phase 12 (Polish) — final sweep

---

## Notes

- **TDD per AGENTS.md**: Tests MUST be written and expected to fail BEFORE implementation code. Every task in a user story's Tests section must execute (and fail) before the corresponding Implementation task begins.
- **`[P]` tasks**: Different files, no dependencies — safe to run in parallel without merge conflicts
- **`[Story]` label**: Maps task to specific user story for traceability and progress tracking
- **Each user story is independently completable and testable** — stories do not depend on other stories (only on Phase 1 + 2 foundation)
- **Commit discipline**: Commit after each task or logical group. Use conventional commits (`feat:`, `test:`, `fix:`).
- **Merge conflicts on `app.py`**: US1, US4, US6, US8, US9 all touch `app.py`. Coordinate or sequence these to avoid conflicts. Recommendation: sequence US1 → US6 → US4 → US8 → US9 on `app.py`, updating the same file serially or with a shared developer.
- **`models.json`**: Already has voyage entries per Phase 9 convergence. No changes needed.
- **`redaction.py`**: Already has `VOYAGE_API_KEY` per Phase 9. No new keys needed.
- **`wizard.py`**: Deprecated for CLI but kept for TUI compat (spec 032). No code changes.
- **`keyring` dependency**: The constitution v1.3.0 permits `keyring` as an optional runtime dep (Principle IV amendment). Use `--optional auth` flag in `uv add`.
- **No new database tables**: The `sessions` table already exists. The only DB change is making `cost_logs.session_id` nullable (migration 004).
- **No server mode**: Per constitution Principle II and spec assumptions, gateway remains direct SDK mode. No LiteLLM proxy server.
- **v1 config**: Read-only via migration command. Gateway itself only reads v2 format (hard break per spec). Auto-detect v1 and error with migration instructions.
