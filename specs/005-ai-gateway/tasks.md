# Implementation Tasks: AI Gateway

**Feature**: 005-ai-gateway
**Status**: Ready for implementation

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

- [ ] T001 Add LiteLLM dependency via `uv add litellm` in the project root

## Phase 2: Foundational (Config & Storage)

Goal: Extend existing configuration models and database schema to support the gateway.

- [ ] T002 [P] Update `src/openreview_cli/config/loader.py` to add `extra_params: dict[str, Any] | None = None` to `ModelSlot`
- [ ] T003 Create `src/openreview_cli/storage/migrations/003_gateway.sql` to rename `review_id` to `session_id` and add `slot` column to `cost_logs` table
- [ ] T004 Update `src/openreview_cli/storage/database.py` to rename `review_id` parameter to `session_id` in `log_cost`, `check_daily_limit`, `check_review_limit`, and add `slot` parameter to `log_cost` and `get_session_cost` query
- [ ] T005 [P] Create `src/openreview_cli/gateway/models.py` with Pydantic models: `ProviderInfo`, `ModelEntry`, `CostRecord`
- [ ] T006 Create `src/openreview_cli/gateway/errors.py` with exception hierarchy: `GatewayError`, `ProviderError`, `SlotNotConfiguredError`, `AllProvidersFailedError`
- [ ] T007 Create `src/openreview_cli/gateway/__init__.py` exposing the core models and errors
- [ ] T008 [P] Create `src/openreview_cli/gateway/models.json` with static curated model list covering 8 providers

## Phase 3: Core Routing (Chat & Embed)

**User Stories:** US1, US2
**Goal:** Route completion and embedding requests with fallback logic.

- [ ] T009 [US1] Create `src/openreview_cli/gateway/router.py` with `Gateway` class, `__init__` (loading config and auth), and helper `_get_litellm_kwargs`
- [ ] T010 [US1] Implement `chat` method in `router.py` with primary/fallback retry logic, passing `extra_params` as kwargs
- [ ] T011 [US2] Implement `embed` method in `router.py`
- [ ] T012 [P] [US1] Create `tests/unit/test_gateway_router.py` and test `chat` and `embed` with mocked `litellm` calls

## Phase 4: Reranking

**User Stories:** US3
**Goal:** Expose reranking capabilities.

- [ ] T013 [US3] Implement `rerank` method in `src/openreview_cli/gateway/router.py`
- [ ] T014 [US3] Update `tests/unit/test_gateway_router.py` to test `rerank` logic

## Phase 5: Cost Tracking

**User Stories:** US5
**Goal:** Intercept LiteLLM usage metrics and log to SQLite store.

- [ ] T015 [US5] Create `src/openreview_cli/gateway/cost.py` with `CostTracker` class wrapping database interactions
- [ ] T016 [US5] Update `src/openreview_cli/gateway/router.py` to calculate costs using `litellm.completion_cost` and call `CostTracker.log_call` after successful `chat`, `embed`, and `rerank` calls
- [ ] T017 [P] [US5] Create `tests/unit/test_gateway_cost.py` to test cost tracking integration

## Phase 6: Model Registry

**User Stories:** US6
**Goal:** Manage and refresh the curated model list.

- [ ] T018 [US6] Create `src/openreview_cli/gateway/registry.py` with `ModelRegistry` class (`load`, `list_providers`, `list_models`)
- [ ] T019 [US6] Implement `refresh` method in `registry.py` to fetch `models.json` from GitHub raw URL via `httpx`
- [ ] T020 [US6] Implement dynamic Ollama discovery in `registry.py` by querying `http://localhost:11434/api/tags`
- [ ] T021 [US6] Implement `health_check` method in `src/openreview_cli/gateway/router.py`
- [ ] T022 [P] [US6] Create `tests/unit/test_gateway_registry.py` to test registry load and refresh

## Phase 7: Setup Wizard & CLI

**User Stories:** US4
**Goal:** Expose all gateway capabilities via the CLI and interactive wizard.

- [ ] T023 [P] [US4] Create `src/openreview_cli/gateway/redaction.py` with `redact_key` utility
- [ ] T024 [US4] Create `src/openreview_cli/gateway/wizard.py` implementing the interactive `gateway_setup()` function
- [ ] T025 [US4] Update `src/openreview_cli/app.py` to add `gateway_app` Typer subcommand group
- [ ] T026 [US4] Register `setup`, `status`, `providers`, `models`, `set`, `refresh`, `test`, `costs` commands in `app.py`
- [ ] T027 [US4] Create `tests/integration/test_gateway_cli.py` to test CLI invocations and wizard flow

## Phase 8: Polish & Pre-Commit

- [ ] T028 Run `uv run pre-commit run --all-files` and fix any formatting/typing issues
- [ ] T029 Validate memory footprint under 100MB by updating `tests/integration/test_memory.py` to include a gateway init
