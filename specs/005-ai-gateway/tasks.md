# Implementation Tasks: AI Gateway

**Feature**: 005-ai-gateway
**Status**: Implementation complete

## Dependencies

- **Phase 1 (Setup)**: Blocks Phase 2
- **Phase 2 (Foundation)**: Blocks Phase 3
- **Phase 3 (Core Routing)**: Blocks Phase 4, Phase 5, Phase 7
- **Phase 4 (Rerank)**: Parallel to Phase 5, Phase 6
- **Phase 5 (Cost Tracking)**: Modifies router.py, depends on Phase 3
- **Phase 6 (Registry)**: Parallel to Phase 3, blocks Phase 7
- **Phase 7 (Wizard & CLI)**: Depends on all prior phases

## Phase 1: Setup

Goal: Initialize project dependencies.

- [x] T001 Add LiteLLM dependency via `uv add litellm` in the project root

## Phase 2: Foundational (Config & Storage)

Goal: Extend existing configuration models and database schema to support the gateway.

- [x] T002 [P] Update `src/openreview_cli/config/loader.py` to add `extra_params: dict[str, Any] | None = None` to `ModelSlot`
- [x] T003 Create `src/openreview_cli/storage/migrations/003_gateway.sql` to rename `review_id` to `session_id` and add `slot` column to `cost_logs` table
- [x] T004 Update `src/openreview_cli/storage/database.py` to rename `review_id` parameter to `session_id` in `log_cost`, `check_daily_limit`, `check_review_limit`, and add `slot` parameter to `log_cost` and `get_session_cost` query
- [x] T005 [P] Create `src/openreview_cli/gateway/models.py` with Pydantic models: `ProviderInfo`, `ModelEntry`, `CostRecord`
- [x] T006 Create `src/openreview_cli/gateway/errors.py` with exception hierarchy: `GatewayError`, `ProviderError`, `SlotNotConfiguredError`, `AllProvidersFailedError`
- [x] T007 Create `src/openreview_cli/gateway/__init__.py` exposing the core models and errors
- [x] T008 [P] Create `src/openreview_cli/gateway/models.json` with static curated model list covering 8 providers

## Phase 3: Core Routing (Chat & Embed)

**User Stories:** US1, US2
**Goal:** Route completion and embedding requests with fallback logic.

- [x] T009 [US1] Create `src/openreview_cli/gateway/router.py` with `Gateway` class, `__init__` (loading config and auth), and helper `_get_litellm_kwargs`
- [x] T010 [US1] Implement `chat` method in `router.py` with primary/fallback retry logic, passing `extra_params` as kwargs
- [x] T011 [US2] Implement `embed` method in `router.py`
- [x] T012 [P] [US1] Create `tests/unit/test_gateway_router.py` and test `chat` and `embed` with mocked `litellm` calls

## Phase 4: Reranking

**User Stories:** US3
**Goal:** Expose reranking capabilities.

- [x] T013 [US3] Implement `rerank` method in `src/openreview_cli/gateway/router.py`
- [x] T014 [US3] Update `tests/unit/test_gateway_router.py` to test `rerank` logic

## Phase 5: Cost Tracking

**User Stories:** US5
**Goal:** Intercept LiteLLM usage metrics and log to SQLite store.

- [x] T015 [US5] Create `src/openreview_cli/gateway/cost.py` with `CostTracker` class wrapping database interactions
- [x] T016 [US5] Update `src/openreview_cli/gateway/router.py` to calculate costs using `litellm.completion_cost` and call `CostTracker.log_call` after successful `chat`, `embed`, and `rerank` calls
- [x] T017 [P] [US5] Create `tests/unit/test_gateway_cost.py` to test cost tracking integration

## Phase 6: Model Registry

**User Stories:** US6
**Goal:** Manage and refresh the curated model list.

- [x] T018 [US6] Create `src/openreview_cli/gateway/registry.py` with `ModelRegistry` class (`load`, `list_providers`, `list_models`)
- [x] T019 [US6] Implement `refresh` method in `registry.py` to fetch `models.json` from GitHub raw URL via `httpx`
- [x] T020 [US6] Implement dynamic Ollama discovery in `registry.py` by querying `http://localhost:11434/api/tags`
- [x] T021 [US6] Implement `health_check` method in `src/openreview_cli/gateway/router.py`
- [x] T022 [P] [US6] Create `tests/unit/test_gateway_registry.py` to test registry load and refresh

## Phase 7: Setup Wizard & CLI

**User Stories:** US4
**Goal:** Expose all gateway capabilities via the CLI and interactive wizard.

- [x] T023 [P] [US4] Create `src/openreview_cli/gateway/redaction.py` with `redact_key` utility
- [x] T024 [US4] Create `src/openreview_cli/gateway/wizard.py` implementing the interactive `gateway_setup()` function
- [x] T025 [US4] Update `src/openreview_cli/app.py` to add `gateway_app` Typer subcommand group
- [x] T026 [US4] Register `setup`, `status`, `providers`, `models`, `set`, `refresh`, `test`, `costs` commands in `app.py`
- [x] T027 [US4] Create `tests/integration/test_gateway_cli.py` to test CLI invocations and wizard flow

## Phase 8: Polish & Pre-Commit

- [x] T028 Run `uv run pre-commit run --all-files` and fix any formatting/typing issues
- [x] T029 Validate memory footprint under 100MB by updating `tests/integration/test_memory.py` to include a gateway init

## Phase 9: Convergence

- [X] T030 Wire `redact_key` utility into gateway logging and error output to ensure API keys are never exposed in logs, errors, or debug output per FR-006 (partial)
- [X] T031 Add cost limit check (`check_session_limit`/`check_daily_limit`) in `Gateway.chat/embed/rerank` before making API calls, with user-facing warning when limit would be exceeded per US5/AC2 (missing)
- [X] T032 Update `get_session_cost` query in `database.py` to group by `slot` so `Gateway.get_cost()` returns per-slot token/cost breakdown per US5/AC1 (partial)
- [X] T033 Add stale-registry check in `app._init()` that silently refreshes `models.json` when `model_registry_refresh_days` has elapsed per US6/AC3 (missing)
- [X] T034 Update `gateway models` CLI command to call `ModelRegistry.discover_ollama()` for Ollama provider and merge dynamic results into displayed model list per US6/AC2 (partial)
- [X] T035 Catch Ollama connection errors (`ConnectionError` / `ConnectError`) specifically in `router.py` and raise with message "Ollama not reachable at localhost:11434 — ensure Ollama is running" per US2/AC3 and EC-3 (partial)
- [X] T036 Add distinct error subclasses or error-message patterns to `router.py` for auth failures (invalid/expired API key), model-not-found, and network errors per EC-1 and EC-2 (partial)
- [X] T037 Add `VALID_SLOTS` validation to `gateway set` CLI command in `app.py` to reject invalid slot names before writing to config per FR-002 and FR-015 (partial)
- [X] T038 Create `tests/unit/test_gateway_redaction.py`, `tests/unit/test_gateway_wizard.py` (mocked prompts), and `tests/unit/test_gateway_models.py` (Pydantic model unit tests) per plan.md test structure (missing)
