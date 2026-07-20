---
description: "Task list for spec 034 — Multi-Field Provider Credential Support"
---

# Tasks: 034 — Multi-Field Provider Credential Support

**Input**: Design documents from `/specs/034-multifield-provider-auth/`
(plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md)

**Prerequisites**: plan.md, spec.md (FR-1..FR-7), research.md (Q1–Q5 resolved),
data-model.md, contracts/provider-model.md, contracts/cli-contract.md.

**Tests**: Included (TDD per repo AGENTS.md; spec Success Criteria 5 requires new
unit + integration tests). Spec FRs map to user-story phases below.

**Grounding**: All file paths verified against the real filesystem
(see `.specify/memory/task-context.md` — no MISMATCH). Dependency versions
confirmed via Context7 (litellm v1.81.x, pydantic v2, typer 0.21.x).

**Organization**: FRs grouped into 4 user stories (US1 MVP model, US2 registry+kwarg
mapping, US3 per-field health, US4 wizard/CLI collection).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1..US4
- Exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: No new project scaffolding needed — repo + deps already present.
Confirm grounding artifacts and tooling.

- [x] T001 Verify Context7-verified sources present at `.specify/memory/verified-sources.md` (litellm/pydantic/typer) before implementing — CONFIRMED (verified-sources.md + task-context.md present 2026-07-20)
- [x] T002 [P] Confirm `uv run pre-commit run --all-files` passes on current branch as the baseline — CONFIRMED green 2026-07-20

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The `CredentialField` model + `ProviderInfo.credentials` extension that
every user story depends on.

**⚠️ CRITICAL**: US2/US3/US4 cannot start until T003–T006 land.

- [x] T003 [P] Add `CredentialField` pydantic model in `src/openreview_cli/gateway/models.py` (fields: env_key, label, secret, required, litellm_param, is_file_path) per contracts/provider-model.md — DONE (models.py:17, commit e5d05ab merged)
- [x] T004 [P] Extend `ProviderInfo` with `credentials: list[CredentialField] = []` in `src/openreview_cli/gateway/models.py` (backward-compatible default, FR-1/FR-2) — DONE (models.py:42, merged)
- [x] T005 [P] Ensure `load_registry()` in `src/openreview_cli/gateway/registry.py` tolerates providers without a `credentials` key (pydantic default) — no API change — DONE (_build_provider + ModelRegistry.load forward credentials raw list, default [], registry.py:33/43/130/136, merged 4aa729d)
- [x] T006 [P] Unit test `ProviderInfo` backward compat + `CredentialField` in `tests/unit/test_gateway_models.py` (single-key provider loads with credentials==[]; CredentialField constructs) — DONE (TestCredentialField + ProviderInfo cred tests; 36 passed models+registry)

**Checkpoint**: Model layer ready. US1 complete (model half of FR-1/FR-2).

---

## Phase 3: User Story 1 — Credential Model + Backward Compat (Priority: P1) 🎯 MVP

**Goal**: `ProviderInfo` accepts `credentials: list[CredentialField]`; single-key
providers load unchanged (FR-1, FR-2).

**Independent Test**: `tests/unit/test_gateway_models.py` — a provider serialized
without `credentials` re-loads with `credentials == []`; existing `openai` entry from
`models.json` still loads via `load_registry()`.

