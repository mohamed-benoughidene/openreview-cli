# Contract: Gateway Config Schema

**Date**: 2026-06-25 | **Spec**: [spec.md](../../specs/004-ai-gateway/spec.md)

## Overview

The gateway configuration is stored in YAML format at `~/.config/openreview/config.yml` under the `gateway` key. This schema defines the structure, validation rules, and defaults for all gateway configuration.

## Schema Definition

```yaml
gateway:
  # Model assignments for each slot
  models:
    reasoning:
      primary: "ollama/qwen3:8b"  # Required: provider/model-id
      fallback: null  # Optional: provider/model-id
      params:  # Optional: model parameters
        temperature: 0.1
        max_tokens: 4000
    
    extraction:
      primary: "ollama/qwen3:4b"
      fallback: null
      params:
        temperature: 0.0
        max_tokens: 2000
    
    embedding:
      primary: "ollama/nomic-embed-text"
      fallback: null
      params:
        dimensions: 512  # Embedding-specific
    
    reranking:
      primary: "ollama/qwen3-reranker-0.6b"
      fallback: null
      params: {}
    
    graph:
      primary: "ollama/qwen3:8b"
      fallback: null
      params:
        temperature: 0.0
        max_tokens: 4000
  
  # Fallback and retry behavior
  fallback:
    retries: 2  # Number of retry attempts (0 = no retries)
    retry_delay: 1.0  # Initial delay in seconds (exponential backoff)
    timeout: 60  # Request timeout in seconds
    on_failure: "error"  # error | skip | warn
  
  # Cost limits (in USD cents)
  cost_limits:
    per_review_cents: 100  # $1.00 per review
    daily_cents: 1000  # $10.00 per day
  
  # Model registry
  registry:
    refresh_days: 7  # Refresh cached registry every N days
    remote_url: "https://example.com/models.json"  # Remote registry URL
  
  # Observability
  logging:
    level: "info"  # debug | info | warning | error
    debug_file: "~/.openreview/gateway.log"  # Debug log file path
```

## Field Specifications

### `gateway.models.<slot>`

**Type**: Object

**Required Fields**:
- `primary` (string): Model identifier in format `provider/model-id`
  - Examples: `openai/gpt-4o`, `anthropic/claude-3-5-sonnet-20241022`, `ollama/llama3.1`
  - Validation: Must be non-empty, must contain `/` or be valid Ollama model name

**Optional Fields**:
- `fallback` (string | null): Fallback model identifier (same format as `primary`)
- `params` (object | null): Model-specific parameters

### `gateway.models.<slot>.params`

**Type**: Object

**Common Fields** (all optional):
- `temperature` (float): Sampling temperature, 0.0 to 2.0, default 0.7
- `max_tokens` (integer): Maximum tokens in response, > 0, default 4000
- `top_p` (float): Nucleus sampling parameter, 0.0 to 1.0
- `stop` (list[string]): Stop sequences

**Embedding-Specific Fields**:
- `dimensions` (integer): Embedding vector dimensions, > 0

**Validation Rules**:
- All fields are optional
- Values must be within specified ranges
- Unknown fields are ignored (forward compatibility)

### `gateway.fallback`

**Type**: Object

**Fields** (all optional with defaults):
- `retries` (integer): Number of retry attempts, ≥ 0, default 2
- `retry_delay` (float): Initial delay in seconds, > 0, default 1.0
- `timeout` (integer): Request timeout in seconds, > 0, default 60
- `on_failure` (string): Failure behavior, one of: `error`, `skip`, `warn`, default `error`

**Validation Rules**:
- `on_failure` must be one of the allowed values
- Numeric values must be positive

### `gateway.cost_limits`

**Type**: Object

**Fields** (all optional with defaults):
- `per_review_cents` (integer): Per-review cost limit in cents, ≥ 0, default 100 ($1.00)
- `daily_cents` (integer): Daily cost limit in cents, ≥ 0, default 1000 ($10.00)

**Validation Rules**:
- Values must be non-negative integers
- Zero means no limit (unlimited spending)

### `gateway.registry`

**Type**: Object

**Fields** (all optional with defaults):
- `refresh_days` (integer): Refresh interval in days, > 0, default 7
- `remote_url` (string): Remote registry URL, must be valid URL

**Validation Rules**:
- `refresh_days` must be positive
- `remote_url` must be valid URL format

### `gateway.logging`

**Type**: Object

**Fields** (all optional with defaults):
- `level` (string): Log level, one of: `debug`, `info`, `warning`, `error`, default `info`
- `debug_file` (string): Debug log file path, default `~/.openreview/gateway.log`

**Validation Rules**:
- `level` must be one of the allowed values
- `debug_file` must be valid file path

## Environment Variable Overrides

All config values can be overridden via environment variables with the `OPENREVIEW_` prefix:

```bash
# Override reasoning model
export OPENREVIEW_GATEWAY__MODELS__REASONING__PRIMARY="openai/gpt-4o"

# Override cost limit
export OPENREVIEW_GATEWAY__COST_LIMITS__PER_REVIEW_CENTS=500

# Override retry count
export OPENREVIEW_GATEWAY__FALLBACK__RETRIES=3
```

**Naming Convention**:
- Prefix: `OPENREVIEW_`
- Nesting: `__` (double underscore)
- Word joining: `_` (single underscore)
- Case: uppercase

**Priority Order** (highest to lowest):
1. Environment variables
2. Config file values
3. Default values

## API Key Configuration

