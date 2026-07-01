# Feature Specification: SLM Model Params Extension

**Feature Branch**: `006-slm-model-params`

**Created**: 2026-07-01

**Status**: Draft

**Input**: User description: "N-3 Extend gateway ModelParams for SLM optimization"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Pass Provider-Specific Parameters to Local SLMs (Priority: P1)

A user configures an Ollama-hosted SLM (e.g. `qwen3:8b`) for the extraction slot. To maximise quality on their 16 GB machine, they set `num_gpu: 0` (CPU-only) and `num_ctx: 4096` (reduced context to save RAM). These parameters are specific to Ollama and do not exist on cloud providers. The gateway passes them through to LiteLLM without modification, and the model runs with the requested settings.

**Why this priority**: Without provider-specific pass-through, SLMs run with LiteLLM defaults that may be suboptimal or even crash the machine (e.g. trying to allocate GPU memory on a machine with no GPU). This is the core value of N-3.

**Independent Test**: Can be tested by configuring `extra_params` in `config.yml` for an Ollama model slot and verifying the parameters appear in the LiteLLM call kwargs.

**Acceptance Scenarios**:

1. **Given** a config with `extra_params: {num_gpu: 0, num_ctx: 4096}` on the extraction slot, **When** the gateway routes a chat call to that slot, **Then** the LiteLLM call kwargs include `num_gpu=0` and `num_ctx=4096`.
2. **Given** a config with no `extra_params`, **When** the gateway routes a chat call, **Then** only standard parameters (`temperature`, `max_tokens`) are included — no extra keys appear.
3. **Given** a config with `extra_params` containing nested values (e.g. `options: {mirostat: 2}`), **When** the gateway routes a call, **Then** the nested structure passes through intact.

---

### User Story 2 - Cloud Providers Ignore Irrelevant Extra Params (Priority: P2)

A user switches their extraction slot from Ollama (`qwen3:8b` with `num_gpu: 0`) to OpenAI (`gpt-4o`). They forget to remove the `extra_params`. The gateway still routes the call. LiteLLM either passes the unknown parameter (and the provider ignores it) or the gateway logs a warning. The call does not crash.

**Why this priority**: Safety net. Users switch providers during experimentation. The gateway should not error on stale configuration.

**Independent Test**: Can be tested by configuring `extra_params` with Ollama-specific keys on an OpenAI model and verifying the call completes (with a warning logged, not an exception).

**Acceptance Scenarios**:

1. **Given** an OpenAI model configured with `extra_params: {num_gpu: 0}`, **When** the gateway routes a call, **Then** the call kwargs include `num_gpu=0` (LiteLLM handles provider filtering) and no exception is raised.

---

### User Story 3 - View Active Extra Params in Health Check (Priority: P3)

A user runs the gateway health check to see which models are configured. For slots that have `extra_params`, the health check output includes a count of extra parameters (e.g. `extra_params: 2 keys`) so the user knows pass-through config is active.

**Why this priority**: Discoverability. Without visibility, users cannot confirm their extra params are actually being picked up.

**Independent Test**: Can be tested by running a health check on a gateway with extra_params configured and verifying the output includes extra_params information.

**Acceptance Scenarios**:

1. **Given** a slot with `extra_params: {num_gpu: 0, num_ctx: 4096}`, **When** the user runs health check, **Then** the slot's health output includes `"extra_params": 2`.
2. **Given** a slot with no `extra_params`, **When** the user runs health check, **Then** no `extra_params` key appears in that slot's output.

---

### Edge Cases

- What happens when `extra_params` contains a key that conflicts with a standard parameter (e.g. `extra_params: {temperature: 0.5}` when `params.temperature` is already 0.7)? — `extra_params` overrides `params` because it is applied after standard params.
- What happens when `extra_params` contains an empty dict (`{}`)? — Treated as no extra params; no keys are added.
- What happens when `extra_params` is set to a non-dict value (e.g. a string or list)? — Rejected at config load time by Pydantic `ValidationError` (the `ModelSlot` model in `_validate_and_merge` defines `extra_params: dict[str, Any] | None`).
- What happens when `extra_params` contains the key `model` or `messages`? — These are critical call keys. `extra_params` MUST NOT override `model` or `messages`. The gateway strips these keys before merging and logs a warning.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The gateway MUST support an `extra_params` field on each model slot in `config.yml` that accepts an arbitrary key-value mapping.
- **FR-002**: The gateway MUST merge `extra_params` into the LiteLLM call kwargs after standard params (`temperature`, `max_tokens`), allowing `extra_params` to override standard params.
- **FR-003**: The gateway MUST strip the keys `model`, `messages`, `input`, and `timeout` from `extra_params` before merging, to protect call-critical parameters.
- **FR-004**: The gateway MUST log at DEBUG level when `extra_params` are applied, listing the keys (not values) being passed through.
- **FR-005**: The gateway MUST log at WARNING level if `extra_params` contains a protected key that was stripped.
- **FR-006**: The `ModelEntry` dataclass MUST include an optional `extra_params` field for the static model registry, allowing per-model default extra params to be documented.
- **FR-007**: The gateway health check MUST report the count of active `extra_params` for each configured slot.
- **FR-008**: The `extra_params` field MUST support nested dict values (pass-through intact) for providers that accept structured options (e.g. Ollama's `options` object).

### Key Entities

- **SlotConfig (config.yml)**: A model slot configuration with `primary`, `fallback`, `params`, and the new `extra_params` field. Lives in the user's `config.yml`.
- **ModelEntry (models.json)**: A static registry entry documenting known models. The new `extra_params` field here is for documentation — showing users what provider-specific params a model supports.
- **Protected Keys**: The set `{model, messages, input, timeout}` — keys that `extra_params` must never override because they are structurally required by the gateway routing logic.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Any key-value pair placed in `extra_params` in config.yml appears in the LiteLLM call kwargs, verifiable in unit tests.
- **SC-002**: Protected keys (`model`, `messages`, `input`, `timeout`) are never overridden by `extra_params`, verifiable in unit tests.
- **SC-003**: Health check output includes extra_params count for configured slots, verifiable in unit tests.
- **SC-004**: All existing gateway tests continue to pass — zero regressions.
- **SC-005**: `mypy --strict` passes with the new `extra_params` field on both `ModelEntry` and config handling.

## Clarifications

### Session 2026-07-01

- Q: Should SlotConfig become a typed Pydantic model or remain dict-based? → A: Dict-based — keep current approach, add validation/logic in `_get_litellm_kwargs` only.

## Assumptions

- LiteLLM passes unknown kwargs through to the provider SDK without raising errors. This is documented LiteLLM behavior — it forwards `**kwargs` to the underlying provider.
- The `extra_params` field in `config.yml` is already parsed by the gateway's `_get_litellm_kwargs` method (the router code at line 98-100 already reads `extra_params` from config and merges them). This spec formalises and hardens that behaviour.
- No new dependencies are required. This is a pure Python change to existing Pydantic models and routing logic.
- The `extra_params` field on `ModelEntry` (models.json) is informational — it documents what provider-specific params are available, but is not enforced at runtime.
