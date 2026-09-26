---
description: "Task list for Privacy Tier Routing implementation"
---

# Tasks: Privacy Tier Routing (020)

**Input**: Design documents from `specs/020-privacy-tier-routing/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md, constitution

**Tests**: Required per project TDD policy — tests written BEFORE implementation code. Each test task MUST fail before its corresponding implementation task.

**Organization**: Tasks grouped by phase: Setup → Foundational (blocks all stories) → User stories by priority (P1 → P2 → P3) → Polish. Each user story independently testable.

## Format: `[ID] [P?] [Story] Description with file path`

- **[P]**: Parallel — different files, no dependencies
- **[Story]**: Which user story this task belongs to (FND=Foundational, US1-5=User Stories, POL=Polish)
- **TDD ordering**: Test tasks before implementation tasks within each phase/story

**Note**: Task context file at `.specify/memory/task-context.md` exists independently for feature 020. All paths below verified against live filesystem scan.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create skeleton structure and test fixture files that all phases depend on.

- [X] T001 [P] [SETUP] Create 3 tier config fixture YAMLs at `tests/fixtures/config_tier_maximum.yml`, `tests/fixtures/config_tier_balanced.yml`, `tests/fixtures/config_tier_performance.yml`
- [X] T002 [P] [SETUP] Create empty source file stubs at `src/openreview_cli/gateway/tier_router.py`, `src/openreview_cli/gateway/tier_config.py`

---

## Phase 2: Foundational — Blocking Prerequisites

**Purpose**: Core types, enums, errors, and utilities that ALL user stories depend on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

**Independent Test**: Run `pytest tests/unit/test_tier_config.py tests/unit/test_tier_router.py tests/unit/test_gateway_errors.py -v` — every test must pass.

### 🧪 Tests (write FIRST, expect failure)

- [X] T003 [P] [FND] **Test PrivacyTier enum values, string parsing, case-insensitivity** in `tests/unit/test_tier_config.py`
- [X] T004 [P] [FND] **Test TierConfig.from_config()** with valid/missing/invalid values, default-to-Maximum behavior, warning propagation in `tests/unit/test_tier_config.py`
- [X] T005 [P] [FND] **Test ProviderLocationClassifier** URL-based classification (localhost, 127.0.0.1, Unix socket, external URL) in `tests/unit/test_tier_router.py`
- [X] T006 [P] [FND] **Test PiiEngine.is_available()** readiness check — returns True on success, False on engine failure in `tests/unit/test_pii_engine.py`
- [X] T007 [P] [FND] **Test PIIUnavailableError and NoMatchingProviderError** — error formatting, actionable suggestions, no raw text leakage in `tests/unit/test_gateway_errors.py`

### 🏗️ Implementation

- [X] T008 [P] [FND] Add `PrivacyTier` enum and `PrivacyTierReport` dataclass (with `progress_banner()`, `report_footer()`) to `src/openreview_cli/gateway/models.py`
- [X] T009 [P] [FND] Add `TierRoutingError`, `PIIUnavailableError`, `NoMatchingProviderError` to `src/openreview_cli/gateway/errors.py`
- [X] T010 [P] [FND] Implement `TierConfig` dataclass with `from_config()` factory (reads `privacy.tier`, defaults to Maximum, validates) in `src/openreview_cli/gateway/tier_config.py`
- [X] T011 [P] [FND] Implement `ProviderLocationClassifier` as a static method on `TierRouter` — `TierRouter.classify_provider(provider_config)` using `urllib.parse.urlparse()` — localhost patterns return LOCAL, all else CLOUD in `src/openreview_cli/gateway/tier_router.py`
- [X] T012 [FND] Add `PiiEngine.is_available()` instance method to existing `PiiEngine` class — lightweight `analyze("test")` probe, per-operation cached result. Implementation in `src/openreview_cli/pii/engine.py`.
- [X] T013a [FND] Wire gateway exports: add `TierRouter`, `TierConfig`, `PrivacyTier`, `PrivacyTierReport`, `PIIUnavailableError`, `NoMatchingProviderError` to `src/openreview_cli/gateway/__init__.py`
- [X] T013b [FND] Wire PII export: add `is_available` to `src/openreview_cli/pii/__init__.py`

**Checkpoint**: Foundation ready — enums parse, config loads, providers classify, PII readiness probes, errors render. All 5 foundational tests pass.

---

## Phase 3: User Story 1 — Maximum Tier (Priority: P1) 🎯 MVP

**Goal**: All inference runs locally via Ollama. Zero network calls to external services. Cloud providers are blocked with actionable error.

**Independent Test**: Set `privacy.tier: maximum`, configure both local + cloud providers, call `router.chat()` and `router.embed()`. Assert: cloud calls raise `NoMatchingProviderError`, local calls succeed, zero HTTP requests to external hosts.

### 🧪 Tests (write FIRST, expect failure)

- [X] T014 [P] [US1] **Test Maximum tier rejects cloud provider call** — `router.chat()` with cloud-only config raises `NoMatchingProviderError` with tier-specific message in `tests/unit/test_tier_router.py`
- [X] T015 [P] [US1] **Test Maximum tier allows local provider call** — `router.chat()` with local-only config passes through to Gateway in `tests/unit/test_tier_router.py`
- [X] T016 [US1] **Test Maximum tier zero external HTTP requests** — integration with mocked providers, assert no HTTP request to non-localhost URL in `tests/integration/test_privacy_tier.py`

### 🏗️ Implementation

- [X] T017 [US1] Implement `TierRouter.__init__(gateway, config)` and `TierRouter.chat()` — filter providers by tier rules, raise `NoMatchingProviderError` if no eligible provider in `src/openreview_cli/gateway/tier_router.py`
- [X] T018 [US1] Implement `TierRouter.embed()` — same filtering logic as chat, wraps `Gateway.embed()` in `src/openreview_cli/gateway/tier_router.py`
- [X] T019 [US1] Wire `PrivacyTierReport.progress_banner()` into review pipeline output — inject `PrivacyTierReport` into `review/base.py` `ReviewCommand` report object, display banner near start of progress output

**Checkpoint**: US1 complete — Maximum tier enforces local-only routing. Tier banner visible. 3 unit tests + 1 integration test pass.

---

## Phase 4: User Story 2 — Balanced Tier (Priority: P1)

**Goal**: Embeddings route to local providers. LLM calls route to cloud providers, but only after PII is stripped from input text.

**Independent Test**: Set `privacy.tier: balanced`, configure local embedding + cloud LLM providers. Call `router.embed()` (resolves local), `router.chat()` (resolves cloud with PII-stripped input). Assert: embedding call hits local provider, cloud LLM input contains no raw PII.

### 🧪 Tests (write FIRST, expect failure)

- [X] T020 [P] [US2] **Test Balanced routes embeddings to local provider** — `router.embed()` with local+cloud config resolves local in `tests/unit/test_tier_router.py`
- [X] T021 [P] [US2] **Test Balanced routes LLM to cloud with PII stripped** — `router.chat()` resolves cloud, input is PII-stripped (verify via mock capture), raw PII absent in `tests/unit/test_tier_router.py`
- [X] T022 [US2] **Test Balanced tier integration** — full pipeline with mocked providers and seeded PII document, assert embedding=local, LLM=cloud, PII stripped in `tests/integration/test_privacy_tier.py`

### 🏗️ Implementation

- [X] T023 [US2] Add Balanced routing logic to `TierRouter.chat()` and `TierRouter.embed()` — LLM → cloud allowed; embedding → local only; PII verification gate before cloud dispatch in `src/openreview_cli/gateway/tier_router.py`

**Checkpoint**: US2 complete — Balanced tier routes by call type. PII verified before cloud egress. 2 unit tests + 1 integration test pass.

---

## Phase 5: User Story 3 — Performance Tier (Priority: P1)

**Goal**: All inference routes to cloud providers for maximum throughput. PII stripped before every cloud call.

**Independent Test**: Set `privacy.tier: performance`, configure cloud providers for all model types. Call `router.embed()` and `router.chat()`. Assert: both resolve to cloud, both inputs PII-stripped.

### 🧪 Tests (write FIRST, expect failure)

- [X] T024 [P] [US3] **Test Performance routes all calls to cloud** — `router.chat()` and `router.embed()` with cloud config resolve cloud in `tests/unit/test_tier_router.py`
- [X] T025 [P] [US3] **Test Performance strips PII before every call** — both embedding and LLM inputs are PII-stripped in `tests/unit/test_tier_router.py`
- [X] T026 [US3] **Test Performance tier integration** — all calls cloud, PII stripped, output shows "PERFORMANCE" banner in `tests/integration/test_privacy_tier.py`

### 🏗️ Implementation

- [X] T027 [US3] Add Performance routing logic to `TierRouter.chat()` and `TierRouter.embed()` — all providers allowed (including cloud), PII verification gate before every dispatch in `src/openreview_cli/gateway/tier_router.py`

**Checkpoint**: US3 complete — Performance tier routes all to cloud. PII stripped before all calls. 2 unit tests + 1 integration test pass.

---

## Phase 6: User Story 4 — PII Engine Failure Blocks Cloud Calls (Priority: P2)

**Goal**: When PII engine is unavailable, cloud calls are blocked with actionable error. Fail-closed. Maximum tier unaffected.

**Independent Test**: Mock `PiiEngine.is_available()` → `False`. Set Balanced tier, call `router.chat()`. Assert: `PIIUnavailableError` raised, no HTTP request made, error includes actionable suggestions. Same setup on Maximum tier: call succeeds.

### 🧪 Tests (write FIRST, expect failure)

- [X] T028 [P] [US4] **Test PIIUnavailableError raised when engine fails on Balanced** — `router.chat()` with PII unavailable raises error, no cloud call dispatched in `tests/unit/test_tier_router.py`
- [X] T029 [P] [US4] **Test Maximum tier unaffected by PII failure** — `router.chat()` with PII unavailable on Maximum tier proceeds normally in `tests/unit/test_tier_router.py`
- [X] T030 [P] [US4] **Test PII failure error contains actionable suggestions** — error message includes "PII", ≥2 actionable suggestions, no document text in `tests/unit/test_tier_router.py`
- [X] T031 [US4] **Test PII failure integration** — mock PII unavailable across Balanced and Performance tiers, verify fail-closed, Maximum unaffected in `tests/integration/test_privacy_tier_pii.py`

### 🏗️ Implementation

- [X] T032 [US4] Add PII verification gate before cloud dispatch — call `PiiEngine.is_available()` (added to `pii/engine.py` in T012), raise `PIIUnavailableError` if unavailable in `src/openreview_cli/gateway/tier_router.py`
- [X] T033 [US4] Build actionable error messages for `PIIUnavailableError` — include 3 suggestions (switch to Maximum, fix PII engine, use --no-pii with caution) in `src/openreview_cli/gateway/errors.py`

**Checkpoint**: US4 complete — PII failure blocks cloud calls with actionable error. Maximum tier still works. 3 unit tests + 1 integration test pass.

---

## Phase 7: User Story 5 — Tier Stability Per Operation (Priority: P3)

**Goal**: Tier is captured at operation start. Changes to `config.yml` mid-operation do not affect the running operation. Current tier always displayed.

**Independent Test**: Start operation with Balanced tier, change `config.yml` to Maximum during operation, assert operation continues under Balanced. Next invocation picks up Maximum.

### 🧪 Tests (write FIRST, expect failure)

- [X] T034 [P] [US5] **Test TierConfig captured once at construction** — `TierConfig` loaded at init, does not re-read config on repeated calls in `tests/unit/test_tier_config.py`
- [X] T035 [US5] **Test config change mid-operation does not affect running op** — integration test with temp config, change tier mid-mock-operation, assert op uses original tier in `tests/integration/test_privacy_tier.py`
- [X] T036 [US5] **Test subsequent operation picks up new tier** — after config change, next `TierConfig.from_config()` returns new tier in `tests/unit/test_tier_config.py`

### 🏗️ Implementation

- [X] T037 [US5] Ensure `TierConfig` is constructed once at operation start and stored in `TierRouter` — no re-read of config during operation lifetime in `src/openreview_cli/gateway/tier_router.py`
- [X] T038 [US5] Wire `PrivacyTierReport` into final pipeline report — inject `PrivacyTierReport.report_footer()` into `review/report.py` `ReviewReport` object, show tier summary in output footer for all tiers

**Checkpoint**: US5 complete — tier stable per operation. Changes deferred to next invocation. 2 unit tests + 1 integration test pass.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Validation, hardening, and verification across all user stories.

- [X] T039 [P] [POL] Run quickstart.md validation scenarios — execute all 6 validation scenarios end-to-end
- [X] T040 [P] [POL] Memory profile test — assert TierRouter overhead <5 MB peak (<100 MB total, NLP model exempt) in `tests/integration/test_privacy_tier.py` or `tests/unit/test_tier_router.py` via `memory_tracker` fixture
- [X] T041 [P] [POL] Run full pre-commit suite — `ruff check --fix`, `ruff format`, `mypy --strict`, `pytest -m "not slow and not integration"`
- [X] T042 [P] [POL] Update module docstrings for all new files (`tier_router.py`, `tier_config.py`) and modified files (`models.py`, `errors.py`, `pii/engine.py`)
- [X] T043 [POL] Verify `PrivacyTierReport` output in final report for all 3 tiers — confirm banner displays tier name + description, footer includes tier summary + entity count

---

## Dependencies & Execution Order

### Phase Dependencies

```
Setup (Phase 1)
  └─► Foundational (Phase 2) — BLOCKS all user stories
        ├─► US1: Maximum Tier (Phase 3) — 🎯 MVP
        ├─► US2: Balanced Tier (Phase 4)
        ├─► US3: Performance Tier (Phase 5)
        ├─► US4: PII Failure Block (Phase 6)
        └─► US5: Tier Stability (Phase 7)
              └─► Polish (Phase 8)