API keys are NOT stored in the config file. They are stored in a separate auth file (`~/.config/openreview/auth.json`) with restricted permissions (chmod 600).

**Auth File Schema**:
```json
{
  "openai": "sk-...",
  "anthropic": "sk-ant-...",
  "google": "AIza...",
  "cohere": "...",
  "openrouter": "sk-or-...",
  "huggingface": "hf_...",
  "custom": "..."
}
```

**Environment Variable Overrides**:
```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GOOGLE_API_KEY="AIza..."
export COHERE_API_KEY="..."
export OPENROUTER_API_KEY="sk-or-..."
export HUGGINGFACE_API_KEY="hf_..."
export CUSTOM_API_KEY="..."
```

**Priority**: Environment variables override auth file values.

## YAML Import Schema

The `gateway import` command accepts a YAML file with slot-keyed format:

```yaml
# Import file schema (simplified)
reasoning:
  provider: "openai"
  model: "gpt-4o"
  fallback: "anthropic/claude-3-5-sonnet-20241022"
  params:
    temperature: 0.1
    max_tokens: 4000

extraction:
  provider: "openai"
  model: "gpt-4o-mini"
  params:
    temperature: 0.0

embedding:
  provider: "ollama"
  model: "nomic-embed-text"
  params:
    dimensions: 512

reranking:
  provider: "cohere"
  model: "rerank-3.5"

graph:
  provider: "ollama"
  model: "qwen3:8b"
  params:
    temperature: 0.0

# Optional: API key env var references (NOT inline keys)
api_key_env:
  openai: "OPENAI_API_KEY"
  anthropic: "ANTHROPIC_API_KEY"
  cohere: "COHERE_API_KEY"
```

**Validation Rules**:
- All five slots must be present (reasoning, extraction, embedding, reranking, graph)
- Each slot must have `provider` and `model` fields
- `api_key_env` values are environment variable names, NOT actual keys
- No inline API keys allowed (security requirement)
- All errors reported at once (not just first error)

## Defaults

```python
DEFAULT_GATEWAY_CONFIG = {
    "models": {
        "reasoning": {
            "primary": "ollama/qwen3:8b",
            "fallback": None,
            "params": {"temperature": 0.1, "max_tokens": 4000}
        },
        "extraction": {
            "primary": "ollama/qwen3:4b",
            "fallback": None,
            "params": {"temperature": 0.0, "max_tokens": 2000}
        },
        "embedding": {
            "primary": "ollama/nomic-embed-text",
            "fallback": None,
            "params": {"dimensions": 512}
        },
        "reranking": {
            "primary": "ollama/qwen3-reranker-0.6b",
            "fallback": None,
            "params": {}
        },
        "graph": {
            "primary": "ollama/qwen3:8b",
            "fallback": None,
            "params": {"temperature": 0.0, "max_tokens": 4000}
        }
    },
    "fallback": {
        "retries": 2,
        "retry_delay": 1.0,
        "timeout": 60,
        "on_failure": "error"
    },
    "cost_limits": {
        "per_review_cents": 100,
        "daily_cents": 1000
    },
    "registry": {
        "refresh_days": 7,
        "remote_url": "https://example.com/models.json"
    },
    "logging": {
        "level": "info",
        "debug_file": "~/.openreview/gateway.log"
    }
}
```

## Validation Implementation

```python
from pydantic import BaseModel, Field, field_validator
from typing import Literal

class ModelParams(BaseModel):
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4000, gt=0)
    dimensions: int | None = Field(default=None, gt=0)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    stop: list[str] | None = None

class SlotConfig(BaseModel):
    primary: str
    fallback: str | None = None
    params: ModelParams | None = None
    
    @field_validator("primary", "fallback")
    @classmethod
    def validate_model_format(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if "/" not in v and not v.startswith("ollama/"):
            raise ValueError(f"model must be in format 'provider/model-id', got '{v}'")
        return v

class FallbackConfig(BaseModel):
    retries: int = Field(default=2, ge=0)
    retry_delay: float = Field(default=1.0, gt=0)
    timeout: int = Field(default=60, gt=0)
    on_failure: Literal["error", "skip", "warn"] = "error"

class CostLimits(BaseModel):
    per_review_cents: int = Field(default=100, ge=0)
    daily_cents: int = Field(default=1000, ge=0)

class RegistryConfig(BaseModel):
    refresh_days: int = Field(default=7, gt=0)
    remote_url: str

class LoggingConfig(BaseModel):
    level: Literal["debug", "info", "warning", "error"] = "info"
    debug_file: str = "~/.openreview/gateway.log"

class GatewayConfig(BaseModel):
    models: dict[str, SlotConfig]
    fallback: FallbackConfig = Field(default_factory=FallbackConfig)
    cost_limits: CostLimits = Field(default_factory=CostLimits)
    registry: RegistryConfig
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
```

## Atomic File Writes

All config file writes must use atomic writes to prevent corruption:

```python
import tempfile
import os

def atomic_write_yaml(path: Path, data: dict) -> None:
    """Write YAML config atomically."""
    import yaml
    
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            yaml.safe_dump(data, f, default_flow_style=False)
            f.flush()
            os.fsync(f.fileno())
        os.rename(tmp_path, path)
    except:
        os.unlink(tmp_path)
        raise
```

## Migration Path

If the config schema changes in future versions:
1. Increment schema version in config file
2. Provide migration function in `config/loader.py`
3. Auto-migrate on load if older version detected
4. Preserve user customizations during migration
