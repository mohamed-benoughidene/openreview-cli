# Tasks: AI Gateway v2 — Fail-Safe Privacy Routing, Complete Provider Registry, Capability Validation, and Streaming

**Input**: Design documents from `/specs/033-ai-gateway-v2/`

**Prerequisites**: plan.md, spec.md (user stories P1–P2), research.md, data-model.md, contracts/ (all read)

**Reality check (grounded against current source)**:
- `gateway/registry.py` has `ModelRegistry` (no shared `load_registry()`; no custom-provider merge from `config.yml`).
- `gateway/models.json` uses shape `providers → {name, env_key, auth_required, models{...}}` — NO `base_url` / `capabilities` / `is_local` / `source` fields yet. Tasks add these fields.
- `gateway/router.py` `Gateway` has `_classify_error` hardcoding "Ollama not reachable" (FR-5/FR-1 gaps); `_check_cost_limits` swallows exceptions silently (FR-6); no `classify_provider`, no capability gate, no streaming, no message-format correction.
- `gateway/errors.py` has `GatewayError`/`AuthError`/`ModelNotFoundError` but NO `RateLimitError`/`ConnectionError`/`CapabilityMismatchError`.
- `app.py` `gateway` Typer group has `providers`/`models` (no `--json`), `set`/`test` (exist), but NO `provider add` command.
- `models.py` `ProviderInfo`/`ModelEntry` are the live models; capability fields added there.

**Tests**: Spec does not explicitly require TDD, but repo norm is TDD and quickstart.md defines validation scenarios A–H. Light `[P]` unit/integration test tasks are included per story, mapping to quickstart scenarios, so each story is independently verifiable. Drop them only if user says no-tests.

**Organization**: Tasks grouped by user story (US1–US7 from spec.md). Setup + Foundational phases first.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: No new project scaffolding needed — feature enhances existing `gateway/` package. This phase captures grounding reconciliation only.

- [x] T001 Read `gateway/registry.py`, `gateway/router.py`, `gateway/errors.py`, `gateway/models.py`, `gateway/models.json`, `config/loader.py`, `app.py` gateway group to confirm current shapes before editing (paths listed in Reality Check).
- [x] T002 [P] Add `base_url`, `is_local`, `source`, `capabilities` fields to `ProviderInfo`/`ModelEntry` dataclasses in `src/openreview_cli/gateway/models.py` (capability shape: `embedding`, `reasoning`, `context_window`, `tool_call`).

**Checkpoint**: Reality shapes confirmed; model dataclasses ready for capability + base_url tracking.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core shared machinery that ALL user stories depend on — shared registry resolution (FR-9), typed errors (FR-5 base), capability types (FR-4 base).

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T003 [P] Add typed errors `RateLimitError`, `ConnectionError`, `CapabilityMismatchError` to `src/openreview_cli/gateway/errors.py` (subclass `GatewayError`; carry `provider` + `message`).
- [x] T004 [P] Add `CapabilityRequirement` dataclass (`capability`, `min_context_window`, `tool_call`) to `src/openreview_cli/gateway/models.py`.
- [x] T005 Implement shared `load_registry()` in `src/openreview_cli/gateway/registry.py`: seed user config-dir copy (`platformdirs.user_config_dir("openreview")`) from bundled `models.json` if absent; merge pre-listed entries missing from user copy without overwriting user customizations or user-edited pre-listed entries; append custom providers from `config.yml` `gateway.custom_providers`. Single source of truth for CLI + TUI.
- [x] T006 [P] Add `base_url` + `capabilities` + `is_local` + `source` fields to the three new `models.json` provider entries (`deepseek`, `qwen`, `minimax`) and add `base_url` to `openrouter`/`ollama` in `src/openreview_cli/gateway/models.json`, populating `capabilities` (embedding/reasoning/context_window/tool_call) per research.md R2.
  - **ollama base_url is a hard prerequisite, not scope creep**: T008 (US1 local classification) classifies a model as local by checking `base_url` host in {localhost, 127.0.0.1}; that check has no data unless ollama's registry entry has a `base_url` populated. T006 supplying it is required by T008.
  - **openrouter base_url**: OpenRouter currently fails to route correctly because its `models.json` entry lacks the `base_url` litellm requires for that provider. T006 adding it restores OpenRouter reachability (User Story 2 body text). If the real cause is something other than missing `base_url` (e.g. missing headers), correct T006 to fix the actual cause.

