# Data Model: SLM Model Params Extension

**Date**: 2026-07-01 | **Feature**: 006-slm-model-params

## Entities

### ModelEntry (Pydantic BaseModel)

**Location**: `src/openreview_cli/gateway/models.py`

**Current fields**:
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| slots | `list[str]` | required | Model capability slots (reasoning, extraction, etc.) |
| context | `int \| None` | `None` | Context window size |
| dimensions | `int \| None` | `None` | Embedding dimensions |
| ram | `str \| None` | `None` | RAM requirement string |
| recommended | `bool` | `False` | Whether model is recommended |
| status | `str \| None` | `None` | Model availability status |
| note | `str \| None` | `None` | Human-readable note |

**New field**:
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| extra_params | `dict[str, Any] \| None` | `None` | Provider-specific default params for documentation. Informational only — not enforced at runtime. |

**Validation rules**: None — the field is a pass-through dict. Any key-value structure is valid.

### SlotConfig (config.yml dict — not a Pydantic model)

**Location**: Read from `config.yml` by `Gateway._get_slot_config()` in `router.py`

**Current structure** (YAML):
```yaml
gateway:
  models:
    <slot_name>:
      primary: <model_id>
      fallback: <model_id>  # optional
      params:               # optional
        temperature: <float>
        max_tokens: <int>
      extra_params:         # optional — ALREADY PARSED (line 98-100)
        <key>: <value>
```

**No structural change needed** — `extra_params` is already read from config. The change is in how `_get_litellm_kwargs()` processes it (adding protected-key stripping and logging).

### Protected Keys (constant)

**Location**: `src/openreview_cli/gateway/router.py`

**Definition**: `_PROTECTED_KEYS = frozenset({"model", "messages", "input", "timeout"})`

**Purpose**: Keys that `extra_params` must never override. Stripped before merging into call kwargs.

## Relationships

```
config.yml (SlotConfig)
  ├── primary → model ID (used in LiteLLM call)
  ├── params → standard LLM params (temperature, max_tokens)
  └── extra_params → provider-specific params
        ├── stripped of protected keys → warning logged
        └── merged into LiteLLM call kwargs

models.json (ModelEntry)
  └── extra_params → documentation of available provider-specific params
        └── informational only — not merged into calls
```

## State Transitions

N/A — no stateful entities. `extra_params` is configuration, not state.
