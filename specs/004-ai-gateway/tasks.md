# Tasks: AI Gateway

**Input**: Design documents from `/specs/004-ai-gateway/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included — TDD workflow per constitution and AGENTS.md. Tests written BEFORE implementation.

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add dependency, create package structure, scaffold test files

- [X] T001 Add `litellm` dependency via `uv add litellm` and run `uv lock`
- [X] T002 Create gateway package: `src/openreview_cli/gateway/__init__.py` (empty initially, re-exports added in Phase 2)
- [X] T003 [P] Create test file skeletons: `tests/unit/test_gateway_models.py`, `tests/unit/test_gateway_engine.py`, `tests/unit/test_gateway_costs.py`, `tests/unit/test_gateway_registry.py`, `tests/unit/test_gateway_wizard.py`, `tests/integration/test_gateway_routing.py`, `tests/integration/test_gateway_fallback.py`, `tests/integration/test_gateway_cli.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core types, error handling, config validation, auth extension — MUST complete before any user story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 [P] Create `GatewayError` dataclass with exit_code, slot, message, action fields in `src/openreview_cli/gateway/errors.py` — follow `PiiError` pattern with `__post_init__` validation
- [X] T005 [P] Create `SlotConfig`, `ModelParams`, `GatewayResponse`, `RerankResult` dataclasses in `src/openreview_cli/gateway/models.py` — use `@dataclass(slots=True)`, `__post_init__` validation per data-model.md
- [X] T006 [P] Create `atomic_write()` utility in `src/openreview_cli/gateway/utils.py` — temp file + fsync + rename pattern per research.md
- [X] T007 Extend `src/openreview_cli/config/loader.py` — add Pydantic models (`SlotConfigModel`, `FallbackConfig`, `CostLimitsConfig`, `GatewayConfigModel`) for gateway config validation inside `_validate_and_merge()`, per contracts/config-schema.md
- [X] T008 Extend `src/openreview_cli/config/auth.py` — add `get_api_key(provider: str) -> str | None` that checks env vars first (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.) then falls back to auth.json
- [X] T009 Add `gateway_error()` function to `src/openreview_cli/errors.py` — exit code 7, follows `pii_error()` pattern
- [X] T010 Write unit tests for models and errors in `tests/unit/test_gateway_models.py` — validation rules from data-model.md (temperature range, token counts, model format)
- [X] T011 Write unit tests for config validation in `tests/unit/test_config_loader.py` — gateway section validation, defaults, env overrides
- [X] T012 Update `src/openreview_cli/gateway/__init__.py` — re-export `GatewayError`, `GatewayResponse`, `RerankResult`, `SlotConfig`, `ModelParams`



**Checkpoint**: Foundation ready — types validated, config loads gateway section, auth resolves keys, errors defined

---

## Phase 3: User Story 1 — Route Requests Through Task-Specific Slots (Priority: P1) 🎯 MVP

**Goal**: Engine can call `route_request(slot, ...)` and get correct response from configured provider/model

**Independent Test**: Configure a slot with a known provider, send request through routing function, verify response returned correctly. Repeat for each of five slots.

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T013 [US1] Write integration test for chat completion routing in `tests/integration/test_gateway_routing.py` — mock LiteLLM `completion()`, verify correct model/provider called, response returned
- [X] T013a [US1] Write integration test for provider switching in `tests/integration/test_gateway_routing.py` — configure slot with provider A, route successfully, reconfigure to provider B via config change only, route again, verify correct provider called without code changes (SC-002)
- [X] T014 [US1] Write integration test for embedding routing in `tests/integration/test_gateway_routing.py` — mock LiteLLM `embedding()`, verify vectors returned
- [X] T015 [US1] Write integration test for reranking routing in `tests/integration/test_gateway_routing.py` — mock LiteLLM `rerank()`, verify sorted results returned
- [X] T015a [US1] Write integration test for fully-local zero-network mode in `tests/integration/test_gateway_routing.py` — configure all 5 slots with Ollama, use `respx.mock(assert_all_mocked=True)` to intercept all httpx calls, assert all requests go to `http://localhost:11434` only, verify no calls to external providers (SC-005)

### Implementation for User Story 1