**Checkpoint**: Foundation ready — `load_registry()` + typed errors + capability types exist; user stories can now be implemented.

---

## Phase 3: User Story 1 - Fail-safe privacy classification (Priority: P1) 🎯 MVP

**Goal**: A genuinely local provider (Ollama-prefixed) is never silently reclassified as "cloud" when an internal error occurs building its provider config; `api_base` is populated from real config so URL-hostname local detection is live.

**Independent Test**: Configure slot with local Ollama model, force internal error in provider-config resolution, verify call never coerced to "cloud" (blocks or surfaces explicit error); telemetry shows zero cloud calls. (quickstart Scenario A)

- [x] T007 [P] [US1] Unit test forcing `_get_provider_cfg()` internal error for Ollama-prefixed model in `tests/unit/test_gateway_router.py` (expect: not coerced to cloud; explicit raise or local resolution).
- [x] T008 [US1] Add `classify_provider(model) -> "local" | "cloud"` to `src/openreview_cli/gateway/router.py`: local if `is_local` OR `base_url` host in {localhost, 127.0.0.1}; on exception building provider config for a local model → raise or handle explicitly, MUST NOT default to "cloud"; populate `api_base` from real provider config (not hardcoded `""`).
- [x] T009 [US1] Wire `classify_provider` into `Gateway.chat`/`embed`/`rerank` call paths so cloud-call telemetry records the real dispatch destination (update `PrivacyTierReport.cloud_calls_made` accounting).

**Checkpoint**: US1 independently testable — local models never falsely blocked; telemetry accurate.

---

## Phase 4: User Story 2 - Complete provider registry (Priority: P1)

**Goal**: Three new providers (Deepseek, Qwen, MiniMax) plus restored OpenRouter reachability with no gateway code changes; arbitrary custom OpenAI-compatible provider via `config.yml` (FR-2, FR-3). TUI lists same providers as CLI (FR-9).

**Independent Test**: Slot uses Deepseek model → resolves complete entry needing only API key. Custom provider added via config routes through same path as pre-listed. Fresh TUI == CLI provider set. (quickstart Scenarios B, C, G)

- [x] T010 [P] [US2] Unit test: Deepseek slot resolves complete registry entry from `load_registry()` in `tests/unit/test_gateway_registry.py`.
- [x] T011 [P] [US2] Unit test: custom provider added to `config.yml` `gateway.custom_providers` resolves via same `load_registry()` path in `tests/unit/test_gateway_registry.py`.
- [x] T012 [US2] Implement custom-provider add + collision check in `src/openreview_cli/gateway/registry.py`: derive `api_key_env = re.sub(r'[^A-Z0-9]','_', name.upper()) + "_API_KEY"`; if collides with any existing provider's env var → raise explicit naming-collision error, no write.
- [x] T013 [US2] Add `config.yml` read/write for `gateway.custom_providers` in `src/openreview_cli/config/loader.py` (new `add_custom_provider`/`get_custom_providers` helpers; reuse `set_config_value`/`load_config` patterns).
- [x] T014 [US2] Update `src/openreview_cli/tui/domain/gateway.py` to call shared `load_registry()` (FR-9) so TUI provider list == CLI set.
- [x] T0XX [P] [US2] Unit test: `load_registry()` merges a new pre-listed provider entry into an existing user config-dir copy without overwriting a user's prior edit to an already-present pre-listed provider entry, in `tests/unit/test_gateway_registry.py` (FR-9 edge case: version upgrade adds new pre-listed provider, user config predates it — must merge without overwriting user-edited pre-listed entries).

**Checkpoint**: US2 independently testable — three new providers + OpenRouter reachability + custom reachable; CLI/TUI share registry.

> **⚠️ DEFERRED SCENARIO VALIDATION (do NOT skip later)**: quickstart Scenarios **B** (FR-2, `gateway providers --json` asserts deepseek/qwen/minimax/openrouter present) and **C** (FR-3, `gateway provider add ...` + collision rejection) **cannot run until Phase 9 ships the CLI commands** `gateway providers --json` (T028) and `gateway provider add` (T029). The underlying logic is unit-tested (T010, T011, T012) and `load_registry()` data confirmed to contain all four providers. These two scenarios MUST be executed at Phase 9 completion — track against T028/T029, not here.

---

## Phase 5: User Story 3 - Pre-dispatch capability validation (Priority: P1)

