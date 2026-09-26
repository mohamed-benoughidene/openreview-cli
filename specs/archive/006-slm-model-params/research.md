# Research: SLM Model Params Extension

**Date**: 2026-07-01 | **Feature**: 006-slm-model-params

## Research Tasks

### R1: LiteLLM Provider-Specific Parameter Forwarding

**Decision**: LiteLLM forwards all non-OpenAI kwargs to the underlying provider as-is.

**Rationale**: Confirmed via official LiteLLM docs (v1.90.1, installed). The `completion()` and `embedding()` functions accept `**kwargs` and route any unrecognised parameter directly to the provider SDK. This is explicitly documented for Sagemaker (`top_k`), Bedrock, Ollama, and others. The Ollama provider supports parameters like `num_gpu`, `num_ctx`, `num_thread`, and the `options` dict.

**Alternatives considered**:
- Wrapping each provider's params in an `extra_body` dict — rejected because LiteLLM handles this internally and top-level kwargs are the documented approach.
- Validating extra_params against known provider schemas — rejected as over-engineering (YAGNI). The provider SDK will reject invalid params; we don't need to duplicate that validation.

### R2: Protected Key Set

**Decision**: Strip `{model, messages, input, timeout}` from `extra_params` before merging.

**Rationale**: These four keys are structurally required by the gateway routing logic:
- `model` — set by `_get_litellm_kwargs()` from the slot's `primary` config
- `messages` — set by `chat()` from the caller's message list
- `input` — set by `embed()` from the caller's text list
- `timeout` — set by `_call_with_fallback()` from the fallback config

Allowing `extra_params` to override these would break routing silently. The current code already sets `model` before merging `extra_params` (line 91), but `extra_params` would override it via `kwargs.update(extra)` (line 100). This is a bug in the current implementation that this feature fixes.

**Alternatives considered**:
- Raising an exception when protected keys appear — rejected because users may have stale config when switching providers. A warning log is more user-friendly.
- Extending the protected set to include `temperature` and `max_tokens` — rejected because `extra_params` should be able to override standard params (spec edge case: `extra_params` overrides `params`).

### R3: Merge Order

**Decision**: `params` → `extra_params` → caller `**kwargs`

**Rationale**: The current code applies `params` first (temperature, max_tokens), then `extra_params` via `kwargs.update(extra)`. The `chat()` method then adds caller kwargs via `call_kwargs.update(kwargs)`. This means the merge order is: slot config params → extra_params → runtime caller kwargs. This is correct: provider-specific config overrides generic config, and runtime args override everything.

**Alternatives considered**: None — the current order is already correct.

### R4: Health Check Extra Params Visibility

**Decision**: Add `extra_params` count (integer) to health check output for slots that have extra params configured.

**Rationale**: The health check currently returns `{status, provider}` per slot. Adding `extra_params: N` (where N is the count of keys) makes it visible that provider-specific config is active without exposing the actual values (which could contain sensitive provider config).

**Alternatives considered**:
- Listing the extra_params key names — rejected because it adds verbosity with minimal benefit. The count is sufficient for "is it active?" verification.
- Exposing values — rejected per Privacy First (Principle I). Even though these are config values not PII, the principle of minimal disclosure applies.

## No NEEDS CLARIFICATION Items

All technical questions resolved from existing code and LiteLLM documentation. No unresolved unknowns.
