# CLI Commands — AI Gateway v2

> Contract specification for every CLI command added or modified by spec 033. Each command entry documents signature, flags, stdin/stdout contract, exit codes, and JSON output schema.

---

## Conventions

- **Exit codes**: 0 = success, 1 = user error (invalid input, missing args), 2 = config error (missing/invalid config, schema violation), 3 = provider error (API failure, auth failure, rate limit)
- **JSON error format** (when `--format json` specified): `{"error": string, "code": int, "message": string}` to stderr
- `--format` flag: `text` (default, Rich table) or `json` (machine-parseable). All commands with output support this flag.
- All commands MUST work in non-TTY context. No prompts, no blocking reads from stdin unless stdin is piped data.

---

## 1. `openreview gateway setup`

**Purpose**: Apply a JSON config from stdin atomically. Replaces interactive wizard for CLI contexts.

**Signature**:
```
openreview gateway setup [--dry-run] [--format text|json]
```

**Flags**:
| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--dry-run` | bool | False | Validate the piped JSON and report what would be written, without modifying any files |
| `--format` | str | `text` | Output format: `text` (human) or `json` (machine-parseable) |

**Stdin**: Complete JSON config conforming to v2 config schema. Read once, parsed atomically. See `contracts/json-stdin-schema.md` for schema.

**Stdout (success, text mode)**:
```
✓ Gateway configuration applied.
  Providers: openai, voyage (2 configured)
  Slots: reasoning, embedding (2 configured)
  Default model: not set
```

**Stdout (success, JSON mode)**:
```json
{
    "status": "applied",
    "providers": ["openai", "voyage"],
    "slots": ["reasoning", "embedding"],
    "dry_run": false
}
```

**Stderr (validation failure)**:
```
Error: Config validation failed.
  - providers.openai.name: field required
  - providers.voyage.apiKeyRef: field required
```

**Exit codes**:
| Code | Condition |
|------|-----------|
| 0 | Config applied successfully (or dry run succeeded) |
| 1 | Validation failure (invalid JSON, missing required field) |
| 1 | No stdin and no TTY (usage printed to stderr) |

**Edge cases**:
- Empty stdin + no TTY → exit 1, "No config provided on stdin. Run `openreview gateway setup --help` for usage."
- Invalid JSON (parse error) → exit 1, "Parse error at line 3: expected ','"
- Partial write protection: no files modified until full validation passes

---

## 2. `openreview gateway status`

**Signature**:
```
openreview gateway status [--format text|json]
```

**Flags**:
| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--format` | str | `text` | Output format |

**Stdout (text mode)**:
```
Gateway Status
──────────────
Providers:
  openai    ✓ enabled (api key: file)
  voyage    ✓ enabled (api key: file)

Slots:
  reasoning   openai/gpt-4o          ✓ reachable
  embedding   voyage/voyage-3        ✓ reachable
  extraction  —                      not configured

Default model: not set
```

**Stdout (JSON mode)**:
```json
{
    "version": 2,
    "providers": {
        "openai": {"enabled": true, "source": "file"},
        "voyage": {"enabled": true, "source": "file"}
    },
    "slots": {
        "reasoning": {"provider": "openai", "model": "gpt-4o", "reachable": true},
        "embedding": {"provider": "voyage", "model": "voyage-3", "reachable": true},
        "extraction": null,
        "reranking": null,
        "graph": null,
        "grounding": null
    },
    "default_model": null
}
```

**Exit codes**:
| Code | Condition |
|------|-----------|
| 0 | Config is valid and loaded |
| 2 | Config not found or invalid |

---

## 3. `openreview models available`

**Purpose**: List all models from static registry that are reachable with currently configured API keys.

**Signature**:
```
openreview models available [--provider <name>] [--format text|json]
```