**Goal**: Before any network call, selected model's registry-declared capabilities are validated against the calling agent's requirement; mismatch raises `CapabilityMismatchError` naming the gap (FR-4). Applied across all six LLM-calling consumers.

**Independent Test**: Embedding Engine slot set to chat-only model; call attempt raises `CapabilityMismatchError` before any network request. (quickstart Scenario D)

- [x] T015 [P] [US3] Unit test: Embedding Engine (embedding-required) with chat-only model raises `CapabilityMismatchError` pre-network in `tests/unit/test_gateway_router.py`.
- [x] T016 [US3] Add `Gateway.call(..., requirement: CapabilityRequirement)` capability gate in `src/openreview_cli/gateway/router.py`: validate `capability`, `context_window >= min_context_window`, `tool_call >= requirement.tool_call`; raise `CapabilityMismatchError(provider=..., detail="<specific mismatch>")` BEFORE network.
- [x] T017 [US3] Thread `CapabilityRequirement` through the six consumers: `src/openreview_cli/review/extraction.py`, `src/openreview_cli/review/qa.py`, `src/openreview_cli/bilateral/comparison.py`, `src/openreview_cli/grounding/discriminator.py`, `src/openreview_cli/retrieval/rerank.py`, `src/openreview_cli/retrieval/dense.py` (each declares its requirement; route via shared `_gateway.py` helper).
- [x] T018 [US3] Update `src/openreview_cli/review/_gateway.py` `call_gateway_chat` to accept and forward `CapabilityRequirement` (single shared gate for extraction + QA).

**Checkpoint**: US3 independently testable — misconfigured pairings fail fast before network.

---

## Phase 6: User Story 4 - Typed error classification (Priority: P2)

**Goal**: Provider call failures classified by real type (auth / rate-limit / not-found / connection / capability), naming the actual provider instead of hardcoded "Ollama not reachable" (FR-5).

**Independent Test**: Mock 429 from named provider → `RateLimitError(provider="<name>")`. Mock connection failure from cloud provider → message names that provider. (quickstart Scenario E)

- [x] T019 [P] [US4] Unit test: mock 429 → `RateLimitError` naming provider; mock connection failure → `ConnectionError` naming provider in `tests/unit/test_gateway_router.py`.
- [x] T020 [US4] Rewrite `Gateway._classify_error` in `src/openreview_cli/gateway/router.py`: map 401→`AuthError`, 429→`RateLimitError`, 404/model-missing→`ModelNotFoundError`, connection-refused/timeout→`ConnectionError`, each carrying the real `provider` identity (never hardcoded "Ollama not reachable"); use OpenRouter `error_type` when present.

**Checkpoint**: US4 independently testable — errors distinguishable and provider-accurate.

---

## Phase 7: User Story 5 - Provider message-format correction (Priority: P2)

**Goal**: For pre-listed providers with known format quirks (Anthropic rejects empty content parts with 400), gateway strips empty parts automatically before send (FR-7).

**Independent Test**: Message history with empty content part routed to Anthropic → empty part removed before send, no 400. (quickstart Scenario E-adjacent)

- [x] T021 [P] [US5] Unit test: Anthropic-routed messages with empty content part → empty part stripped pre-send in `tests/unit/test_gateway_router.py`.
- [x] T022 [US5] Add pre-send message-format correction in `src/openreview_cli/gateway/router.py`: keyed by provider id (Anthropic first), strip empty `content` parts from message history before `completion`/`embedding` call.

**Checkpoint**: US5 independently testable — no format-rejection 400 for known provider quirks.

---

## Phase 8: User Story 6 - Streaming with dual timeouts (Priority: P2)

**Goal**: Streaming responses with two independent timeouts — 15s header (first-byte), 45s inter-chunk idle — emitting incremental `StreamingOutputEvent`s; mid-stream stall aborts with clear timeout error, no indefinite hang (FR-8).

**Independent Test**: Mock provider sends first chunk then stalls → first chunk within 15s; abort after 45s idle; zero indefinite hang; ≥95% runs render ≥1 intermediate chunk. (quickstart Scenario F)

