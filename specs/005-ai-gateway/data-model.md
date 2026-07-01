# Data Model — AI Gateway (Phase 4)

**Date**: 2026-07-01
**Feature**: specs/005-ai-gateway

## Entities

### SlotConfig (extends existing ModelSlot)

The existing `ModelSlot` in `config/loader.py` already has `primary`, `fallback`, `params`.
The gateway adds an `extra_params` field for provider-specific pass-through (Blueprint R-4).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| primary | str | yes | Model identifier (e.g., `openai/gpt-4o`, `ollama/qwen3:8b`) |
| fallback | str \| None | no | Fallback model identifier |
| params | ModelParams \| None | no | temperature, max_tokens |
| extra_params | dict[str, Any] \| None | no | Provider-specific kwargs forwarded to LiteLLM |

**Validation**: `primary` must match pattern `provider/model_name` or `ollama/model_name`.

### ProviderInfo

Represents an AI provider in the model registry.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | str | yes | Display name (e.g., "OpenAI") |
| env_key | str \| None | no | Environment variable for API key (e.g., "OPENAI_API_KEY") |
| auth_required | bool | yes | Whether an API key is needed (False for Ollama) |
| models | dict[str, ModelEntry] | yes | Available models |

### ModelEntry

A specific model offered by a provider.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| slots | list[str] | yes | Compatible slots (e.g., ["reasoning", "extraction"]) |
| context | int \| None | no | Context window size in tokens |
| dimensions | int \| None | no | Embedding dimensions (embedding models only) |
| ram | str \| None | no | RAM requirement (local models only, e.g., "5.2 GB") |
| recommended | bool | no | Whether this model is recommended for its slots |
| status | str \| None | no | "experimental", "deprecated", etc. |
| note | str \| None | no | Human-readable note |

### CostRecord

Maps to existing `cost_logs` table. New columns: `slot`, `session_id`.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | str (UUID) | yes | Unique record ID |
| review_id | str | yes | Associated review ID |
| session_id | str \| None | no | Session ID passed via gateway methods |
| slot | str \| None | no | Which model slot was used |
| model | str | yes | Model identifier |
| provider | str | yes | Provider name |
| prompt_tokens | int | yes | Input tokens |
| completion_tokens | int | yes | Output tokens |
| cost_cents | int | yes | Estimated cost in cents |
| created_at | str | yes | ISO timestamp |

### GatewayError

Custom exception hierarchy for gateway-specific errors.

| Error | Parent | Description |
|-------|--------|-------------|
| GatewayError | Exception | Base gateway error |
| ProviderError | GatewayError | Provider returned an error (auth, rate limit, model not found) |
| SlotNotConfiguredError | GatewayError | Requested slot has no model assigned |
| AllProvidersFailedError | GatewayError | Primary and fallback both failed |

## Relationships

```
GatewayConfig (existing in loader.py)
  └── GatewayModels
       ├── reasoning: ModelSlot (+ extra_params)
       ├── extraction: ModelSlot (+ extra_params)
       ├── embedding: EmbeddingSlot
       ├── reranking: RerankingSlot
       └── graph: ModelSlot (+ extra_params)

ModelRegistry (models.json)
  └── providers: dict[str, ProviderInfo]
       └── models: dict[str, ModelEntry]

Gateway (router.py)
  ├── uses GatewayConfig (from config/loader.py)
  ├── uses auth data (from config/auth.py)
  ├── uses ModelRegistry (from registry.py)
  ├── uses CostTracker (from cost.py)
  └── calls litellm.completion / .embedding / .rerank
```

## Database Migration (003_gateway.sql)

```sql
-- Migration 003: Gateway enhancements
-- Adds slot and session_id columns to cost_logs

ALTER TABLE cost_logs ADD COLUMN slot TEXT;
ALTER TABLE cost_logs ADD COLUMN session_id TEXT;

CREATE INDEX IF NOT EXISTS idx_cost_logs_session_id ON cost_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_cost_logs_slot ON cost_logs(slot);
```