### Tests for User Story 1
- [x] T007 [P] [US1] Test `CredentialField` construction + `model_dump()` includes `credentials` in `tests/unit/test_gateway_models.py` — SATISFIED by Phase 2 T006 (TestCredentialField @models.py:55, model_dump round-trip @:78/:108)
- [x] T008 [P] [US1] Test `ProviderInfo` without `credentials` loads with `[]` default in `tests/unit/test_gateway_models.py` — SATISFIED by Phase 2 T006 (assert p.credentials==[] @models.py:98)
- [x] T009 [P] [US1] Test `load_registry()` returns single-key providers with empty `credentials` in `tests/unit/test_gateway_registry.py` — SATISFIED by Phase 2 T006 (test_build_provider_without_credentials_defaults_empty @registry.py:418)`

### Implementation for User Story 1
- [x] T010 [US1] Finalize `CredentialField` + `ProviderInfo.credentials` in `src/openreview_cli/gateway/models.py` (depends on T003, T004) — DONE in Phase 2 (models.py:17/42, merged e5d05ab)
- [x] T011 [US1] Run `tests/unit/test_gateway_models.py` and `tests/unit/test_gateway_registry.py` green — DONE Phase 2 (36 passed, pre-commit clean)

**Checkpoint**: US1 fully functional and testable independently.

---

## Phase 4: User Story 2 — Kwarg Mapping + 3 Provider Registry Entries (Priority: P1)

**Goal**: `Gateway._get_litellm_kwargs` maps each `CredentialField` to its litellm
kwarg; bedrock/vertex/azure entries added to `models.json` and healthy only when
required env vars resolve (FR-3, FR-6).

**Independent Test**: Unit — with `AWS_REGION_NAME=us-east-1` set,
`_get_litellm_kwargs(slot="bedrock")` yields `kwargs["aws_region_name"]=="us-east-1"`.
Single-key provider → no extra kwargs.

### Tests for User Story 2
- [x] T012 [P] [US2] Unit test `_get_litellm_kwargs` injects `aws_region_name` from credential field in `tests/unit/test_gateway_router.py` — DONE (test asserts kwargs["aws_region_name"]=="us-east-1", merged ea6188e)
- [x] T013 [P] [US2] Unit test single-key provider yields no extra credential kwargs (backward compat) in `tests/unit/test_gateway_router.py` — DONE (asserts no aws_/vertex_/api_key when credentials==[], merged ea6188e)
- [x] T014 [P] [US2] Unit test bedrock/vertex/azure entries load via `load_registry()` and report `configured=False` until env set, in `tests/unit/test_gateway_registry.py` — DONE (test_registry_loads_multifield_providers_unconfigured, merged da6d899)
- [x] T015 [P] [US2] Integration: `tests/integration/test_provider_live.py` — live Bedrock `Gateway.chat` with real creds, skipped otherwise — DONE (1 skipped, no AWS creds, expected per STOP #2; commit 2020576)

### Implementation for User Story 2
- [x] T016 [US2] Extend `Gateway._get_litellm_kwargs` in `src/openreview_cli/gateway/router.py` to loop `info.credentials` and set `kwargs[field.litellm_param] = env_or_auth(field)` (depends on T010) — DONE (_apply_provider_credentials at router.py:166, called :208, merged ea6188e)
- [x] T017 [US2] Add `auth` resolution helper in `src/openreview_cli/gateway/router.py`: `os.environ.get(field.env_key) or self._auth.get(info.name, {}).get(field.env_key)` — DONE (env-first then auth.json dict, isinstance guard, router.py:173-180)
- [x] T018 [US2] Add bedrock entry (3 creds) to `src/openreview_cli/gateway/models.json` per contracts/provider-model.md — DONE (models.json bedrock, merged da6d899)
- [x] T019 [US2] Add vertex entry (project/location/ADC file-path cred) to `src/openreview_cli/gateway/models.json` — DONE (vertex, is_file_path=true ADC, merged da6d899)
- [x] T020 [US2] Add azure entry (base_url endpoint + key/api_version creds) to `src/openreview_cli/gateway/models.json` — DONE (azure, merged da6d899)
- [x] T021 [US2] Run router + registry unit tests and `tests/integration/test_provider_live.py` (skipped w/o creds) green — DONE (75 passed, 1 skipped; pre-commit clean)

**Checkpoint**: US2 functional + testable. FR-3, FR-6 covered.

---

## Phase 5: User Story 3 — Per-Field Health Status (Priority: P2)

**Goal**: `gateway providers --json` and TUI report per-field status; provider
"configured" only when all required fields resolve; secrets redacted (FR-4).

**Independent Test**: With partial env set, `gateway providers --json` emits
`credentials` list with correct `resolved` flags, `configured=false`, and no secret
values leaked.

### Tests for User Story 3
- [x] T022 [P] [US3] Unit test `gateway providers --json` emits per-field `resolved` + `configured` and redacts `secret=true` in `tests/unit/test_gateway_cli.py` (or `app.py` tests) — DONE (test_provider_credential_status_partial in test_gateway_registry.py; asserts "us-east-1"/"fake" never in json.dumps, merged 7038294)
- [x] T023 [P] [US3] Unit test TUI health uses per-field resolution (falls back to `env_key` when list empty) in TUI test module — DONE (test_gateway_providers_json.py T023 + tui/domain/gateway.py list_providers spreads configured+credentials)

### Implementation for User Story 3
- [x] T024 [US3] Update `gateway_providers` JSON branch in `src/openreview_cli/app.py` to emit `credentials` list + `configured` (depends on T010) — DONE (app.py:1346, provider_credential_status single source of truth, backward-compat api_key_env kept)
- [x] T025 [US3] Update TUI health check (currently `os.environ.get(info.env_key)`) to iterate `info.credentials` per-field in the TUI health module — DONE (tui/domain/gateway.py list_providers emits configured+credentials per field)
- [x] T026 [US3] Run US3 unit + TUI tests green — DONE (24 passed registry+providers_json; ruff + targeted mypy clean; LITERAL `openreview gateway providers --json` run confirmed: configured:false partial, per-field resolved, secret values never printed even when resolved)

**Checkpoint**: US3 functional + testable. FR-4 covered.

---

## Phase 6: User Story 4 — Wizard + CLI Collection (Priority: P2)

**Goal**: `gateway provider add --cred env_key=VALUE` (repeatable) and the questionary
wizard collect N fields; Vertex ADC path validated as file (FR-5, FR-7).

**Independent Test**: `gateway provider add bedrock --cred AWS_REGION_NAME=us-east-1 ...`
writes the mapping into `auth.json` (mode 600); wizard loop prompts per field and
rejects a non-existent Vertex ADC path.

### Tests for User Story 4
- [x] T027 [P] [US4] Unit test `gateway provider add --cred` repeatable parsing in `tests/unit/test_gateway_cli.py` — DONE (test_provider_add_writes_dict_shaped_auth, merged 4f4663b)
- [x] T027a [P] [US4] Unit test auth persistence supports dictionary mapping for multi-field providers — DONE (test_save_provider_credentials_writes_dict_and_preserves_legacy in test_auth.py; NOTE: load_auth/save live in config/auth.py, not config/loader.py as task text guessed)
- [x] T028 [P] [US4] Unit test wizard questionary loop over `provider.credentials` (mocked) + Vertex `is_file_path` rejection in `tests/unit/test_gateway_wizard.py` — DONE (test_wizard_collects_per_field_credentials + test_wizard_rejects_missing_vertex_adc_path)
- [x] T028a [US4] Update auth persistence to support dictionary mapping for multi-field providers — DONE in config/auth.py (load_auth -> dict[str, Any] preserves both shapes; save_provider_credentials merges dict; ALSO fixed _set_env_vars bug: legacy string + new dict coexist, regression test added) — merged 4f4663b
- [x] T029 [US4] Add repeatable `--cred` list-option to `gateway provider add` in `src/openreview_cli/app.py`; parse `key=value`, store dict in auth.json — DONE (merged 4f4663b)
- [x] T030 [US4] Extend wizard in `src/openreview_cli/gateway/wizard.py` to loop `provider.credentials`, mask secret, validate `is_file_path` — DONE (merged 4f4663b)
- [x] T031 [US4] Run US4 unit tests green — DONE (74 passed; pre-commit clean)

**Checkpoint**: US4 functional + testable. FR-5, FR-7 covered.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Cross-cutting validation + green CI.

- [x] T032 [P] Run `uv run pre-commit run --all-files` (ruff, ruff-format, mypy --strict, pytest-fast) green across all changes — DONE (full pre-commit green on merged branch, including whole-project mypy)
- [x] T033 [P] Run `uv run pytest tests/unit/ -q` full unit suite green (no regression to single-key providers) — DONE (1922 passed; one isolation flake fixed hermetically in test_provider_credential_status_partial)
- [x] T034 [P] Execute `quickstart.md` validation scenarios 1–7 (live scenario 6 skipped without creds) — DONE (all covered by passing unit/integration suite; scenario 6 = T015 SKIPPED without creds as designed)
- [x] T035 [P] Verify `secret=true` values never appear in `gateway providers --json` output or logs (constitution Principle I) — DONE (literal `openreview gateway providers --json` run: LEAK False; router uses redact_key in logging at router.py:147)

---

## Dependencies & Execution Order

### Phase Dependencies
- **Setup (Phase 1)**: no deps — start immediately.
- **Foundational (Phase 2)**: blocks all user stories (T003–T006).
- **US1 (Phase 3)**: depends on Foundational. MVP.
- **US2 (Phase 4)**: depends on US1 (needs `CredentialField` model).
- **US3 (Phase 5)**: depends on US1 (needs `credentials` on `ProviderInfo`).
- **US4 (Phase 6)**: depends on US1 (needs `credentials`); independent of US2/US3.
- **Polish (Phase 7)**: depends on US1–US4.

### User Story Dependencies
- **US1 (P1)**: after Foundational. No story deps.
- **US2 (P1)**: after US1.
- **US3 (P2)**: after US1. Can run parallel with US2/US4.
- **US4 (P2)**: after US1. Can run parallel with US2/US3.

### Within Each User Story
- Tests written/run; models before mapping; mapping before registry entries; CLI/TUI last.
- Story complete before next priority checkpoint.

### Parallel Opportunities
- T002, T003, T004, T005, T006 marked [P] — run in parallel within Setup/Foundational.
- US2 / US3 / US4 can proceed in parallel after US1 (different files: router+models.json / app.py+TUI / app.py+wizard.py — note US3 and US4 both touch app.py, so sequence those or coordinate).
- All test tasks marked [P] within a story run in parallel.

---

## Parallel Example: User Story 2

```bash
# Models/registry tests (parallel):
Task: "T012 Unit test _get_litellm_kwargs injects aws_region_name"
Task: "T014 Unit test bedrock/vertex/azure load + configured=False"
# Implementation (after T010):
Task: "T016 Extend _get_litellm_kwargs loop in router.py"
Task: "T018 Add bedrock entry to models.json"
Task: "T019 Add vertex entry to models.json"
Task: "T020 Add azure entry to models.json"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)
1. Phase 1 Setup → T001/T002.
2. Phase 2 Foundational → T003–T006 (model + registry tolerance).
3. Phase 3 US1 → T007–T011. **STOP & VALIDATE**: `ProviderInfo` loads with/without
   `credentials`, single-key providers untouched.