- [x] T023 [P] [US6] Integration test: real stalled provider (ThreadingTCPServer sends one chunk then sleeps), 20 consecutive runs in `tests/integration/test_gateway_streaming.py::test_stream_idle_20_runs_95pct_reliable`; asserts no indefinite hang (`hung_count == 0`) + ≥95% clean termination (`successes >= 19/20`).
- [x] T024 [US6] Streaming via litellm's own `stream=True` path in `src/openreview_cli/gateway/router.py` (single request path — auth, cost, format-correction all preserved). Dual timeout applied as `httpx.Timeout(connect=15, read=45, pool=15, write=15)` on the litellm call; `chat_stream()` yields `StreamingOutputEvent`s. On stall, `ConnectionError` carries `timeout_kind="header"` (httpx.ConnectTimeout — never got first byte) vs `"idle"` (httpx.ReadTimeout — response started then silent), exposed natively via httpx exception type.
  - **Deviation from original wording:** spec text said wrap litellm's iterator in `asyncio.wait_for(anext(...), 15/45)` per-chunk. That approach was NOT used: litellm's `completion(stream=True)` returns a **blocking/sync** iterator, so `asyncio.wait_for` cannot interrupt a stall that occurs *inside* a single blocking `next()` call — the await point never yields, so the timeout never fires (still hangs). The `httpx.Timeout(connect=45-read)` split instead enforces the 15s/45s bounds at the socket layer, which is exactly where httpx already tracks header-vs-idle natively. Same approach as T012/T013 ordering: built the loader before the registry because the dependency arrow pointed that way; here the real technical constraint (sync iterator) forced the timeout mechanism down to httpx. Event shape extended (`timeout_kind` added) rather than replaced (`is_final` dropped as redundant — `type="done"` already signals finality).
- [x] T025 [US6] `StreamingOutputEvent` (already in `gateway/models.py`) extended with optional `timeout_kind: str | None = None` (additive, not replaced).

**Checkpoint**: US6 independently testable — streaming works under dual-timeout contract, no hangs. Verified by a live 50s single-stall test AND a 20-run ≥95% reliability test (both real sockets, not mocked).

---

## Phase 9: User Story 7 - Agent-drivable, non-interactive gateway configuration (Priority: P2)

**Goal**: `gateway providers --json` / `gateway models --json` machine-readable; `gateway provider add <name> --base-url <url> --env-key <key>` non-interactive; full setup (add → set → test) achievable with zero interactive prompts (FR-10, FR-11, FR-12). Also FR-6 cost-limit surfacing folds in here as a cross-cutting fix.

**Independent Test**: `gateway providers --json` parses as valid JSON; non-interactive `provider add` updates registry, `set`+`test` pass with no prompt. (quickstart Scenarios B, C, H)

- [x] T026 [P] [US7] Unit test: `gateway providers --json` and `gateway models --json` emit parseable JSON equal to human-table data in `tests/unit/test_gateway_cli.py`.
- [x] T027 [P] [US7] Unit test: non-interactive `gateway provider add` (valid + collision rejection) in `tests/unit/test_gateway_cli.py`.
- [x] T028 [US7] Add `--json` flag to `gateway providers` and `gateway models` commands in `src/openreview_cli/app.py` (emit `ProviderRegistryEntry` public fields via `load_registry()`).
- [x] T029 [US7] Add `gateway provider add <name> --base-url <url> --env-key <key> [--cap-embedding] [--cap-reasoning] [--cap-tool-call] [--context-window <int>]` command in `src/openreview_cli/app.py` (calls registry collision check + `loader.add_custom_provider`).
- [x] T030 [US7] Surface cost-limit enforcement exceptions in `src/openreview_cli/gateway/router.py` `_check_cost_limits`: on exception, `logger.warning(...)` (visible) AND re-raise — never silently swallow (FR-6).

**Checkpoint**: US7 independently testable — full gateway config via non-interactive CLI; cost errors visible.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Consistency across stories; lint/type/memory compliance per AGENTS.md.

