# CLI Contract: SLM Model Params Extension

**Date**: 2026-07-01 | **Feature**: 006-slm-model-params

## Configuration Contract (config.yml)

### Input: extra_params field on any model slot

```yaml
# Example: Ollama SLM with provider-specific params
gateway:
  models:
    extraction:
      primary: ollama/qwen3:8b
      params:
        temperature: 0.1
        max_tokens: 4096
      extra_params:         # NEW — provider-specific pass-through
        num_gpu: 0          # CPU-only inference
        num_ctx: 4096       # Reduced context window to save RAM
        options:            # Nested structure supported
          mirostat: 2
```

### Behaviour

| Scenario | Behaviour |
|----------|-----------|
| `extra_params` present and valid dict | Merged into LiteLLM call kwargs after `params` |
| `extra_params` absent or `null` | No extra keys added — existing behaviour unchanged |
| `extra_params` is empty dict `{}` | No extra keys added |
| `extra_params` is non-dict (string, list, etc.) | Ignored silently, DEBUG log emitted |
| `extra_params` contains protected key (`model`, `messages`, `input`, `timeout`) | Key stripped before merge, WARNING log emitted |
| `extra_params` contains key that duplicates `params` (e.g. `temperature`) | `extra_params` value wins (applied after `params`) |

### Merge Order

```
1. model    ← from slot config (primary)
2. params   ← temperature, max_tokens from slot config
3. extra_params ← provider-specific, protected keys stripped
4. **kwargs ← caller-provided at runtime (chat/embed method args)
```

## Health Check Contract

### Current output per slot:

```json
{
  "reasoning": {"status": "configured", "provider": "openai"},
  "extraction": {"status": "configured", "provider": "ollama"}
}
```

### New output per slot (when extra_params present):

```json
{
  "reasoning": {"status": "configured", "provider": "openai"},
  "extraction": {"status": "configured", "provider": "ollama", "extra_params": 3}
}
```

The `extra_params` key only appears when the slot has extra params configured. The value is the count of keys (integer), not the keys themselves.

## Python API Contract

### ModelEntry (models.py)

```python
# Before
class ModelEntry(BaseModel):
    slots: list[str]
    context: int | None = None
    # ... existing fields

# After
class ModelEntry(BaseModel):
    slots: list[str]
    context: int | None = None
    # ... existing fields
    extra_params: dict[str, Any] | None = None  # NEW
```

### Gateway._get_litellm_kwargs (router.py)

No signature change. Internal behaviour change:
1. Read `extra_params` from slot config (already done)
2. **NEW**: Strip protected keys from `extra_params`
3. **NEW**: Log stripped keys at WARNING level
4. Merge remaining `extra_params` into call kwargs (already done)
5. **NEW**: Log applied keys at DEBUG level
