# Data Model: AI Gateway v2

> Phase 1 data model artifact for spec 033. Defines all Pydantic models, database tables, enums, and relationships for the v2 gateway. Models are ordered by dependency.

---

## 1. Type Overview

```
V2Config (root)
├── version: int = 2
├── providers: dict[str, ProviderConfig]
│   └── ProviderConfig
│       ├── name: str
│       ├── apiKeySource: ApiKeySource (enum)
│       ├── apiKeyRef: str
│       ├── baseURL: str | None
│       ├── enabled: bool
│       └── envVarName: str
├── slots: dict[str, SlotAssignment]
│   └── SlotAssignment
│       ├── provider: str
│       ├── model: str
│       ├── fallback: SlotAssignment | None
│       └── limits: SlotLimits | None
├── defaultModel: str | None
├── fallback: FallbackConfig
│   ├── retries: int
│   ├── timeout: int
│   └── circuitBreaker: CircuitBreaker | None
└── costLimits: CostLimits | None
    ├── perSessionCents: int | None
    └── dailyCents: int | None

ApiKeySource (enum)
    - keyring
    - file
    - env

AuthEntry (in-memory)
    - provider: str
    - key: str
    - source: ApiKeySource

Database tables:
    - sessions
    - cost_logs (modified)
```

---

## 2. V2Config (Root Configuration Model)

```python
# In src/openreview_cli/gateway/v2_config.py
from pydantic import BaseModel, Field
from typing import Optional


class CircuitBreaker(BaseModel):
    failure_threshold: int = 5
    cooldown_seconds: int = 60


class FallbackConfig(BaseModel):
    retries: int = 2
    timeout: int = 60
    circuit_breaker: Optional[CircuitBreaser] = None


class CostLimits(BaseModel):
    per_session_cents: Optional[int] = None
    daily_cents: Optional[int] = None


class ApiKeySource(str, enum.Enum):
    KEYRING = "keyring"
    FILE = "file"
    ENV = "env"


class ProviderConfig(BaseModel):
    name: str  # e.g., "openai", "openrouter", "voyage"
    api_key_source: ApiKeySource = ApiKeySource.FILE
    api_key_ref: str  # env var name (e.g., "OPENAI_API_KEY") or file fingerprint
    base_url: Optional[str] = None  # custom endpoint
    enabled: bool = True
    env_var_name: str  # e.g., "OPENAI_API_KEY"


class SlotLimits(BaseModel):
    max_tokens: Optional[int] = None
    max_context: Optional[int] = None


class SlotAssignment(BaseModel):
    provider: str  # references ProviderConfig.name
    model: str  # short name (e.g., "gpt-4o") or explicit "provider/model"
    fallback: Optional["SlotAssignment"] = None
    limits: Optional[SlotLimits] = None


class V2Config(BaseModel):
    version: int = Field(default=2, ge=1)
    providers: dict[str, ProviderConfig]
    slots: dict[str, SlotAssignment]  # keys: reasoning, extraction, embedding, reranking, graph, grounding
    default_model: Optional[str] = None
    fallback: FallbackConfig = FallbackConfig()
    cost_limits: Optional[CostLimits] = None
```

**Slot keys validation**: Must be a subset of `["reasoning", "extraction", "embedding", "reranking", "graph", "grounding"]`. At minimum, `reasoning` slot should be configured. Pydantic model validator enforces this.

**Provider name uniqueness**: `providers` dict keys must be unique (enforced by dict type). Each key should be the normalized provider name (lowercase, no spaces).

**Relationship direction**: `SlotAssignment.provider` → `ProviderConfig.name` (dereference). A provider must exist in `providers` before a slot can reference it. Validated at load time.

---

## 3. ProviderConfig (Provider Definition)

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | str | Yes | — | Provider identifier (e.g., "openai", "anthropic") |
| `api_key_source` | ApiKeySource | No | `file` | Where to resolve the API key |
| `api_key_ref` | str | Yes | — | If `env`: env var name. If `file`: auth.json key. If `keyring`: keyring entry name |
| `base_url` | str\|None | No | None | Custom endpoint URL for OpenAI-compatible APIs |
| `enabled` | bool | No | True | Whether this provider is active |
| `env_var_name` | str | Yes | — | Canonical env var name (e.g., "ANTHROPIC_API_KEY") |

**Validation rules**:
- `name` must be lowercase, alphanumeric with hyphens/underscores only
- `env_var_name` must match `^[A-Z][A-Z0-9_]*$` (standard env var convention)
- If `base_url` is set, it must be a valid URL with scheme (http/https)
- At least one provider must have `enabled = True`

---

## 4. SlotAssignment (Slot → Model Mapping)

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `provider` | str | Yes | — | Provider name (must exist in `providers`) |
| `model` | str | Yes | — | Short name (e.g., "gpt-4o") or explicit "provider/model" |
| `fallback` | SlotAssignment\|None | No | None | Fallback provider/model if primary fails |
| `limits` | SlotLimits\|None | No | None | Per-slot token limits |

**Validation rules**:
- `provider` must reference a key in `providers` (validated at config load)
- If `model` contains `/`, it is treated as explicit `provider/model` and passed through to LiteLLM
- If `model` is a short name, it is resolved at runtime via `resolver.py`
- `fallback.model` can be a different model or the same model via a different provider

---

## 5. ApiKeySource Enum

| Value | Meaning | Storage Location | Resolve Strategy |
|-------|---------|-----------------|------------------|
| `keyring` | OS keyring | macOS Keychain / Windows Credential Manager / Linux Secret Service | `keyring.get_password("openreview", provider)` |
| `file` | auth.json file | `~/.config/openreview/auth.json` | `json.load(auth_path)[provider]` |
| `env` | Environment variable | Process environment | `os.environ[api_key_ref]` |