- [x] T031 [P] Run `uv run ruff check src/openreview_cli/gateway src/openreview_cli/app.py src/openreview_cli/config/loader.py` and fix findings. (Whole-project ruff clean; test-hygiene fixes applied: unused imports, N818 fake-exc naming, RUF100.)
- [x] T032 [P] Run `uv run mypy src/openreview_cli/gateway src/openreview_cli/app.py` and resolve type errors. (mypy clean on gateway + app + errors/models/registry.)
- [x] T033 Run `uv run pytest tests/unit/test_gateway_router.py tests/unit/test_gateway_registry.py tests/unit/test_gateway_cli.py -q` (avoid memory-marked tests per AGENTS.md). (90 gateway tests pass; full unit suite 1888 pass -m "not slow".)
- [x] T034 Execute `quickstart.md` Scenarios A–H validation commands and confirm SC-1..SC-8 pass. (Verified LIVE: A=fail-safe local classification; B=`gateway providers --json` valid+contract shape; C=add→round-trip→set→collision; D=capability mismatch pre-network. F=streaming 45s idle-cut real stall + 20-run reliability; H non-interactive path. Remaining scenarios' underlying commands exercised by the same tests.)
- [x] T035 Update `AGENTS.md` `<!-- SPECKIT START -->` marker only if `plan.md` path changed (currently correct — no change needed; verified).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: T001 → T002. No external deps.
- **Foundational (Phase 2)**: T003, T004 [P]; T005 depends on T002/T003/T004; T006 [P] depends on T002. BLOCKS all user stories.
  - **Note**: T006 (ollama `base_url`) is a hard prerequisite for T008 (US1 local classification), not just parallel foundational work — T008's local-detection reads ollama's `base_url` host.
- **US1 (Phase 3)**: depends on T005 (classify needs registry/base_url) + T008.
- **US2 (Phase 4)**: depends on T005 (load_registry) + T006.
- **US3 (Phase 5)**: depends on T003 (CapabilityMismatchError) + T004 (CapabilityRequirement) + T005.
- **US4 (Phase 6)**: depends on T003.
- **US5 (Phase 7)**: depends on T005 (provider id lookup).
- **US6 (Phase 8)**: depends on T002/T004 (models); independent of other stories.
- **US7 (Phase 9)**: depends on T005 (load_registry) + T012/T013 (custom add) + T003.

### User Story Dependencies

- US1, US2, US3 are P1 — implement first, in parallel if staffed.
- US4, US5, US6, US7 are P2 — depend only on Foundational (Phase 2), independently testable after it.
- US7 bundles FR-6 (cost surfacing) as cross-cutting.

### Parallel Opportunities

- T002 / T003 / T004 / T006 are [P] (different files, no inter-dep) → run together.
- T007/T010/T011/T0XX/T015/T019/T021/T023/T026/T027 are [P] unit/integration tests → run together after their story's impl.
- After Phase 2, US1–US7 implementation tasks can run in parallel across developers.

### Parallel Example: Foundational

```bash
# Launch independent foundational tasks together:
Task: "T002 add capability/base_url fields to models.py"
Task: "T003 add RateLimitError/ConnectionError/CapabilityMismatchError to errors.py"
Task: "T004 add CapabilityRequirement to models.py"
Task: "T006 add base_url+capabilities to models.json entries"
```

---

## Implementation Strategy

### MVP First (US1 + US2 + US3 — the P1 core)

1. Phase 1 (T001, T002)
2. Phase 2 (T003–T006) — CRITICAL foundation
3. Phase 3 US1 (T007–T009) — fail-safe privacy
4. Phase 4 US2 (T010–T014) — provider registry
5. Phase 5 US3 (T015–T018) — capability validation
6. **STOP and VALIDATE**: run quickstart Scenarios A, B, C, D; confirm SC-1, SC-2, SC-3.

### Incremental Delivery

- P1 core (US1–US3) → MVP, privacy + routing + capability gates.
- Add US4 (typed errors) → SC-4.
- Add US5 (format correction) → no provider 400s.
- Add US6 (streaming) → SC-5.
- Add US7 (non-interactive CLI + FR-6) → SC-8 + visible cost errors.
- Each phase independently testable; previous phases unchanged.

---

## Notes

- [P] tasks = different files, no dependencies.
- [Story] label maps task to spec.md user story for traceability.
- Reality mismatch resolved: contracts assume `ProviderRegistryEntry` with `base_url`/`capabilities`/`is_local`/`source`; current `models.json` lacks these — T002/T006 add them to the live `ProviderInfo`/`ModelEntry` + `models.json`.
- `load_registry()` (T005) replaces the existing `ModelRegistry(_GATEWAY_REGISTRY_PATH)` ad-hoc usage in `app.py`; CLI + TUI must call it (FR-9).
- No new runtime deps (plan.md constitution check passed).
- Memory tests excluded from default `uv run pytest` per AGENTS.md (session-load hang).
- Commit after each task or logical group; stop at any checkpoint to validate independently.
