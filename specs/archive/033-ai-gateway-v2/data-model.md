# Data Model: AI Gateway v2

**Feature**: 033-ai-gateway-v2 | **Date**: 2026-07-17

## Entities

### ProviderRegistryEntry (shared shape — `models.json` + `config.yml`)
| Field | Type | Source | Notes |
|-------|------|--------|-------|
| `name` | str | pre-listed or user | key; for custom, uppercased+`_` → env var base |
| `base_url` | str | pre-listed (models.json) or user (`--base-url`) | e.g. `https://api.deepseek.com` |
| `api_key_env` | str | derived `{NAME_UPPER}_API_KEY` (custom) or fixed (pre-listed) | credential env var |
| `default_headers` | dict[str,str] | pre-listed where required | e.g. MiniMax/OpenRouter auth headers |
| `capabilities` | CapabilityMetadata | both | embedding / reasoning / context_window / tool_call |
| `is_local` | bool | derived | True if base_url host is localhost/127.0.0.1 or name Ollama-prefixed |
| `source` | `"bundled"` \| `"custom"` | resolution | distinguishes upgrade-merge behavior |

### CapabilityMetadata
| Field | Type | Notes |
|-------|------|-------|
| `embedding` | bool | model can embed |
| `reasoning` | bool | model supports reasoning/CoT |
| `context_window` | int | tokens |
| `tool_call` | bool | model supports tool/function calls |

### CapabilityRequirement (passed by calling agent)
| Field | Type | Notes |
|-------|------|-------|
| `capability` | str | required type, e.g. `"embedding"` |
| `min_context_window` | int \| None | minimum tokens |
| `tool_call` | bool | required tool-call support |

### AgentCapabilityRequirementSet
Six consumers each declare one:
- Extraction Agent (`review/extraction.py`) — chat + context
- QA Agent (`review/qa.py`) — chat + context
- Comparison Agent (`bilateral/comparison.py`) — chat
- Citation Grounding Discriminator (`grounding/discriminator.py`) — chat
- Reranker (`retrieval/rerank.py`) — chat/rerank
- Embedding Engine (`retrieval/dense.py`) — embedding (would mismatch a chat-only model → FR-4 test)

### ErrorClassification (FR-5)
| Field | Type | Notes |
|-------|------|-------|
| `kind` | `"auth"` \| `"rate_limit"` \| `"not_found"` \| `"connection"` \| `"capability_mismatch"` | typed |
| `provider` | str | identity of failing provider (never hardcoded default) |
| `message` | str | human-readable, names provider |

### StreamingOutputEvent (FR-8)
| Field | Type | Notes |
|-------|------|-------|
| `chunk` | str | incremental text |
| `is_final` | bool | terminal chunk flag |
| `timeout_kind` | `"header"` \| `"chunk"` \| None | which timeout fired if aborted |

## State Transitions

- **Registry resolution**: bundled defaults + user custom → merged `ProviderRegistry` (custom + user-edited pre-listed preserved; new bundled entries merged in).
- **Classification**: `classify_provider(model)` → `"local"` | `"cloud"`. On internal error building provider config for a local model → raise (never coerce to `"cloud"`).
- **Capability gate**: requirement + model capabilities → pass | `CapabilityMismatchError` (pre-network).
- **Streaming**: connect → (header timeout 15 s) first chunk → (idle 45 s) subsequent chunks → final. Stall → abort with `ConnectionError`/timeout.

## Validation Rules
- Custom provider name → env var collision (pre-listed OR custom) → reject with naming-collision error.
- `base_url` required for custom provider (FR-3).
- Capability mismatch must name specific gap (e.g. "model X lacks embedding; Embedding Engine requires embedding").

## Relationships
- `ProviderRegistryEntry` 1—* consumed by `SlotConfig` (slot → provider+model).
- `SlotConfig` validated against `CapabilityRequirement` per consumer via `Gateway.call(requirement=...)`.
- `ErrorClassification` produced by `Gateway` error wrapper, carries `ProviderRegistryEntry.name`.