```

### User Story Dependencies

| Story | Priority | Depends On | Independent Test |
|-------|----------|------------|------------------|
| US1 (Maximum) | P1 🎯 | Phase 2 (Foundation) | Zero external HTTP on Maximum tier |
| US2 (Balanced) | P1 | Phase 2, US1 (TierRouter structure) | Embeddings local, LLM cloud, PII stripped |
| US3 (Performance) | P1 | Phase 2, US1 (TierRouter structure) | All calls cloud, PII stripped |
| US4 (PII Failure) | P2 | Phase 2, US2 (PII gate logic) | Fail-closed on PII unavailable |
| US5 (Stability) | P3 | Phase 2, US1 (TierConfig lifecycle) | Tier stable per operation |

**Note**: US2 and US3 depend on the TierRouter skeleton from US1 but add independent routing logic. They can proceed in parallel after US1 is complete.

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Models/enums before services
- Services before wiring/integration
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently

### Execution Order (Sequential)

1. **Phase 1** Setup → commit
2. **Phase 2** Foundational (blocks all) → commit, validate
3. **Phase 3** US1 Maximum (MVP) → commit, validate independently
4. **Phase 4** US2 Balanced → commit, validate independently
5. **Phase 5** US3 Performance → commit, validate independently
6. **Phase 6** US4 PII Failure → commit, validate independently
7. **Phase 7** US5 Stability → commit, validate independently
8. **Phase 8** Polish → commit, final validation

### Parallel Opportunities

| Tasks | Run Together |
|-------|-------------|
| T001, T002 (Setup) | ✅ Parallel — different files |
| T003-T007 (Foundation tests) | ✅ Parallel — different test files |
| T008-T011 (Foundation models) | ✅ Parallel — different source files (T011 unified into tier_router.py) |
| T014, T015 (US1 tests) | ✅ Parallel — same file, different functions |
| T020, T021 (US2 tests) | ✅ Parallel — same file, different functions |
| T024, T025 (US3 tests) | ✅ Parallel — same file, different functions |
| T028, T029, T030 (US4 tests) | ✅ Parallel — same file, different functions |
| T039, T040, T041, T042 (Polish) | ✅ Parallel — different concerns |

### Execution Strategy

```bash
# Phase 1: Setup
# T001 (config YAML fixtures) + T002 (source stubs) in parallel

