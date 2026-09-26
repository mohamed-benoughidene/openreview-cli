# Tasks: SLM Model Params Extension

**Input**: Design documents from `/specs/006-slm-model-params/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/cli-contract.md

**Tests**: Included per project TDD mandate (AGENTS.md). All tests written FIRST, verified FAILING, then implementation.

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Exact file paths in descriptions

## Phase 1: Setup

**Purpose**: Verify baseline — no structural changes needed (all work is in existing files per plan.md)

- [X] T001 Verify existing gateway tests pass: `uv run pytest tests/unit/test_gateway_models.py tests/unit/test_gateway_router.py -q`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core model changes that all user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T002 [P] Add `extra_params: dict[str, Any] | None = None` field to `ModelEntry` in `src/openreview_cli/gateway/models.py`
- [X] T003 [P] Define `_PROTECTED_KEYS = frozenset({"model", "messages", "input", "timeout"})` in `src/openreview_cli/gateway/router.py`

**Checkpoint**: Model foundation ready — user story implementation can now begin

---

## Phase 3: User Story 1 — Pass Provider-Specific Params to Local SLMs (Priority: P1) 🎯 MVP

**Goal**: Users configure `extra_params` (e.g. `num_gpu`, `num_ctx`) on Ollama model slots in `config.yml`. These params pass through to LiteLLM. Protected keys are stripped. Debug/warning logs emitted.

**Independent Test**: `uv run pytest tests/unit/test_gateway_router.py -q -k "extra_params"` — all extra_params-related tests pass.

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T004 [P] [US1] Add ModelEntry extra_params tests (construction with/without field, serialization of nested dicts, `None` default) in `tests/unit/test_gateway_models.py`
- [X] T005 [P] [US1] Add extra_params pass-through tests (keys appear in LiteLLM kwargs, missing key → no extra keys, empty dict → no extra keys, nested values pass through, extra_params overrides standard params) in `tests/unit/test_gateway_router.py`
- [X] T006 [P] [US1] Add protected key stripping tests (model/messages/input/timeout stripped before merge, non-dict silently ignored) in `tests/unit/test_gateway_router.py`
- [X] T007 [P] [US1] Add extra_params logging tests (DEBUG message when extra_params applied listing keys, WARNING message when protected keys stripped) in `tests/unit/test_gateway_router.py`

### Implementation for User Story 1

- [X] T008 [US1] Implement protected-key stripping in `_get_litellm_kwargs()` — add filtering dict comprehension before `kwargs.update(extra)` in `src/openreview_cli/gateway/router.py`
- [X] T009 [US1] Add DEBUG-level logging for applied extra_params keys and WARNING-level logging for stripped protected keys in `src/openreview_cli/gateway/router.py`

**Checkpoint**: US1 functional — extra_params pass-through works, protected keys stripped, logs emitted. MVP complete.

---

## Phase 4: User Story 2 — Cloud Providers Ignore Irrelevant Extra Params (Priority: P2)

**Goal**: Stale extra_params from a previous provider (e.g. `num_gpu` on an OpenAI slot) do not crash the call.

**Independent Test**: Configuring Ollama-specific `extra_params` on an OpenAI model slot and verifying the call completes without exception.

### Tests for User Story 2 ⚠️

- [X] T010 [US2] Add cross-provider extra_params safety test (Ollama-specific keys on OpenAI slot → call completes, no exception raised) in `tests/unit/test_gateway_router.py`

**Checkpoint**: US2 confirmed — grace period covers stale config during provider switching. No new implementation code needed (US1 implementation handles this — LiteLLM forwards unknown kwargs).

---

## Phase 5: User Story 3 — View Active Extra Params in Health Check (Priority: P3)

**Goal**: `health_check()` output includes `"extra_params": N` for slots with extra_params configured.

**Independent Test**: `uv run pytest tests/unit/test_gateway_router.py -q -k "health"` — health check tests pass including extra_params count.

### Tests for User Story 3 ⚠️

- [X] T011 [US3] Add health check extra_params tests (slot with extra_params → output includes count, slot without → no extra_params key, verifiable in unit test) in `tests/unit/test_gateway_router.py`

### Implementation for User Story 3

- [X] T012 [US3] Add extra_params count to `health_check()` output in `src/openreview_cli/gateway/router.py` — after determining slot status, add `"extra_params": N` if slot config has extra_params dict

**Checkpoint**: US3 functional — health check reports extra_params count per slot.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final validation, docs, and regression check

- [X] T013 [P] Add extra_params examples for Ollama models in `src/openreview_cli/gateway/models.json` (at least 2 Ollama entries demonstrating num_gpu, num_ctx, options)
- [X] T014 Run full regression: `uv run pytest tests/unit/test_gateway_models.py tests/unit/test_gateway_router.py -q`
- [X] T015 Run mypy strict check: `uv run mypy src/openreview_cli/gateway/models.py src/openreview_cli/gateway/router.py --strict`
- [X] T016 Run quickstart validation scenarios per `specs/006-slm-model-params/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — verify baseline first
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Phase 2 — MVP, must complete first
- **User Story 2 (Phase 4)**: Depends on Phase 3 (reuses same implementation)
- **User Story 3 (Phase 5)**: Depends on Phase 2 (independent of US1/US2 implementation)
- **Polish (Phase 6)**: Depends on all user stories complete

### User Story Dependencies

- **US1 (P1)**: No dependencies on other stories — can start after Phase 2
- **US2 (P2)**: Depends on US1 implementation (same `_get_litellm_kwargs()` code handles both). No additional implementation code needed.
- **US3 (P3)**: Independent — can start after Phase 2, parallel with US1 if desired

### Within Each User Story

- Tests MUST be written and FAIL before implementation (TDD per AGENTS.md)
- Tests before implementation within each phase
- T008 depends on T005, T006, T007 (tests first)
- T009 depends on T007 (logging test)
- T012 depends on T011

### Parallel Opportunities

- **Phase 2**: T002 (models.py) and T003 (router.py) — different files, parallel
- **Phase 3 tests**: T004, T005, T006, T007 — all different test areas, fully parallel
- **Phase 6**: T013, T014, T015, T016 — independent concerns, parallel

---

## Phase 7: Convergence

**Purpose**: Align spec edge-case description with actual behavior

- [X] T017 Update spec.md Edge Cases entry for non-dict `extra_params` — replace "Ignored silently; a debug-level log message is emitted" with "Rejected at config load time by Pydantic `ValidationError` (defined as `dict[str, Any] | None` on `ModelSlot`)" per spec.md Edge Cases (`contradicts`)

---

## Parallel Example: Phase 3 (US1) Tests

```bash
# Launch all US1 tests in parallel:
Task: "Add ModelEntry extra_params tests in tests/unit/test_gateway_models.py"
Task: "Add extra_params pass-through tests in tests/unit/test_gateway_router.py"
Task: "Add protected key stripping tests in tests/unit/test_gateway_router.py"
Task: "Add extra_params logging tests in tests/unit/test_gateway_router.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1: T001 — verify baseline passing
2. Phase 2: T002 + T003 — ModelEntry field + protected keys constant
3. Phase 3: T004–T007 (tests) → T008–T009 (implementation)
4. **STOP and VALIDATE**: US1 independently testable, all tests green
5. MVP ready — extra_params pass-through with protected key stripping

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. US1 → Test independently → MVP (extra_params pass-through, protected key stripping, logging)
3. US2 → Test independently → Safety net confirmed
4. US3 → Test independently → Health check visibility
5. Polish → Regression, types, quickstart validation → Feature complete