**Flags**:
| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--provider` | str | None | Filter to a single provider |
| `--format` | str | `text` | Output format |

**Stdout (text mode)**:
```
Model             Provider     Slots                  Context
gpt-4o            openai       reasoning, extraction   128K
gpt-4o-mini       openai       reasoning, extraction   128K
text-embedding-3  openai       embedding               8K
claude-sonnet-4.5 anthropic    reasoning, extraction   200K
voyage-3          voyage       embedding                —
rerank-2          voyage       reranking                —
```

**Stdout (JSON mode)**:
```json
{
    "models": [
        {"short_name": "gpt-4o", "provider": "openai", "slots": ["reasoning", "extraction"], "context": 128000},
        {"short_name": "voyage-3", "provider": "voyage", "slots": ["embedding"], "context": null}
    ],
    "providers_found": ["openai", "voyage"],
    "total": 2
}
```

**Stderr (empty result)**:
```
No models available. No API keys configured. Run `openreview gateway setup` to add providers.
```

**Exit codes**:
| Code | Condition |
|------|-----------|
| 0 | Query completed (result may be empty) |
| 2 | Config not found making provider list undetermined |

**Performance**: Must complete in <1s for up to 3 providers × 33 models (pure static lookup, no network calls).

---

## 4. `openreview set <slot> <model> [fallback]`

**Purpose**: Assign a model to a slot. Supports short-name resolution.

**Signature**:
```
openreview set <slot> <model> [fallback] [--format text|json]
```

**Arguments**:
| Arg | Required | Description |
|-----|----------|-------------|
| `slot` | Yes | Slot name: one of `reasoning`, `extraction`, `embedding`, `reranking`, `graph`, `grounding` |
| `model` | Yes | Model short name (e.g., `gpt-4o`) or explicit `provider/model` |
| `fallback` | No | Optional fallback model (same format as `model`) |

**Stdout (text mode)**:
```
✓ reasoning → openai/gpt-4o (resolved from "gpt-4o")
```

**Stdout (JSON mode)**:
```json
{
    "status": "configured",
    "slot": "reasoning",
    "provider": "openai",
    "model": "gpt-4o",
    "resolved": "openai/gpt-4o",
    "fallback": null
}
```

**Stderr (resolution failure)**:
```
Error: No configured provider has model 'unknown-model'.
Available models: gpt-4o, gpt-4o-mini, claude-sonnet-4.5, ...
```

**Exit codes**:
| Code | Condition |
|------|-----------|
| 0 | Slot configured successfully |
| 1 | Invalid slot name, missing argument, or model not found |
| 2 | Config file error (permissions, schema) |

---

## 5. `openreview auth add <provider> [key]`

**Purpose**: Store an API key for a provider. Stores to OS keyring when available, falls back to `auth.json`.

**Signature**:
```
openreview auth add <provider> [key] [--base-url <url>] [--format text|json]
```

**Flags**:
| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--base-url` | str | None | Custom base URL for OpenAI-compatible endpoints |
| `--format` | str | `text` | Output format |

**Arguments**:
| Arg | Required | Description |
|-----|----------|-------------|
| `provider` | Yes | Provider name (e.g., `openai`, `anthropic`, `openrouter`) |
| `key` | No | API key. If omitted, prompted (only if TTY). For non-TTY, key is required. |

**Stdout (text mode)**:
```
✓ API key for openrouter stored in keyring
```
Or (fallback):
```
✓ API key for openrouter stored in auth.json
⚠ OS keyring unavailable. For better security, install keyring: pip install keyring
```

**Stdout (JSON mode)**:
```json
{
    "status": "stored",
    "provider": "openrouter",
    "source": "keyring",
    "warning": null
}
```

**Exit codes**:
| Code | Condition |
|------|-----------|
| 0 | Key stored successfully |
| 1 | Provider name missing, key missing in non-TTY |
| 2 | File permission error writing auth.json |

---

## 6. `openreview auth list`

**Purpose**: Show configured providers with key sources and masked key values.

**Signature**:
```
openreview auth list [--format text|json]
```