- [X] T016 [US1] Create `GatewayEngine` class with `route_request()` method in `src/openreview_cli/gateway/engine.py` — accepts slot name, dispatches to correct LiteLLM function based on slot type (chat/embed/rerank)
- [X] T017 [US1] Implement provider resolution in `src/openreview_cli/gateway/engine.py` — read slot config, resolve API key via `get_api_key()`, construct LiteLLM model string, pass `api_key` and `base_url` params
- [X] T018 [US1] Implement chat completion path in `src/openreview_cli/gateway/engine.py` — call `litellm.completion()`, extract `response.choices[0].message.content`, token counts from `response.usage`
- [X] T019 [US1] Implement embedding path in `src/openreview_cli/gateway/engine.py` — call `litellm.embedding()`, extract `response.data[i].embedding`
- [X] T020 [US1] Implement reranking path in `src/openreview_cli/gateway/engine.py` — call `litellm.rerank()`, extract `response.results` into `RerankResult` list
- [X] T021 [US1] Implement slot parameter injection in `src/openreview_cli/gateway/engine.py` — merge slot `params` (temperature, max_tokens, dimensions) with per-call kwargs
- [X] T022 [US1] Write unit tests for engine in `tests/unit/test_gateway_engine.py` — test slot dispatch, parameter injection, error on unconfigured slot
- [X] T023 [US1] Add `route_request()` convenience function in `src/openreview_cli/gateway/engine.py` — module-level function that creates engine from current config and calls `engine.route_request()`

**Checkpoint**: Routing works — all 5 slot types route correctly through LiteLLM, engine code has zero provider-specific imports (FR-017)

---

## Phase 4: User Story 2 — Interactive First-Time Setup (Priority: P1)

**Goal**: First-time user runs `openreview gateway setup` and gets a working configuration through an interactive wizard

**Independent Test**: Run setup on clean config (no files), walk through all 5 slots with simulated input, verify config.yml and auth.json are valid and complete.

**Dependencies**: Phase 2 (Foundational), Phase 3 (US1 — routing needed for API key validation)

### Tests for User Story 2

- [X] T024 [US2] Write integration test for wizard flow in `tests/integration/test_gateway_cli.py` — simulate full wizard with mocked input, verify config and auth files created correctly
- [X] T025 [US2] Write unit tests for wizard in `tests/unit/test_gateway_wizard.py` — test provider selection, model listing, skip, back, cancel-with-save

### Implementation for User Story 2

- [X] T026 [P] [US2] Create `SetupWizard` class in `src/openreview_cli/gateway/wizard.py` — welcome message, slot iteration with "Step X of 5" progress, provider selection via Rich `Prompt`/`Inquirer`
- [X] T027 [US2] Implement model selection step in `src/openreview_cli/gateway/wizard.py` — list models from registry for selected provider, user picks, pre-fill if slot grouping applies
- [X] T027a [US2] Implement `ollama_discover_models()` in `src/openreview_cli/gateway/providers.py` — query `GET http://localhost:11434/api/tags`, parse response `{models: [{name, size, details: {parameter_size, quantization_level}}]}`, handle `httpx.ConnectError` (Ollama not running) and `httpx.TimeoutException`, return list of `ModelInfo` dataclasses. Wire into wizard model selection (FR-012)
- [X] T028 [US2] Implement API key entry in `src/openreview_cli/gateway/wizard.py` — masked input, copy-to-clipboard action, immediate validation via `GET /v1/models` or 1-token fallback, configurable timeout (default 10s via `httpx.Timeout(total=10.0, connect=5.0)`), retry logic with exponential backoff (from `gateway.fallback` config), retry/skip UX on timeout using `typer.confirm()` (FR-028, FR-015, C5)
- [X] T029 [US2] Implement slot grouping in `src/openreview_cli/gateway/wizard.py` — after provider selected for chat slot, offer "Apply to extraction and graph too? (Y/n)" (FR-027)
- [X] T030 [US2] Implement back/cancel/summary in `src/openreview_cli/gateway/wizard.py` — back restores previous selections, cancel warns "Configured slots so far will be saved", summary shows all assignments (FR-026)
- [X] T031 [US2] Implement save in `src/openreview_cli/gateway/wizard.py` — write config.yml via atomic write, write auth.json with chmod 600 (FR-029, FR-005)
- [X] T032 [US2] Add `gateway setup` CLI command in `src/openreview_cli/app.py` — create `gateway_app` Typer sub-app, add `setup` command with `--<slot>` flags, wire to wizard or non-interactive path (FR-020)
- [X] T033 [US2] Implement non-interactive flags path in `src/openreview_cli/app.py` — when flags provided, configure slots directly without wizard, flags take precedence over existing config (FR-020, EC-12)
- [X] T034 [US2] Implement Ollama empty-state handling in `src/openreview_cli/gateway/wizard.py` — three states: not running → `ollama serve` hint, no models → `ollama pull` hint, timeout → spinner + retry/skip (C5)