4. This alone satisfies FR-1 + FR-2 (the model contract) — shippable increment.

### Incremental Delivery
1. Setup + Foundational → model layer ready.
2. US1 → FR-1/FR-2 done → validate.
3. US2 → FR-3/FR-6 done → live test (skipped w/o creds) → validate.
4. US3 → FR-4 done → validate.
5. US4 → FR-5/FR-7 done → validate.
6. Polish → pre-commit + full suite green.

### Parallel Team Strategy
- Dev A: Foundational + US1 (models).
- Dev B: US2 (router mapping + models.json) after US1.
- Dev C: US3 (app.py/TUI) + US4 (app.py/wizard) after US1 (coordinate app.py edits).

---

## Notes
- [P] = different files, no dependencies.
- [Story] maps task to US1..US4 for traceability.
- Every task has an exact file path.
- TDD: tests included per repo AGENTS.md + spec Success Criteria 5.
- No new dependencies (litellm/pydantic/typer already present — Context7-verified).
- MVP = US1 (FR-1, FR-2 model contract).

---

## Phase 8: Convergence

**Purpose**: Close gaps between spec 034 FRs and the implemented code, found by
`/speckit.converge`. Four `partial` gaps (no `missing`/`contradicts`, no constitution
MUST violation). Single-key backward compat (FR-2), secret redaction in output/logs
(FR-4/T035), auth.json chmod 0o600 (FR-8), and FR-3/FR-6 kwargs on chat+embed paths are
confirmed met. TDD: each task needs a unit test.

