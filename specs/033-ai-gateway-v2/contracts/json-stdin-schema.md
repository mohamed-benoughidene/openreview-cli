# JSON-Stdin Schema — `gateway setup`

> Contract specification for the JSON accepted by `openreview gateway setup` via stdin. Schema is a subset of the v2 config schema, omitting file-system concerns (the applier handles paths).

---

## Schema

The JSON payload must conform to the v2 config schema with these constraints:

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `version` | int | Yes | 2 | Must be 2. Future versions may accept 3+. |
| `providers` | object | Yes | — | Map of provider name → ProviderConfig |
| `slots` | object | Yes | — | Map of slot name → SlotAssignment |
| `defaultModel` | str\|null | No | null | Default model short name |
| `fallback` | object | No | `{"retries": 2, "timeout": 60}` | Fallback settings |
| `costLimits` | object\|null | No | null | Cost limits |

---

## ProviderConfig (JSON)

```json
{
    "name": "openai",
    "api_key_source": "env",
    "api_key_ref": "OPENAI_API_KEY",
    "base_url": null,
    "enabled": true,
    "env_var_name": "OPENAI_API_KEY"
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | str | Yes | — | Provider identifier (must be unique) |
| `api_key_source` | str | No | `"file"` | One of: `"keyring"`, `"file"`, `"env"` |
| `api_key_ref` | str | Yes | — | Key reference (env var name, file key, or keyring entry) |
| `base_url` | str\|null | No | null | Custom endpoint URL |
| `enabled` | bool | No | true | Whether provider is active |
| `env_var_name` | str | Yes | — | Canonical env var name |

---

## SlotAssignment (JSON)

```json
{
    "provider": "openai",
    "model": "gpt-4o",
    "fallback": {
        "provider": "openai",
        "model": "gpt-4o-mini"
    },
    "limits": {
        "max_tokens": 4096,
        "max_context": 128000
    }
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `provider` | str | Yes | — | Must reference a key in `providers` |
| `model` | str | Yes | — | Short name or explicit `provider/model` |
| `fallback` | object\|null | No | null | Recursive SlotAssignment |
| `limits` | object\|null | No | null | `{max_tokens, max_context}` |

---

## Example: Minimal Valid JSON

```json
{
    "version": 2,
    "providers": {
        "openai": {
            "name": "openai",
            "api_key_ref": "OPENAI_API_KEY",
            "env_var_name": "OPENAI_API_KEY"
        }
    },
    "slots": {
        "reasoning": {
            "provider": "openai",
            "model": "gpt-4o"
        }
    }
}
```

---

## Example: Full JSON with All Options

```json
{
    "version": 2,
    "providers": {
        "openai": {
            "name": "openai",
            "api_key_source": "env",
            "api_key_ref": "OPENAI_API_KEY",
            "base_url": null,
            "enabled": true,
            "env_var_name": "OPENAI_API_KEY"
        },
        "voyage": {
            "name": "voyage",
            "api_key_source": "file",
            "api_key_ref": "voyage",
            "base_url": null,
            "enabled": true,
            "env_var_name": "VOYAGE_API_KEY"
        },
        "custom-local": {
            "name": "custom-local",
            "api_key_source": "env",
            "api_key_ref": "CUSTOM_API_KEY",
            "base_url": "http://localhost:11434/v1",
            "enabled": true,
            "env_var_name": "CUSTOM_API_KEY"
        }
    },
    "slots": {
        "reasoning": {
            "provider": "openai",
            "model": "gpt-4o",
            "fallback": {
                "provider": "openai",
                "model": "gpt-4o-mini"
            },
            "limits": {
                "max_tokens": 8192,
                "max_context": 128000
            }
        },
        "extraction": {
            "provider": "openai",
            "model": "gpt-4o-mini"
        },
        "embedding": {
            "provider": "voyage",
            "model": "voyage-3"
        },
        "reranking": {
            "provider": "voyage",
            "model": "rerank-2"
        },
        "graph": {
            "provider": "openai",
            "model": "gpt-4o-mini"
        },
        "grounding": {
            "provider": "openai",
            "model": "gpt-4o"
        }
    },
    "default_model": "gpt-4o",
    "fallback": {
        "retries": 3,
        "timeout": 120,
        "circuit_breaker": {
            "failure_threshold": 5,
            "cooldown_seconds": 60
        }
    },
    "cost_limits": {
        "per_session_cents": 100,
        "daily_cents": 1000
    }
}
```

---

## Error Format

On validation failure, the command prints to stderr:

**Text mode**:
```
Error: Config validation failed.
  - providers.openai.name: field required
  - slots.reasoning.provider: field required
```

**JSON mode** (`--format json`):
```json
{
    "error": "validation_failed",
    "code": 1,
    "message": "Config validation failed",
    "details": [
        {"field": "providers.openai.name", "error": "field required"},
        {"field": "slots.reasoning.provider", "error": "field required"}
    ]
}
```

**Parse error** (invalid JSON):
```json
{
    "error": "parse_error",
    "code": 1,
    "message": "Parse error at line 3, column 10: Expected ',' or '}'",
    "details": []
}
```

---

## Implementation Notes

1. **Atomic write**: All files (config.yml, auth.json) are written only after full validation passes. Use a temp file + rename pattern to prevent partial writes on crash.
2. **Key handling**: If `api_key_source` is `file` and the JSON includes an `api_key` field (not in schema but accepted for convenience), the applier writes it to `auth.json`. If `api_key_source` is `env` or `keyring`, the `api_key` field is ignored (the key must be in the specified source already).
3. **Slot validation**: Each slot name is validated against the allowed set. Unknown slots produce a validation error.
4. **Provider reference**: Every slot's `provider` must reference an existing provider key. Cross-reference validation happens after provider block parsing.
5. **Size limit**: The JSON payload should not exceed 1 MB (typical payload is <100 KB). Large payloads are rejected with a clear error.
