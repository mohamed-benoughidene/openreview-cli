# TierRouter Interface Contract

## Purpose

The TierRouter is a thin enforcement layer between calling code (review pipeline, extraction agent) and the AI Gateway. It intercepts every model call, applies privacy tier rules, and either passes the call through or blocks it with an actionable error.

## Interface

### Constructor

```
TierRouter(gateway: Gateway, config: TierConfig)
```

- `gateway`: An instance of the existing AI Gateway class.
- `config`: A `TierConfig` instance (see data-model.md) captured at operation start.
- Raises nothing during construction (validation happens at call time).

### Wrapped Methods

#### `chat(model: str, messages: list, **kwargs) -> ChatResponse`

Wraps `Gateway.chat()`. Enforces LLM routing rules:
- **Maximum**: Select only local providers. If none → `NoMatchingProviderError`.
- **Balanced**: Cloud providers allowed. PII must be verified before dispatch.
- **Performance**: Cloud providers allowed. PII must be verified before dispatch.

#### `embed(model: str, input: str | list[str], **kwargs) -> EmbeddingResponse`

Wraps `Gateway.embed()`. Enforces embedding routing rules:
- **Maximum**: Select only local providers. If none → `NoMatchingProviderError`.
- **Balanced**: Select only local providers. If none → `NoMatchingProviderError`.
- **Performance**: Cloud providers allowed. PII must be verified before dispatch.

### Internal Methods (not part of public contract, but testable)

#### `_get_allowed_provider_location(call_type: CallType) -> ProviderLocation`

Returns which provider location is required for the current tier + call type.

| Tier | chat() | embed() |
|------|--------|---------|
| maximum | local | local |
| balanced | cloud | local |
| performance | cloud | cloud |

#### `_verify_pii_before_cloud_call(document_text: str | None) -> bool`

Called only when a cloud call is pending. Returns True if PII is available and has been applied. Raises `PIIUnavailableError` if PII engine is unavailable. Returns True if no document text is provided (no-op for calls that don't carry document content).

#### `_filter_providers_by_location(providers: list, location: ProviderLocation) -> list`

Filters a list of provider configs to only those matching the required location. Uses `ProviderLocationClassifier` for each provider.

### Exceptions

All defined in `src/openreview_cli/gateway/errors.py`.

#### `TierRoutingError(BaseException)`

Base class for tier routing errors. All tier errors inherit from this.

#### `NoMatchingProviderError(TierRoutingError)`

Raised when the filtered provider list is empty. Message includes:
- Current tier name
- Required provider location (local/cloud)
- Which providers were available but filtered out (and why)
- Suggested action: install a local provider / configure a cloud provider / change tier

#### `PIIUnavailableError(TierRoutingError)`

Raised when a cloud call is pending but PII engine is unavailable. Message includes:
- Current tier name
- The fact that PII stripping failed
- At least two actionable suggestions (A: switch to Maximum, B: fix PII engine, C: --no-pii confirmation)

### Error Behavior

The tier router NEVER:
- Silently falls back to a different tier
- Sends unstripped text to a cloud provider
- Drops errors without user-visible messages
- Modifies provider configs or Gateway state

## Call Flow

```
Caller code → TierRouter.chat() or TierRouter.embed()
  1. Determine allowed provider location (tier + call type)
  2. Filter configured providers to matching location
  3. If no providers match → NoMatchingProviderError
  4. If cloud call and PII not verified → PIIUnavailableError
  5. Pass filtered providers to Gateway
  6. Gateway selects provider and dispatches
  7. Return Gateway response (or propagate error)
```

## Configuration Contract

### config.yml key

```yaml
privacy:
  tier: maximum    # valid: maximum, balanced, performance
```

Behaviour by scenario:
| Config State | Effective Tier | Warning Shown? |
|-------------|----------------|----------------|
| `privacy.tier: maximum` | Maximum | No |
| `privacy.tier: balanced` | Balanced | No |
| `privacy.tier: performance` | Performance | No |
| `privacy.tier: invalid` | Maximum | Yes: "Unrecognized privacy tier 'invalid'. Defaulting to Maximum." |
| `privacy.tier` missing | Maximum | Yes: "privacy.tier not configured. Defaulting to Maximum." |
| No `privacy` section | Maximum | Yes (same as missing key) |

### Provider Config (for classification)

Provider configs may include an optional `local` field to override URL-based classification:

```yaml
providers:
  my-ollama:
    api_base: http://192.168.1.100:11434  # non-localhost but local
    local: true                            # explicit override
  openai:
    api_base: https://api.openai.com/v1
    # no local flag → default cloud
```

## Testability

TierRouter is designed for testability without real providers or PII engine:

- `gateway` parameter accepts mocks/stubs
- `config` parameter accepts programmatic `TierConfig` instances
- `ProviderLocationClassifier` is a pure function (input → output, no IO)
- `PiiEngine.is_available()` can be monkeypatched or mocked
- No filesystem access, no network access during routing logic