**Checkpoint**: Setup works — new user can complete wizard in <5 minutes (SC-001), or use flags in <30 seconds (SC-009)

---

## Phase 5: User Story 3 — Automatic Fallback and Retry on Failure (Priority: P2)

**Goal**: When primary model fails, gateway retries with backoff, then falls back to configured fallback model

**Independent Test**: Configure slot with primary + fallback, simulate primary failure (mock timeout), verify gateway retries then falls back, response indicates fallback used.

**Dependencies**: Phase 3 (US1 — routing must work first)

### Tests for User Story 3

- [X] T035 [US3] Write integration test for fallback in `tests/integration/test_gateway_fallback.py` — mock primary failure, verify retry count, fallback activation, on_failure behavior

### Implementation for User Story 3

- [X] T036 [US3] Implement retry with exponential backoff in `src/openreview_cli/gateway/engine.py` — configurable retries, retry_delay, timeout from `gateway.fallback` config (FR-008)
- [X] T037 [US3] Implement fallback chain in `src/openreview_cli/gateway/engine.py` — after retries exhausted on primary, attempt fallback model with same retry logic (FR-007)
- [X] T038 [US3] Implement on_failure behavior in `src/openreview_cli/gateway/engine.py` — error (raise GatewayError), skip (log + return None), warn (emit warning + return partial) (FR-008)
- [X] T039 [US3] Add `fallback_used` flag to `GatewayResponse` in `src/openreview_cli/gateway/engine.py` — set True when fallback model served the request (FR-016)
- [X] T040 [US3] Write unit tests for retry/fallback in `tests/unit/test_gateway_engine.py` — test backoff timing, fallback activation, all three on_failure modes

**Checkpoint**: Fallback works — primary failure triggers retry → fallback within 30 seconds (SC-003), response indicates which model served

---

## Phase 6: User Story 4 — Track Costs and Enforce Limits (Priority: P2)

**Goal**: Per-call token usage and cost recorded, aggregated per session, limits enforced before each call

**Independent Test**: Make several API calls, verify token counts and costs recorded in SQLite. Set low limit, verify next call blocked after limit reached.

**Dependencies**: Phase 3 (US1 — routing must record costs)

### Tests for User Story 4

- [X] T041 [US4] Write integration test for cost tracking in `tests/integration/test_gateway_routing.py` — mock API calls, verify CostRecord inserted, aggregation correct
- [X] T042 [US4] Write integration test for cost limits in `tests/integration/test_gateway_routing.py` — set low limit, verify call blocked before limit, error message includes current cost and limit

### Implementation for User Story 4

- [X] T043 [P] [US4] Create `ReviewSession` and `CostRecord` dataclasses in `src/openreview_cli/gateway/models.py` — per data-model.md, `@dataclass(slots=True)`, `__post_init__` validation
- [X] T044 [P] [US4] Create `CostStore` class in `src/openreview_cli/gateway/costs.py` — SQLite operations: create tables, insert CostRecord, aggregate by session/day, check limits
- [X] T045 [US4] Implement pre-call cost limit check in `src/openreview_cli/gateway/engine.py` — before each API call, check session total + estimated cost vs per_review limit, check daily total vs daily limit (FR-010, SC-006)
- [X] T046 [US4] Implement post-call cost recording in `src/openreview_cli/gateway/engine.py` — after each API call, extract token counts from LiteLLM response, compute cost via `completion_cost()`, insert CostRecord (FR-009)
- [X] T047 [US4] Implement session lifecycle in `src/openreview_cli/gateway/costs.py` — create session (UUID), update totals, mark completed
- [X] T048 [US4] Write unit tests for costs in `tests/unit/test_gateway_costs.py` — test CostStore CRUD, aggregation, limit enforcement, session lifecycle

**Checkpoint**: Cost tracking works — tokens recorded within 1% accuracy (SC-004), limits enforced before call (SC-006)

---

