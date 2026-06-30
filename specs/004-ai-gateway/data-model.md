# Data Model: AI Gateway

**Date**: 2026-06-25 | **Spec**: [spec.md](../specs/004-ai-gateway/spec.md)

## Entities

### 1. SlotConfig

**Purpose**: Configuration for a single task slot (reasoning, extraction, embedding, reranking—optional, disabled by default—graph).

**Fields**:
- `primary: str` — Model identifier in format `provider/model-id` (e.g., `openai/gpt-4o`, `ollama/llama3.1`)
- `fallback: str | None` — Optional fallback model identifier
- `params: ModelParams | None` — Optional model parameters (temperature, max_tokens, etc.)

**Validation**:
- `primary` must be non-empty
- `primary` must match format `provider/model-id` or be a valid Ollama model name
- `fallback` must match same format if present

**State Transitions**: N/A (configuration object, immutable after creation)

**Storage**: YAML config file (`~/.config/openreview/config.yml` under `gateway.models.<slot>`)

**Example**:
```python
SlotConfig(
    primary="openai/gpt-4o",
    fallback="anthropic/claude-3-5-sonnet-20241022",
    params=ModelParams(temperature=0.1, max_tokens=4000)
)
```

---

### 2. ModelParams

**Purpose**: Model-specific parameters for a slot.

**Fields**:
- `temperature: float = 0.7` — Sampling temperature (0.0 to 2.0)
- `max_tokens: int = 4000` — Maximum tokens in response
- `dimensions: int | None = None` — Embedding dimensions (embedding slot only)
- `top_p: float | None = None` — Nucleus sampling parameter
- `stop: list[str] | None = None` — Stop sequences

**Validation**:
- `temperature` must be between 0.0 and 2.0
- `max_tokens` must be positive
- `dimensions` must be positive if present
- `top_p` must be between 0.0 and 1.0 if present

**Storage**: YAML config file (nested under `gateway.models.<slot>.params`)

---

### 3. ReviewSession

**Purpose**: Tracks a single review invocation for cost aggregation.

**Fields**:
- `session_id: str` — UUID auto-generated per `openreview review` invocation
- `started_at: float` — Unix timestamp when review started
- `ended_at: float | None` — Unix timestamp when review completed (None if in progress)
- `total_cost_usd: float` — Accumulated cost for this session
- `total_input_tokens: int` — Accumulated input tokens
- `total_output_tokens: int` — Accumulated output tokens

**Validation**:
- `session_id` must be valid UUID format
- `started_at` must be positive
- `ended_at` must be >= `started_at` if present
- `total_cost_usd` must be non-negative
- Token counts must be non-negative

**State Transitions**:
- `created` → `in_progress` (when first API call made)
- `in_progress` → `completed` (when review finishes)

**Storage**: SQLite database (`~/.local/share/openreview/gateway.db`, table `review_sessions`)

**Example**:
```python
ReviewSession(
    session_id="550e8400-e29b-41d4-a716-446655440000",
    started_at=1719324000.0,
    ended_at=None,
    total_cost_usd=0.0,
    total_input_tokens=0,
    total_output_tokens=0
)
```

---

### 4. CostRecord

**Purpose**: Per-call record of token usage and cost.

**Fields**:
- `record_id: int` — Auto-increment primary key
- `session_id: str` — Foreign key to ReviewSession
- `slot: str` — Slot name (reasoning, extraction, embedding, graph — required; reranking — optional, disabled by default)
- `model: str` — Model identifier used
- `provider: str` — Provider name
- `input_tokens: int` — Tokens in prompt
- `output_tokens: int` — Tokens in response
- `cost_usd: float` — Estimated cost in USD
- `timestamp: float` — Unix timestamp of API call
- `fallback_used: bool` — True if fallback model was used
- `latency_ms: int` — Request latency in milliseconds

**Validation**:
- `session_id` must reference existing ReviewSession
- `slot` must be one of: reasoning, extraction, embedding, reranking, graph. Reranking is optional and disabled by default.
- `input_tokens`, `output_tokens` must be non-negative
- `cost_usd` must be non-negative
- `latency_ms` must be non-negative

**Storage**: SQLite database (table `cost_records`)

**Example**:
```python
CostRecord(
    record_id=1,
    session_id="550e8400-e29b-41d4-a716-446655440000",
    slot="reasoning",
    model="openai/gpt-4o",
    provider="openai",
    input_tokens=1500,
    output_tokens=800,
    cost_usd=0.023,
    timestamp=1719324060.0,
    fallback_used=False,
    latency_ms=1234
)
```