**Flags**:
| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--format` | str | `text` | Output format |

**Stdout (text mode)**:
```
Provider     Source    Key
openai       env       ****-abc1
openrouter   keyring   ****-xyz3
voyage       file      ****-def4
```

**Stdout (JSON mode)**:
```json
{
    "entries": [
        {"provider": "openai", "source": "env", "key_masked": "****-abc1"},
        {"provider": "openrouter", "source": "keyring", "key_masked": "****-xyz3"},
        {"provider": "voyage", "source": "file", "key_masked": "****-def4"}
    ],
    "total": 3
}
```

**Exit codes**:
| Code | Condition |
|------|-----------|
| 0 | Always (empty list is valid) |

---

## 7. `openreview auth remove <provider>`

**Purpose**: Delete a provider's API key from whichever store it was found in.

**Signature**:
```
openreview auth remove <provider> [--format text|json]
```

**Arguments**:
| Arg | Required | Description |
|-----|----------|-------------|
| `provider` | Yes | Provider name to remove |

**Stdout (text mode)**:
```
✓ API key for openrouter removed from keyring
```

**Stdout (JSON mode)**:
```json
{
    "status": "removed",
    "provider": "openrouter",
    "source": "keyring"
}
```

**Stderr (not found)**:
```
Key for provider 'openrouter' not found in any store.
```

**Exit codes**:
| Code | Condition |
|------|-----------|
| 0 | Key removed successfully |
| 1 | Provider argument missing |
| 1 | Key not found in any store |

---

## 8. `openreview migrate config`

**Purpose**: Convert v1 config.yml to v2 provider-first format.

**Signature**:
```
openreview migrate config [--format text|json]
```

**Flags**:
| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--format` | str | `text` | Output format |

**Stdout (text mode)**:
```
✓ Config migrated from v1 to v2.
  Previous: /home/user/.config/openreview/config.yml (v1)
  Current:  /home/user/.config/openreview/config.yml (v2)
  Backup:   /home/user/.config/openreview/config.yml.bak
  auth.json: unchanged
```

**Stdout (JSON mode)**:
```json
{
    "status": "migrated",
    "from_version": 1,
    "to_version": 2,
    "config_path": "/home/user/.config/openreview/config.yml",
    "backup_path": "/home/user/.config/openreview/config.yml.bak",
    "auth_json_modified": false
}
```

**Stderr (already v2)**:
```
Config is already v2 format. Nothing to migrate.
```

**Exit codes**:
| Code | Condition |
|------|-----------|
| 0 | Migration complete (or already v2 — no-op) |
| 2 | v1 config not found or unreadable |
| 2 | v2 config file write error |

---

## 9. `openreview gateway costs`

**Purpose**: Query cost records from the database.

**Signature**:
```
openreview gateway costs [--today] [--session <id>] [--since <date>] [--format text|json]
```

**Flags**:
| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--today` | bool | False | Filter to today's records only |
| `--session` | str | None | Filter to a specific session ID |
| `--since` | str | None | ISO 8601 date string (e.g., "2026-07-01") |
| `--format` | str | `text` | Output format |

**Stdout (text mode)**:
```
Date       Slot        Model       Provider   Prompt  Completion  Cost(cents)
2026-07-13 reasoning   gpt-4o      openai     1,234   567         3.2
2026-07-13 embedding   voyage-3    voyage     456     88          0.5
─────────────────────────────────────────────────────────────────────────
Total:                                                            3.7¢
```

**Stdout (JSON mode)**:
```json
{
    "records": [
        {"date": "2026-07-13", "slot": "reasoning", "model": "gpt-4o", "provider": "openai", "prompt_tokens": 1234, "completion_tokens": 567, "cost_cents": 3.2, "session_id": "abc-123"}
    ],
    "total_cost_cents": 3.7,
    "record_count": 2,
    "filters": {"today": true}
}
```

**Exit codes**:
| Code | Condition |
|------|-----------|
| 0 | Query completed (empty result is valid) |
| 2 | Database file not found |
| 1 | Invalid session ID format |

---

## 10. Existing Commands (Unchanged)

The following commands are NOT modified by this spec. Their contracts remain as documented in their original specs:

- `openreview parse <file>` — Document parsing (Phase 2)
- `openreview strip <file>` — PII stripping (Phase 3)
- `openreview chunk <file>` — Document chunking (Phase 6)
- `openreview ingest <dir>` — Vector ingestion (Phase 7)
- `openreview retrieve <query>` — Semantic retrieval (Phase 7)
- `openreview precheck <file>` — Single-party review (Phase 5)
- `openreview review <file>` — Single-party review (Phase 5)