## Phase 7: User Story 5 — Manage Gateway Configuration via CLI (Priority: P3)

**Goal**: Maintenance and diagnostic commands for day-to-day gateway management

**Independent Test**: Run each subcommand against known config, verify output matches expectations.

**Dependencies**: Phase 2 (Foundational), Phase 3 (US1 — routing needed for test command)

### Tests for User Story 5

- [X] T049 [US5] Write integration test for CLI commands in `tests/integration/test_gateway_cli.py` — test each subcommand (status, providers, models, set, test, refresh, costs, install-models)

### Implementation for User Story 5

- [X] T050 [P] [US5] Create `ModelRegistry` class in `src/openreview_cli/gateway/registry.py` — load/save JSON cache, fetch from remote URL, retain cache on fetch failure (FR-018)
- [X] T051 [P] [US5] Create built-in minimal registry in `src/openreview_cli/gateway/registry.py` — fallback when cache missing/corrupted (FR-019), covers top models per provider
- [X] T051a [US5] Write unit tests for built-in registry fallback in `tests/unit/test_gateway_registry.py` — delete cache file, verify built-in minimal registry loads; corrupt cache JSON, verify fallback activates and returns valid model data (FR-019)
- [X] T052 [US5] Implement `openreview gateway status` command in `src/openreview_cli/app.py` — Rich table showing each slot's model, provider reachability, health (FR-013)
- [X] T053 [US5] Implement `openreview gateway providers` command in `src/openreview_cli/app.py` — list all providers with auth method and configured/not-configured status
- [X] T054 [US5] Implement `openreview gateway models <provider>` command in `src/openreview_cli/app.py` — list models with slot compatibility, context window, pricing
- [X] T055 [US5] Implement `openreview gateway set <slot> <provider/model>` command in `src/openreview_cli/app.py` — update config with atomic write, support --fallback, --temperature, --max-tokens flags
- [X] T056 [US5] Implement `openreview gateway test <slot>` command in `src/openreview_cli/app.py` — call `GET /v1/models` or 1-token completion, report success/failure + latency (FR-015)
- [X] T057 [US5] Implement `openreview gateway refresh` command in `src/openreview_cli/app.py` — fetch remote registry, update cache, retain on failure
- [X] T058 [US5] Implement `openreview gateway costs` command in `src/openreview_cli/app.py` — show daily/session totals, --days, --session, --clear, --json flags
- [X] T059 [US5] Implement `openreview gateway install-models` command in `src/openreview_cli/app.py` — pull Ollama models with progress display

**Checkpoint**: CLI management works — all 8 subcommands functional (FR-013)

---

## Phase 8: User Story 6 — Import Configuration from YAML File (Priority: P2)

**Goal**: Power users and teams can import config from YAML file or use flags without wizard

**Independent Test**: Write valid YAML with all 5 slots, run import, verify config matches. Repeat with invalid files, verify all errors reported at once.

**Dependencies**: Phase 2 (Foundational — config validation, atomic writes)

### Tests for User Story 6

- [X] T060 [US6] Write integration test for YAML import in `tests/integration/test_gateway_cli.py` — valid import, invalid import (all errors reported), overwrite confirmation

### Implementation for User Story 6

- [X] T061 [US6] Create import validation in `src/openreview_cli/gateway/importer.py` — parse YAML, validate all 5 slot keys present (reasoning, extraction, embedding, reranking, graph), check provider names, check model format, report ALL errors at once (FR-024). Note: YAML import requires all 5 slots per US6 scenario 1; wizard skip (FR-022) is a separate path
- [X] T062 [US6] Implement `openreview gateway import <file>` command in `src/openreview_cli/app.py` — validate, prompt for overwrite confirmation, apply via atomic write, resolve `api_key_env` references (FR-023, FR-025)
- [X] T063 [US6] Implement env var key resolution in `src/openreview_cli/gateway/importer.py` — read `api_key_env` section, verify env vars exist, write keys to auth.json with chmod 600
- [X] T064 [US6] Write unit tests for import in `tests/unit/test_gateway_importer.py` — test validation (missing fields, bad providers, inline keys rejected), env var resolution