- [x] T036 Render per-field credential status (resolved/secret/required) in the TUI provider/health view, consuming the per-field data `tui/domain/gateway.py:list_providers()` already exposes (currently only `p["name"]` is rendered at `tui/screens/gateway_wizard.py:87`) per FR-4 (partial) — DONE (`gateway_wizard.py:_render_provider_step` appends `✓`/`✗` per field; test_wizard_step2_shows_per_field_status in tests/integration/tui/test_gateway_wizard.py GREEN)
- [x] T037 Validate that file-based credentials are non-empty (file size > 0) in `src/openreview_cli/gateway/wizard.py:49-51`, in addition to existence + read access, per FR-7 (partial) — DONE (`os.path.getsize(value) > 0` added; test_wizard_rejects_empty_vertex_adc_file GREEN)
- [x] T038 Reject empty required credential fields in both the wizard (`_collect_provider_credentials`, `wizard.py:46-52`) and `gateway provider add --cred` parsing (`app.py:1596-1597`, currently stores `""`) per FR-5 (partial) — DONE (wizard: `field.required and value == ""` → abort; CLI: `--cred KEY=` → exit 2; tests test_provider_add_rejects_empty_cred + test_wizard_rejects_empty_required_field GREEN)
- [x] T039 Route `Gateway.rerank()` through `_get_litellm_kwargs()` so multi-field provider credentials are mapped to litellm kwargs (currently bypassed at `router.py:543-550`, unlike chat/embed) per FR-3 (partial) — DONE (rerank now builds kwargs via `_get_litellm_kwargs`; test_rerank_applies_provider_credentials GREEN)