# Phase 2: Foundation tests in parallel
uv run pytest tests/unit/test_tier_config.py tests/unit/test_gateway_errors.py tests/unit/test_pii_engine.py tests/unit/test_tier_router.py -v

# Phase 3: US1 tests in parallel
uv run pytest tests/unit/test_tier_router.py::test_maximum_rejects_cloud tests/unit/test_tier_router.py::test_maximum_allows_local -v

# Phase 3-5: Story implementation + verification
uv run pytest tests/unit/test_tier_router.py tests/unit/test_tier_config.py -v
uv run pytest tests/integration/test_privacy_tier.py -v

# Final: Polish
uv run pre-commit run --all-files
```

---

## Extension Hooks

### Hook: US2 PII Verification Gate

When implementing T032 (PII verification gate), the implementation MUST:
- Call `PiiEngine.is_available()` once per operation (cache result)
- Use cached PII-stripped text when the same document is referenced by multiple cloud calls
- Raise `PIIUnavailableError` (not generic `RuntimeError`)
- Include ≥2 actionable suggestions in error message
- Never log raw document text, even in error paths

### Hook: US5 Tier Change Detection (Deferred)

Per CL-05 resolution, the "changed from X since last operation" diff notification is DROPPED from MVP. If explicitly requested later:
- Add a state file at `~/.config/openreview/.last_tier` containing the tier from the last operation
- On next operation, compare current tier to last tier
- Display "Tier changed from {old} to {new}" if different
- Implementation: new file `src/openreview_cli/gateway/tier_tracker.py` with `TierTracker` class
- This hook is dormant — do not implement unless explicitly requested

### Hook: Model Registry Local Flag Enhancement (Deferred)

If the Model Registry schema is revised independently:
- Add optional `local: bool` field to provider model definitions
- `TierRouter.classify_provider()` (the ProviderLocationClassifier static method) should check this flag BEFORE URL inspection
- No changes needed for MVP — URL-based classification covers all current cases
- This hook is dormant — do not implement unless Model Registry changes land

---

## Phase 9: Convergence — Gaps from Codebase Assessment

**Purpose**: Close gaps found during speckit.converge assessment (2026-07-05). Core enforcement is implemented and passing; these are the remaining items for complete spec conformance.

**GAP-01 [RESOLVED]**: `PrivacyTierReport` dataclass exists in `gateway/models.py` with `progress_banner()` and `report_footer()`. Tier visibility in user-facing output fully implemented (FR-08, SC-05, T019, T038, T043).

**GAP-02 [RESOLVED]**: `PrivacyTier` and `PrivacyTierReport` both exported from `gateway/__init__.py`. Callers can `from openreview_cli.gateway import PrivacyTier`.

**GAP-03 [RESOLVED]**: `PrivacyTierReport.progress_banner()` wired into `review/base.py` (line 45). `report_footer()` wired into `review/report.py` via `privacy_footer` parameter (lines 69-71, 159-160).

**GAP-04 [RESOLVED]**: T040 (memory profile test) implemented — `TestTierRouterMemory.test_maximum_tier_peak_memory_budget` in `tests/unit/test_tier_router.py` uses `tracemalloc` to assert TierRouter overhead <5 MB peak.

### 🧪 Tests (write FIRST)

- [X] T044 [P] [CVG] **Test PrivacyTierReport.progress_banner()** — returns tier name + description for each tier, includes "local only" for Maximum, "PII stripped" for Balanced/Performance in `tests/unit/test_tier_config.py` or new `tests/unit/test_tier_report.py`
- [X] T045 [P] [CVG] **Test PrivacyTierReport.report_footer()** — returns tier summary + cloud call count + PII entity count for each tier in `tests/unit/test_tier_config.py` or new `tests/unit/test_tier_report.py`
- [X] T046 [P] [CVG] **Test PrivacyTier exported from gateway/__init__.py** — `from openreview_cli.gateway import PrivacyTier` resolves, values match `PrivacyTier.MAXIMUM == "maximum"` in `tests/unit/test_tier_config.py`
- [X] T047 [CVG] **Test review pipeline displays tier banner** — capture progress output from `ReviewCommand` (mocked) on each tier, assert banner appears with tier name in `tests/integration/test_privacy_tier.py` or new `tests/integration/test_tier_visibility.py`
- [X] T048 [CVG] **Test final report includes tier footer** — capture `ReviewReport` output for each tier, assert footer includes tier summary in `tests/integration/test_privacy_tier.py` or new `tests/integration/test_tier_visibility.py`

### 🏗️ Implementation

- [X] T049 [P] [CVG] Add `PrivacyTierReport` dataclass to `src/openreview_cli/gateway/models.py` with:
  - `tier: str` — the tier name
  - `cloud_calls_made: int = 0` — count of cloud calls dispatched
  - `pii_entities_stripped: int = 0` — count of PII entities redacted
  - `progress_banner() -> str` — returns one-line banner e.g. "Privacy tier: MAXIMUM — all inference local"
  - `report_footer() -> str` — returns multi-line footer with tier summary, e.g. "Processed under Maximum privacy tier. No data was sent to external services."
  - Banner/footer messages match spec examples in §2 Scenarios 1-3
- [X] T050 [CVG] Export `PrivacyTierReport` and `PrivacyTier` from `src/openreview_cli/gateway/__init__.py` — add to imports and `__all__`
- [X] T051 [CVG] Wire `PrivacyTierReport.progress_banner()` into `src/openreview_cli/review/base.py` — inject into `ReviewCommand` run flow, display near start of progress output
- [X] T052 [CVG] Wire `PrivacyTierReport.report_footer()` into `src/openreview_cli/review/report.py` — inject into `ReviewReport` output, show tier summary in footer for all tiers

**Convergence Checkpoint**: All 4 gaps closed (GAP-01/02/03/04 RESOLVED). FR-01 through FR-09 fully implemented. SC-01 through SC-07 verifiable. All 53 tasks completed — 5 convergence tests (T044-T048) + 4 convergence implementation tasks (T049-T052) + memory profile (T040) all passing. Run `uv run pre-commit run --all-files` before final commit.

## Task Summary (Updated)

| Phase | Tasks | Tests | Impl | Priority |
|-------|-------|-------|------|----------|
| Phase 1: Setup | T001-T002 | 0 | 2 | Blocking |
| Phase 2: Foundational | T003-T013b | 5 | 7 | Blocking |
| Phase 3: US1 Maximum 🎯 | T014-T019 | 3 | 3 | P1 MVP |
| Phase 4: US2 Balanced | T020-T023 | 3 | 1 | P1 |
| Phase 5: US3 Performance | T024-T027 | 3 | 1 | P1 |
| Phase 6: US4 PII Failure | T028-T033 | 4 | 2 | P2 |
| Phase 7: US5 Stability | T034-T038 | 3 | 2 | P3 |
| Phase 8: Polish | T039-T043 | 1 | 0+5 | Final |
| **Phase 9: Convergence** | **T044-T052** | **5** | **4** | **Blocking — ALL resolved** |
| **Total** | **T001-T052** | **27** | **22+5** | **53/53 [X], 0 [ ]** |

**Total**: 53 tasks (27 test tasks + 22 implementation tasks + 4 polish tasks)

**Updated 2026-07-05**: Convergence phase appended after codebase assessment. Core routing enforcement (63 tests) already passing. Gaps: PrivacyTierReport dataclass, tier visibility in pipeline output, missed exports.

**MVP scope**: Phases 1-3 (T001-T019): Setup → Foundational → US1 Maximum tier. 19 tasks for a testable, deployable Maximum-tier feature.