**Checkpoint**: Import works — YAML import in <10 seconds (SC-011), all errors reported at once (FR-024)

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [X] T065 [P] Implement three-tier logging in `src/openreview_cli/gateway/logging.py` — console INFO (API calls, cost, fallback), debug file `~/.openreview/gateway.log` (DEBUG: per-call timing, tokens), never log response bodies unless `--debug-unsafe` (C9)
- [X] T065a [P] Create routing performance benchmark in `tests/integration/test_gateway_benchmark.py` — measure gateway routing overhead vs direct LiteLLM calls using `time.perf_counter()`, mock HTTP layer with `respx` to isolate Python overhead from network latency, assert median overhead <50ms (SC-007). Use subtraction method: `overhead = wrapped_call_time - direct_call_time`
- [X] T066 [P] Implement API key redaction in all log output — ensure 100% of keys redacted in logs and CLI display (SC-008), add redaction filter to stdlib logging
- [X] T066a [P] Create network isolation test in `tests/integration/test_gateway_privacy.py` — use `respx.mock(assert_all_mocked=True)` to intercept all HTTP calls during gateway operations, assert all requests go to user-configured provider URLs only (no tool-operated domains), verify API keys sent only to provider endpoints. Covers: setup wizard validation, routing calls, cost tracking, model registry refresh (FR-006)
- [X] T067 Run quickstart.md validation scenarios — execute all 10 scenarios from `specs/004-ai-gateway/quickstart.md`, verify all pass
- [X] T068 Full test suite + pre-commit sweep — `uv run pytest`, `uv run ruff check .`, `uv run ruff format`, `uv run mypy src/ tests/`, `uvx pre-commit run --all-files`
- [X] T069 Update `AGENTS.md` — add Phase 4 gateway section to "Where things live", update SPECKIT markers

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Foundational — MVP, highest priority
- **US2 (Phase 4)**: Depends on Foundational + US1 (routing needed for API key validation)
- **US3 (Phase 5)**: Depends on US1 (routing must work before adding retry/fallback)
- **US4 (Phase 6)**: Depends on US1 (routing must record costs)
- **US5 (Phase 7)**: Depends on Foundational + US1 (test command needs routing)
- **US6 (Phase 8)**: Depends on Foundational (config validation, atomic writes)
- **Polish (Phase 9)**: Depends on all user stories complete

### User Story Dependencies

- **US1 (P1)**: After Foundational — no story dependencies — **MVP**
- **US2 (P1)**: After Foundational + US1 — wizard validates keys via routing
- **US3 (P2)**: After US1 — extends engine with retry/fallback
- **US4 (P2)**: After US1 — extends engine with cost tracking
- **US5 (P3)**: After Foundational + US1 — CLI commands use routing for test
- **US6 (P2)**: After Foundational — import uses config validation

### Within Each User Story

- Tests MUST be written and FAIL before implementation (TDD)
- Models before services before CLI commands
- Core implementation before integration

### Parallel Opportunities

- Phase 1: T002 + T003 in parallel
- Phase 2: T004 + T005 + T006 in parallel (different files)
- Phase 4: T026 (wizard.py) can start while T024/T025 tests are written
- Phase 6: T043 + T044 in parallel (models.py + costs.py)
- Phase 7: T050 + T051 in parallel (registry.py)
- Phase 9: T065 + T066 in parallel (different files)
- US3, US4, US6 can proceed in parallel after US1 complete (different concerns in engine.py — but serialize to avoid merge conflicts)

---

## Parallel Example: Phase 2 (Foundational)

```text
# Launch all foundational types together (different files):
Task: "Create GatewayError in src/openreview_cli/gateway/errors.py"
Task: "Create SlotConfig, ModelParams, GatewayResponse in src/openreview_cli/gateway/models.py"
Task: "Create atomic_write() in src/openreview_cli/gateway/utils.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: User Story 1 (routing)
4. **STOP and VALIDATE**: Test routing through all 5 slots
5. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. US1 (routing) → Test independently → **MVP!**
3. US2 (setup wizard) → Test independently → First-time user experience complete
4. US3 (fallback) → Test independently → Resilience added
5. US4 (costs) → Test independently → Cost visibility added
6. US5 (CLI) → Test independently → Day-to-day management
7. US6 (import) → Test independently → Power user / team support
8. Polish → Production ready

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Verify tests fail before implementing (TDD)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Lazy imports for litellm, rich, pydantic (constitutional Principle III)
- All config writes use atomic_write() (FR-029)
- API keys never logged (SC-008)
- Total: 75 tasks across 9 phases