**Resolution priority at runtime**: `env` > `keyring` > `file`. The source field in ProviderConfig is a *hint* for write operations (where to store). Read operations always check all three tiers in priority order.

---

## 6. AuthEntry (In-Memory Representation)

```python
# Used by keyring_store.py and auth.py for the auth list/remove flow
@dataclass
class AuthEntry:
    provider: str       # Provider identifier (e.g., "openai")
    key: str            # The actual API key (in-memory only, never serialized)
    source: ApiKeySource  # Where the key was loaded from
    
    def masked_key(self) -> str:
        """Return last 4 chars only for display."""
        if len(self.key) < 8:
            return "****"
        return "****" + self.key[-4:]
```

---

## 7. Database Tables

### cost_logs (Modified)

Existing table with one change: `session_id` becomes nullable.

```sql
-- Migration: 004_nullable_session.sql
-- Makes session_id nullable in cost_logs. Cost tracking must succeed
-- regardless of whether a session reference is available.

-- Step 1: Drop the existing FK constraint (SQLite requires table rebuild)
-- SQLite does not support ALTER DROP CONSTRAINT. Strategy:
--   1. Create new table with nullable session_id
--   2. Copy data
--   3. Drop old table
--   4. Rename new table

CREATE TABLE cost_logs_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,                           -- NULLABLE (was NOT NULL)
    slot TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    cost_cents INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

INSERT INTO cost_logs_new SELECT * FROM cost_logs;
DROP TABLE cost_logs;
ALTER TABLE cost_logs_new RENAME TO cost_logs;
```

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Auto-incrementing ID |
| session_id | TEXT | NULLABLE, FK → sessions(id) | Optional session reference (was NOT NULL) |
| slot | TEXT | NOT NULL | Slot name (reasoning, extraction, etc.) |
| provider | TEXT | NOT NULL | Provider name |
| model | TEXT | NOT NULL | Model string (resolved) |
| prompt_tokens | INTEGER | NOT NULL DEFAULT 0 | Input token count |
| completion_tokens | INTEGER | NOT NULL DEFAULT 0 | Output token count |
| cost_cents | INTEGER | NOT NULL DEFAULT 0 | Estimated cost in cents (integer) |
| created_at | TEXT | NOT NULL DEFAULT datetime('now') | ISO 8601 timestamp |

**Indexes**: `idx_cost_logs_session_id` on `session_id`, `idx_cost_logs_created_at` on `created_at`.

### sessions (Target for FK)

```sql
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,                          -- UUID v4
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    user_id TEXT,                                 -- Optional user identifier
    tool_version TEXT                             -- openreview-cli version
);
```

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | TEXT | PRIMARY KEY | UUID v4 (generated at session start) |
| started_at | TEXT | NOT NULL DEFAULT datetime('now') | Session creation timestamp |
| user_id | TEXT | NULLABLE | User identifier (for multi-user, future) |
| tool_version | TEXT | NULLABLE | openreview-cli version that created the session |

**Note**: This table already exists in the current schema (generated by `database.py`). The migration only changes `cost_logs.session_id` to be nullable.

---

## 8. ModelRegistry Entry (Existing, No Change)

From `models.json` — each entry:

```json
{
    "model_id": "gpt-4o",
    "provider": "openai",
    "slots": ["reasoning", "extraction"],
    "context": 128000,
    "dimensions": null,
    "recommended": true,
    "status": "stable"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `model_id` | str | Short name (key for resolution) |
| `provider` | str | Primary provider that serves this model |
| `slots` | list[str] | Compatible slot names |
| `context` | int\|null | Max context length in tokens |
| `dimensions` | int\|null | Embedding dimensions (embedding models only) |
| `recommended` | bool | Whether this is a recommended model |
| `status` | str | "stable", "beta", "deprecated" |

---

## 9. Relationships Diagram

```
V2Config
  │
  ├── providers: dict[str, ProviderConfig]
  │     │
  │     ├── name ──────────────────────────┐
  │     ├── api_key_source ──→ ApiKeySource │
  │     └── env_var_name                    │
  │                                         │
  └── slots: dict[str, SlotAssignment]      │
        │                                   │
        └── provider ───────────────────────┘ (references ProviderConfig.name)
        └── model ──→ resolved via ──→ ModelRegistry (models.json)
        └── fallback ──→ SlotAssignment (recursive)

  AuthEntry (in-memory, not persisted)
    ├── provider
    ├── key
    └── source: ApiKeySource

  Database:
    sessions 1──────* cost_logs
      id ───────────── session_id (nullable)
```

---

## 10. Migration Path (Schema Changes)

| Change | Type | Backward Compatible? | Migration Required? |
|--------|------|---------------------|-------------------|
| Add `grounding` to `GatewayModels` Pydantic schema | Additive | Yes | No |
| Make `cost_logs.session_id` nullable | Database | Yes | Yes (004_nullable_session.sql) |
| Replace v1 config format with v2 provider-first | Config file | No | Yes (migrate config command) |
| Add `keyring` as optional auth store | Additive | Yes (fallback exists) | No |
| Add `Session` table | Additive | Yes | No (created via `CREATE TABLE IF NOT EXISTS`) |

**Migration order**: (1) Run 004_nullable_session.sql (can run anytime, backward-compatible). (2) User runs `openreview migrate config` to convert config file. (3) Old v1 config can be deleted after verification.
