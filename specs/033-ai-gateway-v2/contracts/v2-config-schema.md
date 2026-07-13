# v2 Config Schema — `config.yml`

> Contract specification for the v2 configuration file (`~/.config/openreview/config.yml`). Provider-first format. YAML serialization.

---

## Top-Level Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `version` | int | Yes | 2 | Schema version. Must be 2. |
| `providers` | object | Yes | — | Map of provider name → ProviderConfig |
| `slots` | object | Yes | — | Map of slot name → SlotAssignment |
| `defaultModel` | str\|null | No | null | Default model for commands without a slot |
| `fallback` | object | No | `{retries: 2, timeout: 60}` | Global fallback settings |
| `costLimits` | object\|null | No | null | Spending caps |

---

## ProviderConfig Object

```yaml
providers:
  <provider_name>:        # Key = normalized provider identifier
    name: str              # Required. Provider display name
    apiKeySource: str      # Optional. Default "file". One of: "keyring", "file", "env"
    apiKeyRef: str         # Required. If source=env: env var name. If source=file: auth.json key
    baseURL: str|null      # Optional. For custom/self-hosted endpoints
    enabled: bool          # Optional. Default true
    envVarName: str        # Required. Canonical env var name (e.g., "OPENAI_API_KEY")
```

**Field details**:
- `name`: Must be lowercase alphanumeric with hyphens/underscores. Used for display and slot referencing.
- `apiKeySource`: Where to find the key. `keyring` requires `keyring` library. `file` reads from `auth.json`. `env` reads from environment at runtime.
- `apiKeyRef`:
  - If `apiKeySource=env`: the env var name (e.g., `OPENAI_API_KEY`)
  - If `apiKeySource=file`: the key in auth.json (usually matches `name`)
  - If `apiKeySource=keyring`: the service entry name (usually matches `name`)
- `baseURL`: When set, all API calls for this provider route to this URL instead of the default. Supports OpenAI-compatible endpoints (Ollama, LM Studio, custom).
- `enabled`: When false, this provider is skipped during model discovery and slot resolution.
- `envVarName`: The canonical environment variable name for this provider. Used by the auth command and documentation.

---

## SlotAssignment Object

```yaml
slots:
  <slot_name>:               # One of: reasoning, extraction, embedding, reranking, graph, grounding
    provider: str             # Required. References a key in `providers`
    model: str                # Required. Short name or explicit "provider/model"
    fallback: SlotAssignment  # Optional. Recursive slot assignment for failover
    limits:                   # Optional. Per-slot limits
      maxTokens: int|null     # Max output tokens
      maxContext: int|null    # Max context length
```

**Slot name validation**: Must be one of: `reasoning`, `extraction`, `embedding`, `reranking`, `graph`, `grounding`.

---

## FallbackConfig Object

```yaml
fallback:
  retries: int               # Optional. Default 2. Number of retries before failing
  timeout: int               # Optional. Default 60 seconds. Per-call timeout
  circuitBreaker:            # Optional. Circuit breaker settings
    failureThreshold: int    # Default 5. Consecutive failures before tripping
    cooldownSeconds: int     # Default 60. Seconds to wait before retrying
```

---

## CostLimits Object

```yaml
costLimits:
  perSessionCents: int|null  # Optional. Max spend per session in cents
  dailyCents: int|null       # Optional. Max spend per day in cents
```

When a limit is reached, subsequent API calls for that scope return an error. Limits are checked at the start of each call, not after.

---

## Full Example (6 Slots, 2 Providers)

```yaml
version: 2
providers:
  openai:
    name: openai
    apiKeySource: file
    apiKeyRef: openai
    enabled: true
    envVarName: OPENAI_API_KEY
  voyage:
    name: voyage
    apiKeySource: env
    apiKeyRef: VOYAGE_API_KEY
    baseURL: null
    enabled: true
    envVarName: VOYAGE_API_KEY
slots:
  reasoning:
    provider: openai
    model: gpt-4o
    fallback:
      provider: openai
      model: gpt-4o-mini
    limits:
      maxTokens: 4096
      maxContext: 128000
  extraction:
    provider: openai
    model: gpt-4o-mini
  embedding:
    provider: voyage
    model: voyage-3
  reranking:
    provider: voyage
    model: rerank-2
  graph:
    provider: openai
    model: gpt-4o-mini
  grounding:
    provider: openai
    model: gpt-4o
defaultModel: gpt-4o
fallback:
  retries: 3
  timeout: 120
  circuitBreaker:
    failureThreshold: 5
    cooldownSeconds: 60
costLimits:
  perSessionCents: 100
  dailyCents: 1000
```

---

## Minimal Example (1 Provider, 1 Slot)

```yaml
version: 2
providers:
  openai:
    name: openai
    apiKeySource: env
    apiKeyRef: OPENAI_API_KEY
    enabled: true
    envVarName: OPENAI_API_KEY
slots:
  reasoning:
    provider: openai
    model: gpt-4o
```

---

## Migration Table: v1 → v2 Field Names

| v1 Path | v2 Path | Notes |
|---------|---------|-------|
| `reasoning.provider` | `providers.{name}` (inferred) | v2 creates provider from slot provider name |
| `reasoning.model` | `slots.reasoning.model` | Same value, prefixed with provider if needed |
| `reasoning.fallback` | `slots.reasoning.fallback.model` | Same structure |
| `embedding.provider` | `providers.{name}` (inferred) | v1 per-slot provider → v2 deduplicated |
| `embedding.model` | `slots.embedding.model` | Same value |
| `(new)` | `providers.{name}.apiKeySource` | Default: `file` (maintains auth.json compat) |
| `(new)` | `providers.{name}.envVarName` | Inferred from provider name: `{PROVIDER}_API_KEY` |
| `(new)` | `version` | Set to 2 |
| `(new)` | `defaultModel` | Not set (null) |
| `(new)` | `fallback` | Default values |
| `(new)` | `costLimits` | Not set (null) |

**Key structural change**: v1 had slot assignments directly at root level with per-slot `provider` and `model`. v2 has a separate `providers` section with shared provider configs, and `slots` section with references to named providers. This allows one provider key to serve multiple slots.