---

### 5. ModelRegistryEntry

**Purpose**: Cached information about an available model.

**Fields**:
- `provider: str` — Provider name
- `model_id: str` — Model identifier
- `display_name: str` — Human-readable name
- `slot_compatibility: list[str]` — Which slots this model can serve (e.g., ["reasoning", "extraction", "graph"])
- `context_window: int | None` — Max context length in tokens
- `ram_required_mb: int | None` — RAM required for local models
- `pricing_input_usd_per_mtok: float | None` — Cost per million input tokens
- `pricing_output_usd_per_mtok: float | None` — Cost per million output tokens
- `is_local: bool` — True if model runs locally (Ollama)

**Validation**:
- `provider` must be non-empty
- `model_id` must be non-empty
- `slot_compatibility` must be non-empty list
- `context_window` must be positive if present
- `ram_required_mb` must be positive if present
- Pricing fields must be non-negative if present

**Storage**: JSON cache file (`~/.cache/openreview/model_registry.json`)

**Example**:
```python
ModelRegistryEntry(
    provider="openai",
    model_id="gpt-4o",
    display_name="GPT-4o",
    slot_compatibility=["reasoning", "extraction", "graph"],
    context_window=128000,
    ram_required_mb=None,
    pricing_input_usd_per_mtok=5.0,
    pricing_output_usd_per_mtok=15.0,
    is_local=False
)
```

---

### 6. AuthStore

**Purpose**: Secure storage for API keys.

**Fields**:
- `keys: dict[str, str]` — Provider name → API key mapping
- `file_path: Path` — Path to auth.json file

**Validation**:
- `keys` values must be non-empty strings
- `file_path` must have mode 600 (enforced on write)

**Storage**: JSON file (`~/.config/openreview/auth.json`, chmod 600)

**Security**:
- File permissions enforced on write (chmod 600)
- Permissions checked and fixed on read if incorrect
- Keys never logged (redacted in all output)
- Environment variables override file values

**Example**:
```python
AuthStore(
    keys={
        "openai": "sk-...",
        "anthropic": "sk-ant-...",
        "cohere": "..."
    },
    file_path=Path.home() / ".config/openreview/auth.json"
)
```

---

## Relationships

```
ReviewSession (1) ──< (N) CostRecord
     │
     └── session_id (FK)

SlotConfig (1) ──< (1) ModelParams
     │
     └── params (embedded)

ModelRegistryEntry (standalone)
     │
     └── cached in JSON, refreshed periodically

AuthStore (standalone)
     │
     └── keys referenced by provider name
```

---

## Validation Rules

### SlotConfig Validation
- `primary` format: `provider/model-id` (e.g., `openai/gpt-4o`)
- Special case: Ollama models can be `ollama/model-name` or just `model-name`
- `fallback` must match same format if present
- `params` optional, validated by ModelParams rules

### ModelParams Validation
- `temperature`: 0.0 ≤ x ≤ 2.0
- `max_tokens`: x > 0
- `dimensions`: x > 0 (if present)
- `top_p`: 0.0 ≤ x ≤ 1.0 (if present)

### CostRecord Validation
- `input_tokens`, `output_tokens`: x ≥ 0
- `cost_usd`: x ≥ 0.0
- `latency_ms`: x ≥ 0
- `session_id` must reference existing ReviewSession

### ReviewSession Validation
- `session_id`: valid UUID format
- `started_at`: x > 0
- `ended_at`: x ≥ `started_at` (if present)
- `total_cost_usd`: x ≥ 0.0
- Token counts: x ≥ 0

---

## State Transitions

### ReviewSession Lifecycle
```
created (ended_at=None, total_cost_usd=0)
    ↓
in_progress (first API call made, total_cost_usd>0)
    ↓
completed (ended_at set, review finished)
```

### CostRecord Lifecycle
```
created (inserted after each API call)
    ↓
persisted (immutable, never updated or deleted)
```

---

## Storage Locations

| Entity | Storage | Path | Format |
|--------|---------|------|--------|
| SlotConfig | YAML config | `~/.config/openreview/config.yml` | YAML |
| ModelParams | YAML config | `~/.config/openreview/config.yml` | YAML |
| ReviewSession | SQLite | `~/.local/share/openreview/gateway.db` | SQL table |
| CostRecord | SQLite | `~/.local/share/openreview/gateway.db` | SQL table |
| ModelRegistryEntry | JSON cache | `~/.cache/openreview/model_registry.json` | JSON |
| AuthStore | JSON file | `~/.config/openreview/auth.json` | JSON (chmod 600) |
